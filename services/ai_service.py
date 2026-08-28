import os
import json
import logging
import base64
import re
from datetime import datetime
from config import Config
from clauses.agreement_renderer import generate_preview_html, generate_docx
from services.agreement_state import AgreementState, FieldEntry, FieldStatus, ProvenanceSource
from services.interview_engine import InterviewEngine
from services.places_service import places_service

logger = logging.getLogger("AgreementAI_Service")


class AadhaarOcrError(RuntimeError):
    """Raised when a real Aadhaar OCR response cannot be produced."""


class AIService:
    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.gemini_key = Config.GEMINI_API_KEY
        
    def render_clauses_agreement(self, data: dict) -> str:
        """Render complete HTML agreement using exact static clauses from simple_rental or leave_license."""
        agr_type = data.get("agreement_type", "simple_rental")
        data["agreement_type"] = agr_type
        
        # Supply defaults if missing
        if not data.get("P1") and not data.get("today_date") and not data.get("agreement_date"):
            data["P1"] = "24th day of July 2026"
        if not data.get("P16") and not data.get("agreement_start_date"):
            data["P16"] = "1st day of August 2026"
        if not data.get("P17") and not data.get("agreement_end_date"):
            data["P17"] = "30th day of June 2027"
        if not data.get("P14") and not data.get("rent_amount_words"):
            data["P14"] = "Twenty Five Thousand"
        if not data.get("P20") and not data.get("security_deposit_words"):
            data["P20"] = "One Lakh Fifty Thousand"
            
        return generate_preview_html(data)

    def review_and_modify_agreement(self, agreement_html: str, user_prompt: str, agreement_type: str = "simple_rental") -> dict:
        """AI Legal Copilot — answers legal questions and modifies agreement clauses."""
        api_key = self.gemini_key or os.getenv("GEMINI_API_KEY", "")

        if self.provider == "gemini" and api_key:
            try:
                from google import genai
                from google.genai import types

                agreement_label = "Leave & License" if "leave" in agreement_type else "Simple Rental"

                # Build a field list for the AI to reference
                field_keys_hint = ", ".join([
                    "notice_period", "monthly_rent", "security_deposit", "increase_percent",
                    "lockin_months", "penalty_deduction", "maintenance",
                    "agreement_start_date", "agreement_end_date", "agreement_date",
                    "owner1_name", "owner1_age", "owner1_occupation", "owner1_address",
                    "tenant1_name", "tenant1_age", "tenant1_occupation", "tenant1_address",
                    "property_address", "annexure", "tenant_type",
                ])

                system_prompt = f"""You are an expert Indian property law copilot for AgreementAI.
You know Indian tenancy law thoroughly (Transfer of Property Act, Rent Control Acts, Registration Act, etc.).
Explain legal concepts in plain language. Always reference actual clause numbers, values, dates, and names from the document.
Read the ENTIRE document carefully before answering — do not say a clause is missing if it exists anywhere in the text.

COMPLETE DOCUMENT ({agreement_label}):
\"\"\"
{agreement_html}
\"\"\"

The agreement is generated from a form. The available form field keys are:
{field_keys_hint}

Return ONLY a single valid JSON object:
- For questions: {{"action":"answer","response":"<thorough answer with emojis and markdown, referencing specific clause numbers and values from the document>"}}
- For edits (change/add/remove/modify): {{"action":"modify","response":"<summary>","find":"<exact text to find in document>","replace":"<replacement text>","field_updates":{{"<field_key>":"<new_value>"}}}}

RULES:
- For questions, always cite the specific clause/point number and quote relevant text.
- For edits, use find/replace with EXACT text from the document. Only include the minimal changed portion.
- For edits, ALWAYS include "field_updates" mapping the affected form field key to its new value.
  Examples: notice_period changed to 1 Month → {{"notice_period":"1 Month"}}
            monthly_rent changed to 30000 → {{"monthly_rent":"30000"}}
            lockin_months changed to 6 → {{"lockin_months":"6"}}
            penalty_deduction changed to 90 → {{"penalty_deduction":"90"}}
- If the edit does not map to any form field (e.g. adding a completely new clause), use an empty object for field_updates.
- Give practical, actionable legal advice — not generic textbook answers."""

                client = genai.Client(api_key=api_key)
                model_name = getattr(Config, "GEMINI_MODEL", "gemini-2.5-flash")
                # Fallback model chain for copilot
                copilot_models = [model_name, "gemini-3.6-flash", "gemini-2.5-flash-preview"]
                response = None
                for m_name in copilot_models:
                    try:
                        response = client.models.generate_content(
                            model=m_name,
                            contents=f"User: {user_prompt}",
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.4,
                                system_instruction=system_prompt,
                            ),
                        )
                        if response and response.text:
                            break
                    except Exception as copilot_err:
                        logger.warning(f"Copilot model {m_name} error: {copilot_err}")
                        continue
                if not response or not response.text:
                    raise Exception("All copilot models exhausted")
                raw = (response.text or "").strip()
                result = self._safe_parse_json(raw)

                # If AI returned find/replace, apply it to the HTML
                if result.get("action") == "modify" and result.get("find"):
                    find_text = result["find"]
                    replace_text = result.get("replace", "")
                    if find_text in agreement_html:
                        result["updated_html"] = agreement_html.replace(find_text, replace_text, 1)
                    else:
                        result["updated_html"] = agreement_html
                        result["response"] += " (Note: Could not locate the exact text to modify. Please edit manually.)"

                    # Server-side fallback: detect field changes if AI didn't provide field_updates
                    if not result.get("field_updates"):
                        result["field_updates"] = self._detect_field_updates(find_text, replace_text)

                if isinstance(result, dict) and result.get("response"):
                    return result
            except Exception as e:
                logger.warning(f"Gemini copilot error, using fallback: {e}")

        # ── Fallback (only if API fails completely) ──
        return {
            "action": "answer",
            "response": "📋 I wasn't able to connect to the AI service right now. Please check your Gemini API key and try again."
        }

    def _detect_field_updates(self, find_text: str, replace_text: str) -> dict:
        """Server-side fallback: detect which form field was changed based on find/replace text.

        Compares old vs. new text to extract value changes for known form fields.
        This is only used when the AI doesn't return field_updates itself.
        """
        import re as _re
        updates = {}

        # Notice period patterns: "1 Month", "2 Months", "3 Months"
        notice_old = _re.search(r'(\d+)\s*[Mm]onths?', find_text)
        notice_new = _re.search(r'(\d+)\s*[Mm]onths?', replace_text)
        if notice_old and notice_new and notice_old.group(0) != notice_new.group(0):
            n = int(notice_new.group(1))
            updates["notice_period"] = "1 Month" if n == 1 else f"{n} Months"

        # Lockin months
        lockin_old = _re.search(r'(?:lock[\-\s]*in.*?|minimum tenure.*?)(\d+)\s*[Mm]onths', find_text)
        lockin_new = _re.search(r'(?:lock[\-\s]*in.*?|minimum tenure.*?)(\d+)\s*[Mm]onths', replace_text)
        if lockin_old and lockin_new and lockin_old.group(1) != lockin_new.group(1):
            updates["lockin_months"] = lockin_new.group(1)

        # Penalty deduction days
        penalty_old = _re.search(r'(\d+)\s*days?\s*(?:of\s*)?(?:monthly\s*)?rent', find_text, _re.I)
        penalty_new = _re.search(r'(\d+)\s*days?\s*(?:of\s*)?(?:monthly\s*)?rent', replace_text, _re.I)
        if penalty_old and penalty_new and penalty_old.group(1) != penalty_new.group(1):
            updates["penalty_deduction"] = penalty_new.group(1)

        # Rent amount (Rs. X,XXX or Rs. XX,XXX)
        rent_old = _re.search(r'Rs\.?\s*([\d,]+)', find_text)
        rent_new = _re.search(r'Rs\.?\s*([\d,]+)', replace_text)
        if rent_old and rent_new and rent_old.group(1) != rent_new.group(1):
            # Could be rent or deposit — check context
            if 'deposit' in find_text.lower() or 'deposit' in replace_text.lower():
                updates["security_deposit"] = rent_new.group(1).replace(",", "")
            else:
                updates["monthly_rent"] = rent_new.group(1).replace(",", "")

        # Increase percent
        inc_old = _re.search(r'(\d+(?:\.\d+)?)\s*[-–]?\s*\d*%', find_text)
        inc_new = _re.search(r'(\d+(?:\.\d+)?)\s*[-–]?\s*\d*%', replace_text)
        if inc_old and inc_new and inc_old.group(1) != inc_new.group(1):
            updates["increase_percent"] = inc_new.group(1)

        return updates

    def _safe_parse_json(self, raw_text: str) -> dict:
        """Robustly parse JSON responses from LLM, handling markdown blocks, extra text, and unescaped newlines."""
        if not raw_text:
            return {}
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        # 1. Standard loads
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 2. Strict=False (allows unescaped newlines inside strings)
        try:
            return json.loads(cleaned, strict=False)
        except Exception:
            pass

        # 3. JSONDecoder raw_decode
        try:
            decoder = json.JSONDecoder(strict=False)
            res, _ = decoder.raw_decode(cleaned)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 4. Fallback regex extraction
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', cleaned)
        action_val = action_match.group(1) if action_match else "answer"

        resp_match = re.search(r'"response"\s*:\s*"(.*)"', cleaned, re.DOTALL)
        if resp_match:
            resp_val = resp_match.group(1).replace('\\"', '"').replace('\\n', '\n').strip()
            return {"action": action_val, "response": resp_val}

        return {"action": "answer", "response": cleaned}

    def understand_and_extract(self, user_message: str, current_state: AgreementState) -> dict:
        """
        AI Natural Language Understanding & Extraction Adapter.
        1. Analyzes user natural language text (or batch prompt).
        2. Extracts multiple entities in one pass.
        3. Updates current_state with extracted fields and provenance.
        4. Applies deterministic calculations (end date, words).
        5. Queries InterviewEngine for gaps, readiness, and next question + suggestion chips.
        6. Formulates an empathetic conversational assistant message.
        """
        api_key = self.gemini_key or os.getenv("GEMINI_API_KEY", "")
        extracted_dict: dict = {}
        confidences: dict = {}

        # 0. Detect user role from message
        msg_lower = user_message.lower().strip()
        if re.search(r'\b(i am|i\'m|im)\s+(the\s+)?(owner|landlord|lessor)\b', msg_lower) or msg_lower in ("owner", "landlord"):
            current_state.user_role = "owner"
        elif re.search(r'\b(i am|i\'m|im)\s+(the\s+)?(tenant|renter|lessee)\b', msg_lower) or msg_lower in ("tenant", "renter"):
            current_state.user_role = "tenant"
        elif re.search(r'\b(i am|i\'m|im)\s+(a\s+)?(broker|agent)\b', msg_lower) or "broker" in msg_lower:
            current_state.user_role = "broker"

        # 1. High-speed Offline Rule Extractor (instant sub-millisecond execution for chips, cards, dates, rent, deposit, tenure, names)
        rule_extracted = self._extract_entities_rule_based(user_message, current_state)
        if rule_extracted:
            for k, v in rule_extracted.items():
                extracted_dict[k] = v
                confidences[k] = 0.95

        # 2. If rule extractor didn't match anything and Gemini API is configured, use LLM as smart fallback for unstructured freeform paragraphs
        if not extracted_dict and self.provider == "gemini" and (self.gemini_key or os.getenv("GEMINI_API_KEY")):
            try:
                from google import genai
                from google.genai import types
                api_key = self.gemini_key or os.getenv("GEMINI_API_KEY")
                system_prompt = """You are an expert Indian Rental Agreement Data Extraction Engine for AgreementAI.
Your job is to read the user's message and extract all rental agreement parameters in ONE PASS.
Target field keys:
- owner1_name: Full name of property owner/landlord (string)
- owner1_age: Numeric age in years (string/number, e.g. "35", "52")
- owner1_careof: "Father Name" or "Husband Name"
- owner1_careofname: Full name of owner's father or husband (string)
- owner1_address: Permanent address of owner (string)
- tenant1_name: Full name of primary tenant/licensee (string)
- tenant1_age: Numeric age in years (string/number, e.g. "28", "34")
- tenant1_careof: "Father Name" or "Husband Name"
- tenant1_careofname: Full name of tenant's father or husband (string)
- tenant1_address: Permanent address of tenant (string)
- property_address: Full address of the rented property (string)
- flat_no: Flat / Unit / Villa number (string, e.g. "504", "Flat 302")
- society_name: Building / Apartment / Society name (string, e.g. "Brigade Gateway", "Green Acres")
- city: City name (string, e.g. "Bangalore", "Hyderabad", "Mumbai", "Pune", "Delhi")
- monthly_rent: Numeric monthly rent (number/string, e.g. 35000, 55000)
- security_deposit: Numeric deposit (number/string, e.g. 150000, 300000)
- agreement_start_date: Start date (string, DD-MM-YYYY or DD Month YYYY)
- tenure_months: Duration in months (number/string, e.g. "11", "12")
- maintenance: "Including" (if included in rent) | "Excluding" (if tenant pays separately)
- notice_period: "1 Month" | "2 Months" | "3 Months"
- lockin_months: Minimum stay duration in months (string, e.g. "6", "11")
- penalty_deduction: Days of rent forfeited on early exit (string, e.g. "30", "60")
- tenant_type: "Family" | "Bachelor"
- annexure: List of fixtures/fittings if mentioned

Return ONLY a single valid JSON object:
{
  "extracted": { "<field_key>": "<extracted_value>" },
  "confidences": { "<field_key>": 0.95 }
}
"""
                client = genai.Client(api_key=api_key)
                known_fields_summary = {k: current_state.get_value(k) for k in (current_state.fields or {}) if current_state.get_value(k)}
                next_interaction_info = InterviewEngine.plan_next_interaction(current_state)
                target_focus = next_interaction_info.get("target_fields", [])
                
                extraction_prompt = f"""Current Known Agreement Fields:
{json.dumps(known_fields_summary, indent=2)}

Current Target Fields Being Asked: {target_focus}

User's Message:
\"\"\"{user_message}\"\"\"

Extract agreement fields from the user message.
"""
                candidate_models = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-2.5-flash-preview"]
                for model_name in candidate_models:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=extraction_prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.1,
                                system_instruction=system_prompt,
                            ),
                        )
                        raw = (response.text or "").strip()
                        parsed = self._safe_parse_json(raw)
                        if isinstance(parsed, dict):
                            llm_extracted = parsed.get("extracted", parsed)
                            llm_conf = parsed.get("confidences", {})
                            if llm_extracted:
                                for lk, lv in llm_extracted.items():
                                    if lk not in extracted_dict:
                                        extracted_dict[lk] = lv
                                        confidences[lk] = llm_conf.get(lk, 0.9)
                                break
                    except Exception as model_err:
                        logger.warning(f"Gemini extraction fallback notice ({model_name}): {model_err}")
            except Exception as e:
                logger.warning(f"Gemini extraction setup notice: {e}")

        # Clean false-positive names
        for nk in ("owner1_name", "tenant1_name", "owner1_careofname", "tenant1_careofname"):
            if nk in extracted_dict and str(extracted_dict[nk]).strip().lower() in (
                "father", "husband", "father's name", "husband's name", "father name", "husband name",
                "is", "name", "pays", "pays extra", "pay", "will pay", "pays maintenance",
                "excluding", "including", "extra", "maintenance", "tenant", "owner", "landlord"
            ):
                del extracted_dict[nk]
                if nk in confidences:
                    del confidences[nk]

        # Prevent duplicate assignment of careofname into tenant1_name / owner1_name
        if "owner1_careofname" in extracted_dict or "tenant1_careofname" in extracted_dict:
            cf_val = extracted_dict.get("owner1_careofname") or extracted_dict.get("tenant1_careofname")
            if extracted_dict.get("tenant1_name") == cf_val:
                del extracted_dict["tenant1_name"]
                if "tenant1_name" in confidences:
                    del confidences["tenant1_name"]

        # Safeguard: Do not overwrite confirmed owner or tenant names with action phrases
        if current_state and current_state.get_value("tenant1_name") and "tenant1_name" in extracted_dict:
            if not re.search(r'\b(?:change\s+|update\s+|set\s+)?tenant(?:\'s)?\s+name\b', user_message, re.I):
                del extracted_dict["tenant1_name"]
                if "tenant1_name" in confidences:
                    del confidences["tenant1_name"]

        if current_state and current_state.get_value("owner1_name") and "owner1_name" in extracted_dict:
            if not re.search(r'\b(?:change\s+|update\s+|set\s+)?owner(?:\'s)?\s+name\b', user_message, re.I):
                del extracted_dict["owner1_name"]
                if "owner1_name" in confidences:
                    del confidences["owner1_name"]

        # Safeguard: Prevent accidental overwrite of confirmed monthly_rent by deposit or duration inputs
        if current_state and current_state.get_value("monthly_rent"):
            if not re.search(r'\b(?:change\s+|update\s+|set\s+)?(?:monthly\s+)?rent(al)?\b', user_message, re.I):
                if "monthly_rent" in extracted_dict:
                    # If security_deposit is missing in state, move this extracted amount to security_deposit
                    if not current_state.get_value("security_deposit") and "security_deposit" not in extracted_dict:
                        extracted_dict["security_deposit"] = extracted_dict["monthly_rent"]
                        confidences["security_deposit"] = confidences.get("monthly_rent", 0.9)
                    del extracted_dict["monthly_rent"]
                    if "monthly_rent" in confidences:
                        del confidences["monthly_rent"]

        # Safeguard: Never allow notice period or lock-in inputs to set or overwrite tenure_months
        if re.search(r'\b(?:notice|lock[\-\s]*in)\b', user_message, re.I):
            if "tenure_months" in extracted_dict:
                del extracted_dict["tenure_months"]
                if "tenure_months" in confidences:
                    del confidences["tenure_months"]

        # Safeguard: Never allow party profile / contact inputs to be extracted as property_address
        if "property_address" in extracted_dict:
            pa_val = str(extracted_dict["property_address"])
            if re.search(r'\b(?:owner\s+profile|tenant\s+profile|mobile\s+\d|email\s+[^\s@]+@|occupation)\b', pa_val, re.I) or re.search(r'\b(?:owner|tenant)\s+profile\b', user_message, re.I):
                del extracted_dict["property_address"]
                if "property_address" in confidences:
                    del confidences["property_address"]

        # 3. Update AgreementState with extracted fields (preserve provenance!)
        newly_extracted_keys = []
        for k, v in extracted_dict.items():
            if v is not None and str(v).strip() != "":
                conf = confidences.get(k, 0.9)
                is_profile_f = k in ("owner1_occupation", "owner1_phone", "owner1_email", "tenant1_occupation", "tenant1_phone", "tenant1_email")
                current_state.set_field(
                    key=k,
                    value=str(v),
                    source=ProvenanceSource.EXTRACTED_CHAT,
                    confidence=1.0 if is_profile_f else conf,
                    status=FieldStatus.CONFIRMED if is_profile_f else FieldStatus.EXTRACTED,
                )
                newly_extracted_keys.append(k)

        # 3.5. Google Places Resolution: ONLY resolve genuine building/society/area queries (never person names)
        prop_query = extracted_dict.get("property_address") or extracted_dict.get("society_name")
        is_genuine_property = False
        if prop_query:
            pq_lower = prop_query.lower()
            prop_tokens = (
                "flat", "apartment", "society", "nagar", "colony", "road", "street",
                "layout", "enclave", "heights", "towers", "residency", "villas", "sector",
                "phase", "palace", "view", "gardens", "acres", "greens", "floor", "building",
                "kondapur", "gachibowli", "hitech", "madhapur", "miyapur", "whitefield",
                "indiranagar", "koramangala", "bellandur", "marathahalli", "baner", "wakad",
                "hinjewadi", "kharadi", "andheri", "powai", "thane", "navi mumbai"
            )
            # Must have property tokens, numbers (door/flat no), or commas indicating an address
            if any(t in pq_lower for t in prop_tokens) or re.search(r'\d', prop_query) or "," in prop_query:
                is_genuine_property = True

        if prop_query and is_genuine_property and places_service.is_configured():
            try:
                resolved = places_service.search_and_resolve(prop_query)
                if resolved:
                    if resolved.get("society_name"):
                        current_state.set_field("society_name", resolved["society_name"], source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.98)
                        if "society_name" not in newly_extracted_keys:
                            newly_extracted_keys.append("society_name")
                    user_addr = current_state.get_value("property_address") or ""
                    if resolved.get("property_address") and (not user_addr or len(user_addr) < 25):
                        current_state.set_field("property_address", resolved["property_address"], source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.98)
                        if "property_address" not in newly_extracted_keys:
                            newly_extracted_keys.append("property_address")
                    res_city = resolved.get("city")
                    curr_city = current_state.get_value("city") or ""
                    if res_city and (not curr_city or curr_city.lower() in places_service._INVALID_CITY_TOKENS):
                        current_state.set_field("city", res_city, source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.98)
                        if "city" not in newly_extracted_keys:
                            newly_extracted_keys.append("city")
                    if resolved.get("pincode") and not current_state.get_value("pincode"):
                        current_state.set_field("pincode", resolved["pincode"], source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.98)
                        if "pincode" not in newly_extracted_keys:
                            newly_extracted_keys.append("pincode")
                    if resolved.get("state") and not current_state.get_value("state"):
                        current_state.set_field("state", resolved["state"], source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.98)
            except Exception as e:
                logger.warning(f"Places auto-resolution notice: {e}")

        # Ensure PIN code is included in property_address if available and not already present
        pin = current_state.get_value("pincode")
        addr = current_state.get_value("property_address")
        if pin and addr and str(pin) not in str(addr):
            if re.search(r'\bIndia\b', addr, re.I):
                addr_with_pin = re.sub(r'(?i)\bIndia\b', f"{pin}, India", addr).strip()
            else:
                addr_with_pin = f"{addr} - {pin}"
            current_state.set_field("property_address", addr_with_pin, source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.98)
            if "property_address" not in newly_extracted_keys:
                newly_extracted_keys.append("property_address")

        # 4. Apply deterministic auto-calculations (words, end date)
        calculated_keys = InterviewEngine.apply_auto_calculations(current_state)

        # 5. Evaluate deterministic readiness & next question
        readiness = InterviewEngine.evaluate_readiness(current_state)
        next_interaction = InterviewEngine.plan_next_interaction(current_state)

        # 6. Build structured assistant message
        assistant_message = self._compose_assistant_response(
            newly_extracted_keys=newly_extracted_keys,
            calculated_keys=calculated_keys,
            current_state=current_state,
            next_interaction=next_interaction,
            readiness=readiness,
        )

        # 7. Generate live HTML preview
        try:
            preview_html = generate_preview_html(current_state.to_flat_dict())
        except Exception as e:
            logger.warning(f"Live preview generation error: {e}")
            preview_html = ""

        return {
            "success": True,
            "assistant_message": assistant_message,
            "next_interaction": next_interaction,
            "readiness": readiness,
            "newly_extracted_keys": newly_extracted_keys,
            "calculated_keys": calculated_keys,
            "agreement_state": current_state.to_client_payload(),
            "preview_html": preview_html,
        }

    def _compose_assistant_response(
        self,
        newly_extracted_keys: list,
        calculated_keys: list,
        current_state: AgreementState,
        next_interaction: dict,
        readiness: dict,
    ) -> str:
        """Composes a natural, conversational response acknowledging captured info and presenting the next question."""
        parts = []

        if newly_extracted_keys:
            # Build bulleted acknowledgment of captured details
            labels_map = {
                "owner1_name": "👤 Owner Name",
                "owner1_age": "🧓 Owner Age",
                "owner1_careofname": "👨 Owner Father/Husband",
                "owner1_address": "📍 Owner Address",
                "tenant1_name": "👤 Tenant Name",
                "tenant1_age": "🧓 Tenant Age",
                "tenant1_careofname": "👨 Tenant Father/Husband",
                "tenant1_address": "📍 Tenant Address",
                "property_address": "🏠 Property",
                "flat_no": "🚪 Unit/Flat",
                "society_name": "🏢 Society",
                "city": "🌆 City",
                "pincode": "📮 PIN Code",
                "state": "🗺️ State",
                "monthly_rent": "💰 Monthly Rent",
                "security_deposit": "💎 Security Deposit",
                "agreement_start_date": "📅 Start Date",
                "agreement_end_date": "📅 End Date",
                "maintenance": "💡 Maintenance",
                "notice_period": "⏳ Notice Period",
                "lockin_months": "🔒 Lock-in",
                "tenant_poc": "👥 Bachelor SPOC",
            }
            summary_items = []
            for k in newly_extracted_keys:
                label = labels_map.get(k, k.replace("_", " ").title())
                val = current_state.get_value(k)
                if k in ("monthly_rent", "security_deposit"):
                    try:
                        n = int(str(val).replace(",", ""))
                        val = f"₹{n:,}"
                    except Exception:
                        pass
                summary_items.append(f"• **{label}:** {val}")

            # If party profile (occupation / phone / email) is being answered
            owner_profile_keys = {"owner1_occupation", "owner1_phone", "owner1_email"}
            tenant_profile_keys = {"tenant1_occupation", "tenant1_phone", "tenant1_email"}

            has_owner_prof = any(k in owner_profile_keys for k in newly_extracted_keys)
            has_tenant_prof = any(k in tenant_profile_keys for k in newly_extracted_keys)

            if has_owner_prof and has_tenant_prof:
                o_name = current_state.get_value("owner1_name") or "Owner"
                t_name = current_state.get_value("tenant1_name") or "Tenant"
                o_occ = current_state.get_value("owner1_occupation", "Not specified")
                o_ph = current_state.get_value("owner1_phone", "Not specified")
                o_em = current_state.get_value("owner1_email", "Not specified")
                t_occ = current_state.get_value("tenant1_occupation", "Not specified")
                t_ph = current_state.get_value("tenant1_phone", "Not specified")
                t_em = current_state.get_value("tenant1_email", "Not specified")
                parts.append(
                    f"✨ **Got it! I've captured contact & profile details for both parties:**\n"
                    f"• 🏠 **Owner ({o_name}):** {o_occ} | 📱 {o_ph} | 📧 {o_em}\n"
                    f"• 👤 **Tenant ({t_name}):** {t_occ} | 📱 {t_ph} | 📧 {t_em}"
                )
            elif has_owner_prof:
                o_name = current_state.get_value("owner1_name") or "Owner"
                occ = current_state.get_value("owner1_occupation", "Not specified")
                ph = current_state.get_value("owner1_phone", "Not specified")
                em = current_state.get_value("owner1_email", "Not specified")
                parts.append(
                    f"✨ **Got it! I've captured contact & profile details for {o_name}:**\n"
                    f"• 💼 **Occupation:** {occ}\n"
                    f"• 📱 **Phone:** {ph}\n"
                    f"• 📧 **Email:** {em}"
                )
            elif has_tenant_prof:
                t_name = current_state.get_value("tenant1_name") or "Tenant"
                occ = current_state.get_value("tenant1_occupation", "Not specified")
                ph = current_state.get_value("tenant1_phone", "Not specified")
                em = current_state.get_value("tenant1_email", "Not specified")
                parts.append(
                    f"✨ **Got it! I've captured contact & profile details for {t_name}:**\n"
                    f"• 💼 **Occupation:** {occ}\n"
                    f"• 📱 **Phone:** {ph}\n"
                    f"• 📧 **Email:** {em}"
                )
            # If lock-in is being answered, generate the comprehensive Agreement Dates & Terms milestone receipt!
            elif any(k in ("lockin", "lockin_months") for k in newly_extracted_keys):
                start_d = current_state.get_value("agreement_start_date", "-")
                end_d = current_state.get_value("agreement_end_date", "-")
                notice_p = current_state.get_value("notice_period", "1 Month")
                lockin_m = current_state.get_value("lockin_months", "0")
                lockin_str = "No Lock-in" if (str(lockin_m) == "0" or current_state.get_value("lockin") == "N") else f"{lockin_m} Months"
                parts.append(
                    f"✨ **Got it! I've captured Agreement Dates details:**\n"
                    f"• 📅 **Start Date recorded as** {start_d}\n"
                    f"• 📅 **End Date recorded as** {end_d}\n"
                    f"• ⏱️ **Notice Period:** {notice_p}\n"
                    f"• 🔒 **Lock-in Period:** {lockin_str}"
                )
            # If rent escalation (increase_percent) is being answered or completed
            elif any(k in ("increase_percent", "rent_increase_type") for k in newly_extracted_keys) and current_state.get_value("increase_percent"):
                rent_v = current_state.get_value("monthly_rent", "-")
                dep_v = current_state.get_value("security_deposit", "-")
                maint_v = current_state.get_value("maintenance", "Including")
                inc_val = current_state.get_value("increase_percent")
                inc_type = current_state.get_value("rent_increase_type") or "% of Rent"
                try: rent_v = f"₹{int(str(rent_v).replace(',', '')):,}"
                except Exception: pass
                try: dep_v = f"₹{int(str(dep_v).replace(',', '')):,}"
                except Exception: pass
                maint_label = "Excluding (Extra)" if maint_v == "Excluding" else "Included in Rent"
                
                inc_label = str(inc_val)
                if not inc_label.startswith("₹") and not inc_label.endswith("%"):
                    inc_label = f"{inc_label}%"
                if "fixed" in str(inc_type).lower():
                    escalation_str = f"Fixed {inc_label} per annum"
                else:
                    escalation_str = f"{inc_label} Annual Increase"

                parts.append(
                    f"✨ **Got it! I've captured financial details:**\n"
                    f"• 💰 **Monthly Rent:** {rent_v}\n"
                    f"• 💎 **Security Deposit:** {dep_v}\n"
                    f"• 💡 **Maintenance:** {maint_label}\n"
                    f"• 📈 **Rent Increase:** {escalation_str}"
                )
            elif len(newly_extracted_keys) == 1:
                k = newly_extracted_keys[0]
                if k == "tenure_months":
                    end_d = current_state.get_value("agreement_end_date")
                    val = current_state.get_value(k)
                    if end_d:
                        parts.append(f"✨ **Got it! Agreement duration set to {val} Months** *(Until {end_d})*")
                    else:
                        parts.append(f"✨ **Got it! Agreement duration set to {val} Months**")
                else:
                    label = labels_map.get(k, k.replace("_", " ").title())
                    val = current_state.get_value(k)
                    if k in ("monthly_rent", "security_deposit"):
                        try:
                            n = int(str(val).replace(",", ""))
                            val = f"₹{n:,}"
                        except Exception:
                            pass
                    elif k == "maintenance":
                        val = "Excluding (Extra)" if val == "Excluding" else "Included in Rent"
                    parts.append(f"✨ **Got it! {label} recorded as {val}**")
            else:
                financial_keys = {"monthly_rent", "security_deposit", "maintenance", "rent_increase_type"}
                date_keys = {"agreement_start_date", "agreement_end_date", "tenure_months"}
                owner_keys = {"owner1_name", "owner1_age", "owner1_careofname", "owner1_address", "owner1_careof"}
                tenant_keys = {"tenant1_name", "tenant1_age", "tenant1_careofname", "tenant1_address", "tenant1_careof"}
                prop_keys = {"property_address", "flat_no", "society_name", "city", "pincode"}

                keys_set = set(newly_extracted_keys)
                if keys_set.issubset(financial_keys) or ("monthly_rent" in keys_set and "security_deposit" in keys_set):
                    if not current_state.get_value("increase_percent"):
                        category_label = "rent terms"
                    else:
                        category_label = "financial details"
                elif keys_set.issubset(date_keys):
                    category_label = "lease duration details"
                elif keys_set.issubset(owner_keys):
                    category_label = "landlord details"
                elif keys_set.issubset(tenant_keys):
                    category_label = "tenant details"
                elif keys_set.issubset(prop_keys):
                    category_label = "property details"
                else:
                    clean_keys = [k for k in newly_extracted_keys if k not in ("lockin", "penalty_deduction", "monthly_rent_words", "security_deposit_words")]
                    category_label = f"{len(clean_keys)} agreement details"

                # Filter out redundant internal fields from summary items
                visible_summary_items = [
                    f"• **{labels_map.get(k, k.replace('_', ' ').title())}:** {current_state.get_value(k)}"
                    for k in newly_extracted_keys
                    if k not in ("lockin", "penalty_deduction", "monthly_rent_words", "security_deposit_words")
                ]
                if visible_summary_items:
                    parts.append(f"✨ **Got it! I've captured {category_label}:**\n" + "\n".join(visible_summary_items))

            # If user entered a single first name, add a helpful note
            for name_k in ("owner1_name", "tenant1_name"):
                if name_k in newly_extracted_keys:
                    name_val = str(current_state.get_value(name_k) or "").strip()
                    if " " not in name_val and len(name_val) > 1:
                        parts.append(f"💡 *(If you have a surname / last name like **{name_val} Agarwal**, you can tell me anytime).*")

        # Add Next Question
        question_text = next_interaction.get("question_text", "")
        if question_text:
            if parts:
                parts.append("\n---\n" + question_text)
            else:
                parts.append(question_text)

        return "\n\n".join(parts)

    def _extract_entities_rule_based(self, text: str, current_state: AgreementState = None) -> dict:
        """
        High-precision regex/rule-based extractor for Indian rental expressions.
        Extracts rent, deposit, start date, tenure, names, age, careof, property, maintenance, and lockin.
        """
        extracted = {}
        cleaned = text.strip()
        user_role = getattr(current_state, "user_role", "owner").lower() if current_state else "owner"

        # 0. Check for structured in-chat Aadhaar extraction payload
        if "from uploaded aadhaar id" in cleaned.lower():
            is_owner = bool(re.search(r'\bowner\b', cleaned, re.I))
            is_tenant = bool(re.search(r'\btenant\b', cleaned, re.I))
            prefix = "owner1_" if is_owner else ("tenant1_" if is_tenant else "owner1_")
            
            name_m = re.search(r'name\s+is\s+([^,]+)', cleaned, re.I)
            if name_m and name_m.group(1):
                extracted[f"{prefix}name"] = name_m.group(1).strip()

            age_m = re.search(r'age\s+is\s+(\d+)', cleaned, re.I)
            if age_m and age_m.group(1):
                extracted[f"{prefix}age"] = age_m.group(1).strip()

            careof_m = re.search(r'careof\s+is\s+([^,]+)', cleaned, re.I)
            if careof_m and careof_m.group(1):
                extracted[f"{prefix}careof"] = careof_m.group(1).strip()
                
            rel_m = re.search(r'relation\s+is\s+([^,]+)', cleaned, re.I)
            if rel_m and rel_m.group(1):
                extracted[f"{prefix}careofname"] = rel_m.group(1).strip()
                
            addr_m = re.search(r'address\s+is\s+([^.\n]+)', cleaned, re.I)
            if addr_m and addr_m.group(1):
                extracted[f"{prefix}address"] = addr_m.group(1).strip()
                
            return extracted

        # 0.5. Standalone Age (e.g. "35", "35 years", "35 years old", "age 35", "i am 35")
        age_m = re.search(r'\b(?:age(?:\s+is)?\s*|i\s+am\s+)(\d{2})\s*(?:years?\s*old|yrs?)?', cleaned, re.I)
        if not age_m:
            lone_num = re.match(r'^\s*(\d{2})\s*(?:years?\s*old|yrs?|years?)?\s*$', cleaned, re.I)
            if lone_num and 18 <= int(lone_num.group(1)) <= 95:
                age_m = lone_num
        if age_m:
            val_age = age_m.group(1)
            target_prefix = "tenant1_" if (user_role == "tenant" and not (current_state and current_state.get_value("tenant1_age"))) else "owner1_"
            if current_state and current_state.get_value("owner1_name") and not current_state.get_value("owner1_age"):
                target_prefix = "owner1_"
            elif current_state and current_state.get_value("tenant1_name") and not current_state.get_value("tenant1_age"):
                target_prefix = "tenant1_"
            extracted[f"{target_prefix}age"] = val_age

        # 0.59. Relationship selection alone (e.g. user clicks "Father's Name" or "Husband's Name" chip)
        rel_only_m = re.match(r'^(?:(?:i\s+choose|use|select|my)\s+)?(father(?:\'?s)?(?:\s+name)?|husband(?:\'?s)?(?:\s+name)?)$', cleaned.strip(), re.I)
        if rel_only_m:
            chosen = rel_only_m.group(1).lower()
            target_prefix = "tenant1_" if user_role == "tenant" else "owner1_"
            extracted[f"{target_prefix}careof"] = "Husband Name" if "husband" in chosen else "Father Name"

        # 0.6. Standalone Father / Husband Name (e.g. "Father name is Suresh", "S/o Suresh", "Husband name is Ramesh", "Change father name to Suresh")
        careof_m = re.search(r'\b(?:change\s+|correct\s+|update\s+)?(father|husband|mother|wife|s/o|w/o|d/o|c/o)(?:\'?s)?(?:\s+name)?(?:\s+(?:is|to|:|=|was|\s))\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)', cleaned, re.I)
        if careof_m:
            rel_type_str = careof_m.group(1).lower()
            rel_name = careof_m.group(2).strip()
            # Ignore stop words like "is", "the", "a", "name"
            if rel_name.lower() not in ("is", "name", "the", "a", "an", "of", "to", "my", "our", "and", "father", "husband") and len(rel_name) > 1:
                target_prefix = "tenant1_" if user_role == "tenant" else "owner1_"
                extracted[f"{target_prefix}careofname"] = " ".join(w.capitalize() for w in rel_name.split())
                extracted[f"{target_prefix}careof"] = "Husband Name" if "husband" in rel_type_str or "w/o" in rel_type_str or "wife" in rel_type_str else "Father Name"

        # 0.7. Contextual Father/Husband input (if user just types the name after being asked)
        if current_state and not extracted.get("owner1_careofname") and not extracted.get("tenant1_careofname") and not rel_only_m:
            curr_role = getattr(current_state, "user_role", "owner").lower()
            prefix = "tenant1_" if curr_role == "tenant" else "owner1_"
            curr_val = current_state.get_value(f"{prefix}careofname")
            if current_state.get_value(f"{prefix}name") and (not curr_val or curr_val == "is"):
                direct_careof_m = re.match(r'^(?:(?:my\s+)?(?:father|husband)(?:\'?s)?\s+(?:name\s+)?(?:is\s+|to\s+)?|s/o\s+|w/o\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)$', cleaned.strip())
                if direct_careof_m:
                    cand = direct_careof_m.group(1).strip()
                    non_names_cf = {"Father", "Father Name", "Husband", "Husband Name", "Yes", "No", "Ok", "Sure", "Rent", "Deposit"}
                    if cand not in non_names_cf and len(cand) >= 2 and not re.search(r'\d', cand):
                        extracted[f"{prefix}careofname"] = " ".join(w.capitalize() for w in cand.split())
                        # If relationship was previously chosen, keep it; otherwise default to Father Name
                        existing_careof = current_state.get_value(f"{prefix}careof")
                        if not extracted.get(f"{prefix}careof"):
                            extracted[f"{prefix}careof"] = existing_careof or "Father Name"

        # 1. Rent Amount (e.g. "rent 55000", "55,000 per month", "rent is 35k", "35000/month", "35k rent", "40k rent", "rent is 40K", "for 55000 per month")
        rent_match = re.search(r'\b(?:change\s+|update\s+|set\s+)?(?:monthly\s*)?rent(?:al)?\s*(?:is|of|:|=|to)\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(k|thousand|lakh|l)?(?!\s*months?\b)', cleaned, re.I)
        if not rent_match or not rent_match.group(1):
            rent_match = re.search(r'(?:^|[,;.\s]|and\s+)(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(k|thousand|lakh|l)?\s*(?:per\s*month|/mo|pm)?\s*(?:rs\.?|inr|₹)?\s*rent\b', cleaned, re.I)
        if not rent_match or not rent_match.group(1):
            rent_match = re.search(r'\b(?:change\s+|update\s+|set\s+)?(?:monthly\s*)?rent(?:al)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(k|thousand|lakh|l)?(?!\s*(?:months?|deposit|depost|deposite|advance)\b)', cleaned, re.I)
        if not rent_match or not rent_match.group(1):
            rent_match = re.search(r'\b(?:rs\.?|inr|₹)\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(k|thousand|lakh|l)?\s*(?:per\s*month|/mo|pm|a\s*month)\b', cleaned, re.I)
        if not rent_match or not rent_match.group(1):
            rent_match = re.search(r'\bfor\s+(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(k|thousand|lakh|l)?\s*(?:per\s*month|/mo|pm|a\s*month)?\b', cleaned, re.I)
        
        if rent_match and rent_match.group(1):
            num_str = rent_match.group(1).replace(",", "")
            multiplier = rent_match.group(2) or ""
            try:
                val = float(num_str)
                if multiplier.lower() in ("k", "thousand"):
                    val *= 1000
                elif multiplier.lower() in ("l", "lakh"):
                    val *= 100000
                extracted["monthly_rent"] = str(int(val))
            except ValueError:
                pass

        # 2. Security Deposit (e.g. "deposit 3 lakh", "deposit is 1.5L", "deposit of 2,00,000", "1.5 lakh deposit", "80k depost", "deposit is 80K", "advance 50000")
        dep_match = re.search(r'\b(?:security\s*)?(?:deposit|depost|deposite|advance)\s*(?:is|of|:|=)\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(lakh|l|k|thousand)?(?!\s*(?:st|nd|rd|th|months?\b))', cleaned, re.I)
        if not dep_match or not dep_match.group(1):
            dep_match = re.search(r'(?:^|[,;.\s]|and\s+)(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(lakh|l|k|thousand)?\s*(?:rs\.?|inr|₹)?\s*(?:security\s*)?(?:deposit|depost|deposite|advance)\b', cleaned, re.I)
        if not dep_match or not dep_match.group(1):
            dep_match = re.search(r'\b(?:security\s*)?(?:deposit|depost|deposite|advance)\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(lakh|l|k|thousand)?(?!\s*(?:st|nd|rd|th|months?\b))', cleaned, re.I)

        if dep_match and dep_match.group(1):
            num_str = dep_match.group(1).replace(",", "")
            unit_str = dep_match.group(2) or ""
            try:
                val = float(num_str)
                unit_lower = unit_str.lower()
                if unit_lower in ("l", "lakh"):
                    val *= 100000
                elif unit_lower in ("k", "thousand"):
                    val *= 1000
                extracted["security_deposit"] = str(int(val))
            except ValueError:
                pass

        # 2.5 Standalone numeric amount (e.g. "25000", "₹25,000", "25k", "25 thousand", "1.5L", "2 lakh", "Rs. 25000", "₹50,000 (2× Rent)")
        if not extracted.get("monthly_rent") and not extracted.get("security_deposit"):
            standalone_amount_m = re.search(
                r'^(?:(?:it\s+is|it\'s|its|around|approx|approximately|only|amount\s+is|rent\s+is|deposit\s+is)\s+)?(?:(?:rs\.?|inr|₹)\s*)?(\d+(?:\.\d+)?|\d+(?:,\d+)*)\s*(k|thousand|lakh|l)?(?:\s*(?:rs\.?|inr|₹|only|per\s*month|/mo|pm|\/-|\(.*?rent.*?\)))?$',
                cleaned.strip(),
                re.I
            )
            if standalone_amount_m and standalone_amount_m.group(1):
                num_str = standalone_amount_m.group(1).replace(",", "")
                unit_str = (standalone_amount_m.group(2) or "").lower()
                try:
                    val = float(num_str)
                    if unit_str in ("l", "lakh"):
                        val *= 100000
                    elif unit_str in ("k", "thousand"):
                        val *= 1000
                    parsed_amt = str(int(val))
                    
                    has_rent = current_state and bool(current_state.get_value("monthly_rent"))
                    has_deposit = current_state and bool(current_state.get_value("security_deposit"))
                    
                    if not has_rent:
                        extracted["monthly_rent"] = parsed_amt
                    elif not has_deposit:
                        extracted["security_deposit"] = parsed_amt
                    else:
                        extracted["monthly_rent"] = parsed_amt
                except ValueError:
                    pass

        # 3. Tenant Name (e.g. "to Aman Verma", "tenant is Rahul Sharma", "tenant Rahul", "to Rahul")
        has_tenant_name = current_state and bool(current_state.get_value("tenant1_name"))
        if not has_tenant_name or re.search(r'\b(?:change\s+|update\s+|set\s+)?tenant(?:\'s)?\s+name\b', cleaned, re.I):
            tenant_match = re.search(r'(?:to\s+(?:mr\.?\s*|ms\.?\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)*)|\btenant(?:\s+is|\s+name:?|\s*:)\s*(?:mr\.?\s*|ms\.?\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)*))', cleaned, re.I)
            if tenant_match:
                raw_t = (tenant_match.group(1) or tenant_match.group(2) or "").strip()
                # Strip trailing boundary words
                t_name = re.split(r'\b(?:for|with|from|at|on|in|having|deposit|depost|rent|starts?|will|pays?|shall|extra|maintenance|excluding|including)\b', raw_t, flags=re.I)[0].strip()
                non_t_names = {
                    "rent", "deposit", "depost", "agreement", "october", "september", "november", "december",
                    "january", "february", "march", "april", "may", "june", "july", "august", "bhk", "flat",
                    "villa", "pays", "pay", "will pay", "pays extra", "extra", "maintenance", "excluding", "including"
                }
                if t_name and len(t_name) > 2 and t_name.lower() not in non_t_names:
                    extracted["tenant1_name"] = t_name

        # 4. Owner Name (e.g. "owner is Naresh Agarwal", "owner Naresh Agarwal")
        has_owner_name = current_state and bool(current_state.get_value("owner1_name"))
        if not has_owner_name or re.search(r'\b(?:change\s+|update\s+|set\s+)?owner(?:\'s)?\s+name\b', cleaned, re.I):
            owner_match = re.search(r'\bowner(?:\s+is|\s+name:?|\s*:)\s*(?:mr\.?\s*|ms\.?\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)*)', cleaned, re.I)
            if owner_match:
                raw_o = owner_match.group(1).strip()
                o_name = re.split(r'\b(?:for|with|from|at|on|in|having|deposit|depost|rent|starts?|property|renting|and|pays?|shall|will|extra|maintenance)\b', raw_o, flags=re.I)[0].strip()
                if o_name and len(o_name) > 2 and o_name.lower() not in ("rent", "deposit", "depost", "agreement", "is", "bhk", "flat", "pays", "pay", "extra", "maintenance"):
                    extracted["owner1_name"] = o_name

        # 4.5. Standalone Direct Name (e.g. "Naresh", "naresh", "Naresh Agarwal", "My name is Naresh")
        direct_name_m = re.match(r'^(?:(?:my|the)\s+name\s+is\s+|i\s+am\s+|name:\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)*)$', cleaned.strip())
        if direct_name_m and not extracted.get("owner1_name") and not extracted.get("tenant1_name"):
            cand_name = direct_name_m.group(1).strip()
            non_names = {
                "yes", "no", "ok", "okay", "sure", "cancel", "done", "next", "hi", "hello", "hey",
                "rent", "deposit", "owner", "tenant", "draft", "preview", "generate", "start", "stop"
            }
            if cand_name.lower() not in non_names and len(cand_name) > 2 and not re.search(r'\d', cand_name):
                cand_name_formatted = " ".join(w.capitalize() for w in cand_name.split())
                if current_state:
                    user_role = getattr(current_state, "user_role", "owner").lower()
                    if user_role == "tenant" and not (current_state and current_state.get_value("tenant1_name")):
                        extracted["tenant1_name"] = cand_name_formatted
                    elif not (current_state and current_state.get_value("owner1_name")):
                        extracted["owner1_name"] = cand_name_formatted
                    elif not (current_state and current_state.get_value("tenant1_name")):
                        extracted["tenant1_name"] = cand_name_formatted

        # 5. Property Details / Flat / Society / City (ONLY if explicit property tokens exist)
        flat_match = re.search(r'(?:flat|unit|villa|apt|apartment)\s*(?:no\.?|#|num\.?|\s:?)\s*([A-Za-z]?[-/]?[0-9]+[A-Za-z0-9\-]*)', cleaned, re.I)
        if flat_match:
            candidate_flat = flat_match.group(1).strip()
            if candidate_flat.lower() not in ("is", "in", "at", "for", "near", "my", "the", "located", "and"):
                extracted["flat_no"] = candidate_flat

        # Common Indian cities
        city_match = re.search(r'\b(Bangalore|Bengaluru|Hyderabad|Secunderabad|Mumbai|Pune|Delhi|Gurgaon|Noida|Chennai|Kolkata)\b', cleaned, re.I)
        if city_match:
            extracted["city"] = city_match.group(1).capitalize()

        # Property address context
        prop_explicit_m = re.search(r'(?:rented\s+|rental\s+)?property(?:\s+address)?\s*(?::|\s+is|\s+at|\s+located\s+at)\s*(.+)', cleaned, re.I)
        if prop_explicit_m:
            raw_prop = prop_explicit_m.group(1).strip()
            prop_clean = re.split(r'(?:\n|\b(?:monthly\s+)?rent\s*(?::|is)\b|\bsecurity\s+deposit\s*(?::|is)\b|\bdeposit\s*(?::|is)\b|\bstart\s+date\s*(?::|is)\b)', raw_prop, flags=re.I)[0].strip(' ,.-')
            prop_clean = re.sub(r'^(?:address\s*:?\s*)', '', prop_clean, flags=re.I).strip(' ,.-')
            if prop_clean and len(prop_clean) > 3:
                extracted["property_address"] = prop_clean
        elif re.search(r'\b(?:my\s+)?(?:flat|apartment|house|property|villa|unit)\s+is\s+in\s+', cleaned, re.I):
            in_m = re.search(r'\b(?:my\s+)?(?:flat|apartment|house|property|villa|unit)\s+is\s+in\s+(.+)', cleaned, re.I)
            if in_m:
                cand = in_m.group(1).strip()
                cand = re.split(r'\b(?:rent\s+is|deposit\s+is|start\s+date|starts)\b', cand, flags=re.I)[0].strip(' ,.-')
                if cand and len(cand) > 3:
                    extracted["property_address"] = cand
        elif "renting" in cleaned.lower():
            renting_part = cleaned.split("renting", 1)[-1]
            prop_candidate = re.split(r'\b(?:to\s+[A-Z][a-z]+|for\s+\d+|from\s+\d+|with\s+deposit)\b', renting_part, flags=re.I)[0]
            prop_clean = re.sub(r'^(?:(?:my|the)\s+)?(?:\d+BHK\s+)?(?:flat|apartment|house|property|villa|unit|home)\s*(?:no\.?|#|[0-9]+[A-Za-z0-9\-]*)?\s*(?:at|in|located\s+at|located\s+in)?\s*', '', prop_candidate.strip(), flags=re.I).strip(' ,.-')
            if prop_clean and len(prop_clean) > 3:
                extracted["property_address"] = prop_clean
        elif re.search(r'^(?:(?:flat|apartment|unit|villa|house)\s+[A-Za-z0-9\-]+\s*(?:at|in|,)\s*)?([A-Za-z0-9\s]+(?:colony|nagar|society|towers|heights|city|apartments|villas|road|layout|enclave|greens|acres|gardens|view)[A-Za-z0-9\s,]*)', cleaned, re.I):
            front_m = re.search(r'^(?:(?:flat|apartment|unit|villa|house)\s+[A-Za-z0-9\-]+\s*(?:at|in|,)\s*)?([A-Za-z0-9\s]+(?:colony|nagar|society|towers|heights|city|apartments|villas|road|layout|enclave|greens|acres|gardens|view)[A-Za-z0-9\s,]*)', cleaned, re.I)
            if front_m:
                cand = front_m.group(1).strip()
                cand = re.split(r'\b(?:rent|deposit|depost|start|starts|from|for|to)\b', cand, flags=re.I)[0].strip(' ,.-')
                if cand and len(cand) > 3:
                    extracted["property_address"] = cand
        elif not re.search(r'\b(?:profile|mobile|email|occupation)\b', cleaned, re.I) and (cleaned.count(",") >= 2 or re.search(r'\b(road|street|nagar|colony|layout|society|enclave|towers|heights|apartments|villas|kondapur|gachibowli|hitech|madhapur|miyapur|whitefield|indiranagar|koramangala|bellandur|telangana|karnataka|maharashtra|india)\b', cleaned, re.I)):
            cand = cleaned.strip()
            cand = re.split(r'\b(?:rent\s+is|deposit\s+is|start\s+date|starts)\b', cand, flags=re.I)[0].strip(' ,.-')
            if len(cand) > 10 and not cand.lower().startswith(("rent", "deposit", "agreement", "i am", "my name is", "owner is", "tenant is", "owner profile", "tenant profile")):
                extracted["property_address"] = cand
        
        if not extracted.get("property_address") and ("flat_no" in extracted or "city" in extracted):
            parts = []
            if "flat_no" in extracted: parts.append(f"Flat {extracted['flat_no']}")
            if "city" in extracted: parts.append(extracted["city"])
            if parts:
                extracted["property_address"] = ", ".join(parts)

        # 6. Start Date (e.g. "October 1st", "1st Sept", "01-10-2026", "September 1", "from Oct 1", "starts October 1st")
        date_match = re.search(
            r'(?:starts?(?:\s+from|\s+on|\s*:)?|from\s+)?\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+[0-9]{4})?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+[0-9]{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*[0-9]{4})?|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})',
            cleaned,
            re.I
        )
        if date_match:
            raw_date = (date_match.group(1) or "").strip()
            parsed_dt = InterviewEngine._parse_flexible_date(raw_date)
            if not parsed_dt:
                # Try parsing date strings like "October 1st" with current/next year
                try:
                    cleaned_date = re.sub(r'(st|nd|rd|th)', '', raw_date, flags=re.I).strip()
                    for fmt in ("%B %d", "%b %d", "%d %B", "%d %b", "%B %d %Y", "%d %B %Y"):
                        try:
                            dt = datetime.strptime(cleaned_date, fmt)
                            year = dt.year if dt.year > 1900 else datetime.now().year
                            if year <= 1900:
                                year = datetime.now().year
                                if dt.month < datetime.now().month:
                                    year += 1
                            parsed_dt = datetime(year, dt.month, dt.day)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
            if parsed_dt:
                extracted["agreement_start_date"] = parsed_dt.strftime("%d-%m-%Y")

        # 7. Tenure (e.g. "11 months", "12 months", "1 year", "5 months")
        # NEVER match when message is about notice period or lock-in period!
        if not re.search(r'\b(?:notice|lock[\-\s]*in)\b', cleaned, re.I):
            tenure_match = re.search(r'^(?:duration|tenure|period|term|for)?\s*(\d+)\s*months?$', cleaned.strip(), re.I)
            if not tenure_match:
                tenure_match = re.search(r'\b(\d+)\s*months?\s*(?:duration|tenure|period|term|stay)?\b(?!\s*(?:notice|lock))', cleaned, re.I)
            if tenure_match:
                extracted["tenure_months"] = tenure_match.group(1)

        # 8. Maintenance responsibility (e.g. "Aman will pay electricity and maintenance", "tenant pays maintenance", "including maintenance", "extra", "excluding")
        if re.search(r'(?:tenant|licensee|aman|rahul)\s+(?:will\s+)?pay\s+(?:electricity\s+and\s+)?maintenance|maintenance\s+(?:is\s+)?extra|excluding\s+maintenance|\bexcluding\b|\bextra\b|tenant\s+pays\s+extra|owner\s+pays', cleaned, re.I):
            extracted["maintenance"] = "Excluding"
        elif re.search(r'maintenance\s+(?:is\s+)?included|including\s+maintenance|\bincluding\b|\bincluded\b|included\s+in\s+rent', cleaned, re.I):
            extracted["maintenance"] = "Including"

        # 8.1. Rent Increase Type & Value (e.g. "% of rent", "fixed increase", "5%", "5-10%", "10%", "₹1,000", "1500")
        is_date_msg = bool(re.search(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b(?:start|begin|from|today|date)\b', cleaned, re.I))
        if not is_date_msg:
            if re.search(r'(?:%\s*of\s*rent|percentage|percent\s*of\s*rent|\bpercentage\b|\bpercent\b)', cleaned, re.I):
                extracted["rent_increase_type"] = "% of Rent"
            elif re.search(r'(?:fixed\s*increase|fixed\s*amount|\bfixed\b)', cleaned, re.I) and not re.search(r'\d+\s*%', cleaned):
                extracted["rent_increase_type"] = "Fixed Increase"

            # Strict percentage increase pattern (requires explicit % or percent symbol)
            pct_m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*-\s*(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*percent|(\d+(?:\.\d+)?)\s*(?:%|percent)\s*(?:increase|escalation|hike|per\s+annum)?', cleaned, re.I)
            if pct_m:
                if pct_m.group(1) and pct_m.group(2):
                    extracted["increase_percent"] = f"{pct_m.group(1)}-{pct_m.group(2)}%"
                elif pct_m.group(3) and pct_m.group(4):
                    extracted["increase_percent"] = f"{pct_m.group(3)}-{pct_m.group(4)}%"
                elif pct_m.group(5) and pct_m.group(6):
                    extracted["increase_percent"] = f"{pct_m.group(5)}-{pct_m.group(6)}%"
                elif pct_m.group(7):
                    extracted["increase_percent"] = f"{pct_m.group(7)}%"
                if not extracted.get("rent_increase_type"):
                    extracted["rent_increase_type"] = "% of Rent"
            elif re.search(r'(?:₹|rs\.?|inr)\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})|\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:fixed|fixed\s+increase|rupees)\b', cleaned, re.I):
                fx_m = re.search(r'(?:₹|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})', cleaned, re.I)
                if fx_m:
                    num_str = fx_m.group(1).replace(",", "")
                    if int(num_str) >= 100:  # Avoid single digit numbers like age or tenure
                        extracted["increase_percent"] = f"₹{int(num_str):,}"
                        if not extracted.get("rent_increase_type"):
                            extracted["rent_increase_type"] = "Fixed Increase"

        # 9. Lock-in Period (e.g. "no lock-in", "6 months lock-in", "full 11 months", "3 months lock-in")
        if re.search(r'\b(?:no\s+lock[\-\s]*in|zero\s+lock[\-\s]*in|without\s+lock[\-\s]*in|no\s+minimum\s+stay|exit\s+anytime)\b', cleaned, re.I):
            extracted["lockin"] = "N"
            extracted["lockin_months"] = "0"
        else:
            lock_match = re.search(r'(\d+)\s*[- ]?months?\s*lock[\-\s]*in|lock[\-\s]*in(?:\s+period)?(?:\s+of)?\s*(\d+)\s*months?|full\s+(\d+)\s*months?', cleaned, re.I)
            if lock_match:
                months = lock_match.group(1) or lock_match.group(2) or lock_match.group(3)
                extracted["lockin_months"] = months
                extracted["lockin"] = "Y" if int(months) > 0 else "N"
                extracted["penalty_deduction"] = "30"  # standard 30 days default

        # 10. Notice Period (e.g. "1 month notice", "2 months notice")
        notice_match = re.search(r'(\d+)\s*months?\s*notice', cleaned, re.I)
        if notice_match:
            n_months = int(notice_match.group(1))
            extracted["notice_period"] = "1 Month" if n_months == 1 else f"{n_months} Months"

        # 11. Dual Party Profile Parsing (e.g. "Owner profile: PRIVATE EMPLOYEE, mobile 9876543210, email owner@test.com. Tenant profile: BUSINESS, mobile 9876543211, email tenant@test.com")
        occ_patterns = [
            (r'\b(?:private\s+(?:employee|sector|job)|pvt\s+emp|software\s+eng(?:ineer)?|it\s+(?:professional|employee)|corporate)\b', "PRIVATE EMPLOYEE"),
            (r'\b(?:government\s+employee|govt\s+emp|civil\s+servant|public\s+sector)\b', "GOVERNMENT EMPLOYEE"),
            (r'\b(?:retired\s+government\s+employee|retired\s+govt\s+emp)\b', "RETIRED GOVERNMENT EMPLOYEE"),
            (r'\b(?:retired|senior\s+citizen|pensioner)\b', "RETIRED"),
            (r'\b(?:business|businessman|businesswoman|trader|merchant|shopkeeper)\b', "BUSINESS"),
            (r'\b(?:professional|doctor|advocate|lawyer|chartered\s+accountant|ca|consultant|architect)\b', "PROFESSIONAL"),
            (r'\b(?:self[\-\s]*employed|freelancer|contractor)\b', "SELF EMPLOYED"),
            (r'\b(?:housewife|homemaker)\b', "HOUSEWIFE"),
        ]

        owner_segment = ""
        tenant_segment = ""
        if re.search(r'\bowner(?:\'s)?\s+profile\b', cleaned, re.I) and re.search(r'\btenant(?:\'s)?\s+profile\b', cleaned, re.I):
            parts_split = re.split(r'\btenant(?:\'s)?\s+profile[:\s]*', cleaned, flags=re.I)
            if len(parts_split) == 2:
                owner_segment = parts_split[0]
                tenant_segment = parts_split[1]

        if owner_segment and tenant_segment:
            ph_o = re.search(r'(?:\+?91[\-\s]?)?([6-9]\d{9})\b', owner_segment)
            if ph_o:
                extracted["owner1_phone"] = ph_o.group(1)
            em_o = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})\b', owner_segment)
            if em_o:
                extracted["owner1_email"] = em_o.group(1).lower()
            for pat, standard_occ in occ_patterns:
                if re.search(pat, owner_segment, re.I):
                    extracted["owner1_occupation"] = standard_occ
                    break

            ph_t = re.search(r'(?:\+?91[\-\s]?)?([6-9]\d{9})\b', tenant_segment)
            if ph_t:
                extracted["tenant1_phone"] = ph_t.group(1)
            em_t = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})\b', tenant_segment)
            if em_t:
                extracted["tenant1_email"] = em_t.group(1).lower()
            for pat, standard_occ in occ_patterns:
                if re.search(pat, tenant_segment, re.I):
                    extracted["tenant1_occupation"] = standard_occ
                    break
            return extracted
        else:
            # Check for single party profile format
            is_single_profile = bool(re.match(r'^(?:owner|tenant)\s+profile:\s*', cleaned, re.I))
            if is_single_profile:
                target_p = "tenant1_" if re.match(r'^tenant\s+profile:', cleaned, re.I) else "owner1_"
                ph = re.search(r'(?:\+?91[\-\s]?)?([6-9]\d{9})\b', cleaned)
                if ph:
                    extracted[f"{target_p}phone"] = ph.group(1)
                em = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})\b', cleaned)
                if em:
                    extracted[f"{target_p}email"] = em.group(1).lower()
                for pat, standard_occ in occ_patterns:
                    if re.search(pat, cleaned, re.I):
                        extracted[f"{target_p}occupation"] = standard_occ
                        break
                return extracted

            # 11. Phone Number (10-digit Indian Mobile e.g. 9876543210, +91-9876543210)
            phone_match = re.search(r'(?:\+?91[\-\s]?)?([6-9]\d{9})\b', cleaned)
            if phone_match:
                phone_val = phone_match.group(1)
                is_tenant_phase = bool(current_state and current_state.get_value("owner1_address") and not current_state.get_value("tenant1_phone") and current_state.get_value("tenant1_name"))
                if user_role == "tenant" or is_tenant_phase:
                    extracted["tenant1_phone"] = phone_val
                else:
                    extracted["owner1_phone"] = phone_val

            # 12. Email Address (e.g. naresh@example.com)
            email_match = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})\b', cleaned)
            if email_match:
                email_val = email_match.group(1).lower()
                is_tenant_phase = bool(current_state and current_state.get_value("owner1_address") and not current_state.get_value("tenant1_email") and current_state.get_value("tenant1_name"))
                if user_role == "tenant" or is_tenant_phase:
                    extracted["tenant1_email"] = email_val
                else:
                    extracted["owner1_email"] = email_val

            # 13. Occupation (Standard Indian Registration Categories)
            for pat, standard_occ in occ_patterns:
                if re.search(pat, cleaned, re.I):
                    is_tenant_phase = bool(current_state and current_state.get_value("owner1_address") and not current_state.get_value("tenant1_occupation") and current_state.get_value("tenant1_name"))
                    if user_role == "tenant" or is_tenant_phase:
                        extracted["tenant1_occupation"] = standard_occ
                    else:
                        extracted["owner1_occupation"] = standard_occ
                    break

        # Safeguard: Prevent accidental overwrite of confirmed monthly_rent by deposit or duration inputs
        if current_state and current_state.get_value("monthly_rent") and not re.search(r'\b(?:change\s+|update\s+|set\s+)?(?:monthly\s+)?rent(al)?\b', cleaned, re.I):
            if "monthly_rent" in extracted:
                if not current_state.get_value("security_deposit") and "security_deposit" not in extracted:
                    extracted["security_deposit"] = extracted["monthly_rent"]
                del extracted["monthly_rent"]

        return extracted

    def extract_aadhaar_ocr(self, document_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Extract structured party details from an Aadhaar image or a multi-page PDF."""
        # 1. Fast Offline Digital PDF Extraction (Zero API cost, instant execution)
        if mime_type == "application/pdf":
            try:
                import fitz
                pdf_doc = fitz.open(stream=document_bytes, filetype="pdf")
                raw_text = "\n".join([page.get_text() for page in pdf_doc])
                pdf_doc.close()

                if raw_text and len(raw_text.strip()) >= 50:
                    digital_extracted = self._parse_digital_aadhaar_text(raw_text)
                    if digital_extracted.get("full_name"):
                        logger.info("Aadhaar details successfully extracted via offline digital PDF parser.")
                        return digital_extracted
            except Exception as pdf_err:
                logger.warning(f"Offline PDF extraction failed, falling back to vision: {pdf_err}")

        # 2. Vision OCR via Gemini Multimodal Models
        if self.provider != "gemini" or not self.gemini_key:
            raise AadhaarOcrError("Aadhaar OCR is not configured. Set AI_PROVIDER=gemini and GEMINI_API_KEY.")

        try:
            from google import genai
            from google.genai import types

            document_parts = []
            if mime_type == "application/pdf":
                import fitz  # PyMuPDF
                pdf = fitz.open(stream=document_bytes, filetype="pdf")
                try:
                    for page in list(pdf)[:2]:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        document_parts.append(types.Part.from_bytes(data=pix.tobytes("png"), mime_type="image/png"))
                finally:
                    pdf.close()
            else:
                document_parts.append(types.Part.from_bytes(data=document_bytes, mime_type=mime_type))

            if not document_parts:
                raise AadhaarOcrError("The uploaded document does not contain readable pages.")

            prompt = """
Extract the visible details from this Indian Aadhaar document. Return only a JSON object with these keys:
full_name, relation_type, relation_name, date_of_birth, gender, aadhaar_masked, address_line1, locality, city, state, pincode.
Use relation_type only as S/O, W/O, D/O, C/O, or an empty string. Convert date_of_birth to YYYY-MM-DD when visible.
Never invent values. Use an empty string for a value that is absent or unclear. Always mask the Aadhaar number as XXXX-XXXX-last4.
"""
            model_candidates = [
                "gemini-2.5-flash",
                "gemini-3.6-flash",
                "gemini-2.5-flash-preview",
            ]

            client = genai.Client(api_key=self.gemini_key)
            response = None
            last_err = None

            for model_name in model_candidates:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[*document_parts, prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json"),
                    )
                    if response and response.text:
                        break
                except Exception as m_err:
                    last_err = m_err
                    err_str = str(m_err)
                    logger.warning(f"Aadhaar OCR notice with {model_name}: {m_err}")
                    # On rate limit, wait briefly before trying next model
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        import time as _time
                        retry_match = re.search(r'retry in (\d+)', err_str, re.I)
                        wait_secs = min(int(retry_match.group(1)), 15) if retry_match else 5
                        logger.info(f"Rate limited on {model_name}, waiting {wait_secs}s before next model...")
                        _time.sleep(wait_secs)
                    continue

            if not response or not response.text:
                if last_err and ("429" in str(last_err) or "RESOURCE_EXHAUSTED" in str(last_err)):
                    raise AadhaarOcrError("Gemini OCR quota limit reached. Please upload an official e-Aadhaar PDF or type details directly.")
                if last_err and ("503" in str(last_err) or "UNAVAILABLE" in str(last_err)):
                    raise AadhaarOcrError("Google Gemini Vision service is currently experiencing a temporary server spike. Please re-upload or upload a digital PDF.")
                raise AadhaarOcrError(f"Could not extract Aadhaar fields: {last_err}")

            extracted = json.loads((response.text or "").strip())
            if not isinstance(extracted, dict) or not extracted.get("full_name"):
                raise AadhaarOcrError("Gemini could not read a name from this Aadhaar document. Please upload a clearer image.")

            # 1. Compute Age from date_of_birth if present
            dob = extracted.get("date_of_birth", "")
            if dob:
                dob_match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})|(\d{1,2})[-/](\d{1,2})[-/](\d{4})', dob)
                if dob_match:
                    birth_year = int(dob_match.group(1) or dob_match.group(6))
                    current_year = datetime.now().year
                    if 1900 < birth_year < current_year:
                        extracted["age"] = str(current_year - birth_year)

            # 2. Normalize Care of Relation
            rel_type = (extracted.get("relation_type") or "").upper()
            if "W/O" in rel_type or "WIFE" in rel_type or "HUSBAND" in rel_type:
                extracted["careof"] = "Husband Name"
            else:
                extracted["careof"] = "Father Name"

            # 2b. Derive name prefix (Mr./Ms.) from gender and relation_type
            gender_raw = (extracted.get("gender") or "").upper().strip()
            if gender_raw in ("MALE", "M") or "S/O" in rel_type:
                extracted["prefix"] = "Mr."
            elif gender_raw in ("FEMALE", "F") or "D/O" in rel_type or "W/O" in rel_type:
                extracted["prefix"] = "Ms."
            # Father or husband in care-of is always male
            extracted["careofname_prefix"] = "Mr."

            # 3. Assemble complete postal address
            addr_parts = []
            for k in ("address_line1", "locality", "city", "state", "pincode"):
                val = extracted.get(k)
                if val and str(val).strip():
                    addr_parts.append(str(val).strip())
            if addr_parts:
                extracted["full_address"] = ", ".join(addr_parts)

            return extracted
        except AadhaarOcrError:
            raise
        except Exception as error:
            logger.exception("Gemini Aadhaar OCR failed")
            raise AadhaarOcrError(f"Gemini could not process this Aadhaar document: {error}") from error

    def _parse_digital_aadhaar_text(self, raw_text: str) -> dict:
        """Parse structured Aadhaar attributes directly from digital PDF text stream."""
        extracted = {}

        # 1. Full Legal Name
        name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\n\s*(?:S/O|W/O|D/O|C/O|DOB|Date of Birth|\n\s*DOB)', raw_text)
        if not name_match:
            name_match = re.search(r'To\s*\n+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', raw_text, re.I)
        if name_match:
            extracted["full_name"] = name_match.group(1).strip()

        # 2. DOB / Age
        dob_match = re.search(r'\b(?:DOB|Date of Birth)\s*:?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})', raw_text, re.I)
        if dob_match:
            dob_str = dob_match.group(1).strip()
            extracted["date_of_birth"] = dob_str
            try:
                birth_year = int(dob_str.split('/')[-1].split('-')[-1])
                curr_year = datetime.now().year
                if 1900 < birth_year < curr_year:
                    extracted["age"] = str(curr_year - birth_year)
            except Exception:
                pass

        # 3. Care of (Father / Husband)
        careof_match = re.search(r'\b(S/O|W/O|D/O|C/O)\s*:?\s*([A-Za-z]+(?:\s+[A-Za-z]+)+)', raw_text, re.I)
        if careof_match:
            rel_type = careof_match.group(1).upper()
            rel_name = careof_match.group(2).split('\n')[0].split(',')[0].strip()
            extracted["relation_type"] = rel_type
            extracted["relation_name"] = rel_name
            extracted["careof"] = "Husband Name" if "W/O" in rel_type else "Father Name"

        # 4. Full Address & Pincode
        addr_match = re.search(r'Address\s*:\s*([\s\S]+?)(?=\b\d{4}\s+\d{4}\s+\d{4}\b|VID\s*:|\n\s*\n\s*\d|\Z)', raw_text, re.I)
        if addr_match:
            raw_addr = addr_match.group(1).strip()
            clean_addr = " ".join(raw_addr.split())
            clean_addr = re.sub(r'^(?:S/O|W/O|D/O|C/O)\s*:?\s*[^,]+,\s*', '', clean_addr, flags=re.I)
            extracted["full_address"] = clean_addr

            pin_match = re.search(r'\b(\d{6})\b', clean_addr)
            if pin_match:
                extracted["pincode"] = pin_match.group(1)

        # 5. Masked Aadhaar
        aadhaar_match = re.search(r'\b(\d{4}\s+\d{4}\s+\d{4})\b', raw_text)
        if aadhaar_match:
            last4 = aadhaar_match.group(1).replace(" ", "")[-4:]
            extracted["aadhaar_masked"] = f"XXXX-XXXX-{last4}"

        # 6. Derive name prefix (Mr./Ms.) from gender text or relation_type
        gender_match = re.search(r'\b(MALE|FEMALE)\b', raw_text, re.I)
        gender_raw = (gender_match.group(1).upper() if gender_match else "")
        rel_type_raw = (extracted.get("relation_type") or "").upper()
        if gender_raw == "MALE" or "S/O" in rel_type_raw:
            extracted["prefix"] = "Mr."
        elif gender_raw == "FEMALE" or "D/O" in rel_type_raw or "W/O" in rel_type_raw:
            extracted["prefix"] = "Ms."
        extracted["careofname_prefix"] = "Mr."

        return extracted

    def _mock_agreement_draft(self, prompt: str, state_code: str, agr_type: str) -> dict:
        title = "LEAVE AND LICENSE AGREEMENT" if agr_type == "leave_license" else "SIMPLE RENTAL AGREEMENT"
        
        render_data = {
            "agreement_type": agr_type,
            "monthly_rent": "25000",
            "monthly_rent_words": "Twenty Five Thousand",
            "security_deposit": "150000",
            "security_deposit_words": "One Lakh Fifty Thousand",
            "property_address": "FLAT NO 302, GREEN ACRES APARTMENT, INDIRANAGAR, BENGALURU",
            "today_date": "24th day of July 2026",
            "agreement_start_date": "1st day of August 2026",
            "agreement_end_date": "30th day of June 2027",
            "owner1_name": "Standard Property Owner",
            "owner1_age": "45",
            "owner1_careof": "S",
            "owner1_careofname": "Late Ramaswamy",
            "owner1_occupation": "Business",
            "owner1_address": "INDIRANAGAR, BENGALURU",
            "tenant1_name": "Rahul Ramesh Sharma",
            "tenant1_age": "32",
            "tenant1_careof": "S",
            "tenant1_careofname": "Suresh Sharma",
            "tenant1_occupation": "Software Engineer",
            "tenant1_address": "BENGALURU, KARNATAKA",
            "lockin_months": "6",
            "notice_period": "1 Month",
            "increase_percent": "5"
        }
        
        full_html = generate_preview_html(render_data)
        
        return {
            "title": title,
            "agreement_type": agr_type,
            "state_code": state_code,
            "city": "Bengaluru",
            "monthly_rent": 25000,
            "security_deposit": 150000,
            "escalation_percentage": 5.0,
            "tenure_months": 11,
            "compliance_score": 99.8,
            "clauses": [
                "GRANT OF LICENCE / TENANCY: 11 months tenure",
                "PAYMENT OF RENT / LICENSE FEES: Payable on or before 5th of each month",
                "SECURITY DEPOSIT: Refundable interest-free deposit",
                "MAINTENANCE & UTILITIES: Payable directly to authorities"
            ],
            "full_text": full_html
        }

    def _mock_aadhaar_ocr(self) -> dict:
        return {
            "full_name": "Rahul Ramesh Sharma",
            "relation_type": "S/O",
            "relation_name": "Suresh Sharma",
            "date_of_birth": "1992-08-15",
            "gender": "Male",
            "aadhaar_masked": "XXXX-XXXX-8912",
            "address_line1": "Flat 302, Green Acres Apartment",
            "locality": "10th Main, HSR Layout Sector 1",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560102",
            "is_ocr_verified": False
        }

ai_service = AIService()
