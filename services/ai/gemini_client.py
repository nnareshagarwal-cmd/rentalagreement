"""
services/ai/gemini_client.py — Google Gemini Multimodal Client & Conversation Engine
====================================================================================
Interfaces with Gemini Flash / Pro models for conversational natural language understanding,
clause modification, legal copilot assistance, and fallback entity extraction.
"""

import os
import json
import logging
import re
from config import Config
from services.agreement_state import AgreementState, FieldEntry, FieldStatus, ProvenanceSource
from services.interview_engine import InterviewEngine
from services.places_service import places_service
from services.ai.entity_extractor import EntityExtractor
from clauses.agreement_renderer import generate_preview_html

logger = logging.getLogger("AgreementAI_GeminiClient")


class GeminiClient:
    """Client for Google Gemini generative AI models and conversation copilot."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.gemini_key = Config.GEMINI_API_KEY

    def review_and_modify_agreement(self, agreement_html: str, user_prompt: str, agreement_type: str = "simple_rental") -> dict:
        """AI Legal Copilot — answers legal questions and modifies agreement clauses."""
        api_key = self.gemini_key or os.getenv("GEMINI_API_KEY", "")

        if self.provider == "gemini" and api_key:
            try:
                from google import genai
                from google.genai import types

                agreement_label = "Leave & License" if "leave" in agreement_type else "Simple Rental"

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
- If the edit does not map to any form field (e.g. adding a completely new clause), use an empty object for field_updates.
- Give practical, actionable legal advice — not generic textbook answers."""

                client = genai.Client(api_key=api_key)
                model_name = getattr(Config, "GEMINI_MODEL", "gemini-2.5-flash")
                copilot_models = [model_name, "gemini-3.6-flash", "gemini-2.5-flash-preview"]
                response = None
                for m_name in copilot_models:
                    try:
                        response = client.models.generate_content(
                            model=m_name,
                            contents=user_prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                temperature=0.2,
                                response_mime_type="application/json",
                            ),
                        )
                        if response and response.text:
                            break
                    except Exception as m_err:
                        logger.warning(f"Copilot notice with {m_name}: {m_err}")
                        continue

                if response and response.text:
                    parsed = self._safe_parse_json(response.text)
                    if parsed.get("action") == "modify" and not parsed.get("field_updates"):
                        find_txt = parsed.get("find", "")
                        replace_txt = parsed.get("replace", "")
                        detected = EntityExtractor.detect_field_updates(find_txt, replace_txt)
                        if detected:
                            parsed["field_updates"] = detected
                    return parsed

            except Exception as e:
                logger.exception("Gemini copilot review failed")
                return {
                    "action": "answer",
                    "response": f"⚠️ Copilot encountered an error: {str(e)}"
                }

        # Offline / fallback response
        prompt_lower = user_prompt.lower()
        if "lock" in prompt_lower and "period" in prompt_lower:
            return {
                "action": "answer",
                "response": "🔒 **Lock-in Period:** A lock-in period prevents either party from terminating the agreement for a minimum duration. If terminated early, the defaulting party typically forfeits a specified penalty amount."
            }
        elif "notice" in prompt_lower:
            return {
                "action": "answer",
                "response": "⏳ **Notice Period:** The standard notice period is **1 Month** (or 30 days) written notice before terminating the tenancy."
            }
        elif "deposit" in prompt_lower:
            return {
                "action": "answer",
                "response": "💎 **Security Deposit:** An interest-free refundable deposit paid by the tenant to the owner, refundable within 2 weeks after tenancy expiry subject to adjustments."
            }

        return {
            "action": "answer",
            "response": "📋 I wasn't able to connect to the AI service right now. Please check your Gemini API key and try again."
        }

    def _safe_parse_json(self, raw_text: str) -> dict:
        """Robustly parse JSON responses from LLM, handling markdown blocks, extra text, and unescaped newlines."""
        if not raw_text:
            return {}
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        try:
            return json.loads(cleaned, strict=False)
        except Exception:
            pass

        try:
            decoder = json.JSONDecoder(strict=False)
            res, _ = decoder.raw_decode(cleaned)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

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
        1. Analyzes user natural language text.
        2. Extracts multiple entities in one pass via offline rule extractor and Gemini fallback.
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

        # 1. High-speed Offline Rule Extractor
        rule_extracted = EntityExtractor.extract_entities_rule_based(user_message, current_state)
        if rule_extracted:
            for k, v in rule_extracted.items():
                extracted_dict[k] = v
                confidences[k] = 0.95

        # 2. LLM fallback for unstructured freeform paragraphs
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

        # Safeguard: Do not overwrite confirmed owner or tenant names
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

        # Safeguard: Prevent accidental overwrite of confirmed monthly_rent by deposit
        if current_state and current_state.get_value("monthly_rent"):
            if not re.search(r'\b(?:change\s+|update\s+|set\s+)?(?:monthly\s+)?rent(al)?\b', user_message, re.I):
                if "monthly_rent" in extracted_dict:
                    if not current_state.get_value("security_deposit") and "security_deposit" not in extracted_dict:
                        extracted_dict["security_deposit"] = extracted_dict["monthly_rent"]
                        confidences["security_deposit"] = confidences.get("monthly_rent", 0.9)
                    del extracted_dict["monthly_rent"]
                    if "monthly_rent" in confidences:
                        del confidences["monthly_rent"]

        # Safeguard: Never allow notice period or lock-in inputs to set tenure_months
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

        # 3. Update AgreementState with extracted fields
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

        # 3.5. Google Places Resolution
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

        # Ensure PIN code is included in property_address
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

        # 4. Apply deterministic auto-calculations
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

                visible_summary_items = [
                    f"• **{labels_map.get(k, k.replace('_', ' ').title())}:** {current_state.get_value(k)}"
                    for k in newly_extracted_keys
                    if k not in ("lockin", "penalty_deduction", "monthly_rent_words", "security_deposit_words")
                ]
                if visible_summary_items:
                    parts.append(f"✨ **Got it! I've captured {category_label}:**\n" + "\n".join(visible_summary_items))

            for name_k in ("owner1_name", "tenant1_name"):
                if name_k in newly_extracted_keys:
                    name_val = str(current_state.get_value(name_k) or "").strip()
                    if " " not in name_val and len(name_val) > 1:
                        parts.append(f"💡 *(If you have a surname / last name like **{name_val} Agarwal**, you can tell me anytime).*")

        question_text = next_interaction.get("question_text", "")
        if question_text:
            if parts:
                parts.append("\n---\n" + question_text)
            else:
                parts.append(question_text)

        return "\n\n".join(parts)

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
