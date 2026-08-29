"""
services/ai/entity_extractor.py — Offline Rule-Based Entity & Field Extractor
=============================================================================
High-precision regex/rule-based extractor for Indian rental agreement expressions.
Extracts financial details, tenure, dates, parties, contact info, lock-in terms,
and detects field diffs without requiring external LLM API calls.
"""

import re
from datetime import datetime
from services.agreement_state import AgreementState
from services.interview_engine import InterviewEngine


class EntityExtractor:
    """High-precision deterministic extractor for conversational Indian rental inputs."""

    @staticmethod
    def extract_entities_rule_based(text: str, current_state: AgreementState = None) -> dict:
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

        # 10.5. Property Inventory & Annexure Extraction
        if re.search(r'\b(?:un[\-\s]*furnished|no\s+inventory|no\s+annexure|standard\s+fixtures?\s+only|skip\s+inventory|skip\s+annexure|without\s+inventory|no\s+furniture)\b', cleaned, re.I):
            if ":" in cleaned and len(cleaned.split(":", 1)[1].strip()) > 2:
                extracted["annexure"] = cleaned.strip()
            else:
                extracted["annexure"] = "Unfurnished (No separate inventory)"
        elif re.search(r'\bsemi[\-\s]*furnished\b', cleaned, re.I):
            extracted["annexure"] = cleaned.strip()
        elif re.search(r'\bfully[\-\s]*furnished\b', cleaned, re.I):
            extracted["annexure"] = cleaned.strip()
        elif re.search(r'^(?:(?:property\s+)?inventory|annexure|fixtures|fittings|furniture|appliances)[:\s\-]+(.+)$', cleaned, re.I | re.DOTALL):
            inv_m = re.search(r'^(?:(?:property\s+)?inventory|annexure|fixtures|fittings|furniture|appliances)[:\s\-]+(.+)$', cleaned, re.I | re.DOTALL)
            if inv_m and inv_m.group(1).strip():
                extracted["annexure"] = inv_m.group(1).strip()
        elif current_state and ("annexure" not in (current_state.fields or {}) or not current_state.get_value("annexure")) and current_state.get_value("agreement_start_date") and (current_state.get_value("lockin") or current_state.get_value("lockin_months")):
            # If we are in the Annexure question phase and user lists fixtures/appliances
            if any(term in cleaned.lower() for term in ("fan", "light", "geyser", "ac", "air conditioner", "kitchen", "wardrobe", "cupboard", "sofa", "bed", "mattress", "tv", "fridge", "refrigerator", "washing machine", "table", "chair", "curtain", "chimney")):
                extracted["annexure"] = cleaned.strip()

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

    @staticmethod
    def detect_field_updates(find_text: str, replace_text: str) -> dict:
        """Server-side fallback: detect which form field was changed based on find/replace text."""
        updates = {}

        # Notice period patterns: "1 Month", "2 Months", "3 Months"
        notice_old = re.search(r'(\d+)\s*[Mm]onths?', find_text)
        notice_new = re.search(r'(\d+)\s*[Mm]onths?', replace_text)
        if notice_old and notice_new and notice_old.group(0) != notice_new.group(0):
            n = int(notice_new.group(1))
            updates["notice_period"] = "1 Month" if n == 1 else f"{n} Months"

        # Lockin months
        lockin_old = re.search(r'(?:lock[\-\s]*in.*?|minimum tenure.*?)(\d+)\s*[Mm]onths', find_text)
        lockin_new = re.search(r'(?:lock[\-\s]*in.*?|minimum tenure.*?)(\d+)\s*[Mm]onths', replace_text)
        if lockin_old and lockin_new and lockin_old.group(1) != lockin_new.group(1):
            updates["lockin_months"] = lockin_new.group(1)

        # Penalty deduction days
        penalty_old = re.search(r'(\d+)\s*days?\s*(?:of\s*)?(?:monthly\s*)?rent', find_text, re.I)
        penalty_new = re.search(r'(\d+)\s*days?\s*(?:of\s*)?(?:monthly\s*)?rent', replace_text, re.I)
        if penalty_old and penalty_new and penalty_old.group(1) != penalty_new.group(1):
            updates["penalty_deduction"] = penalty_new.group(1)

        # Rent amount (Rs. X,XXX or Rs. XX,XXX)
        rent_old = re.search(r'Rs\.?\s*([\d,]+)', find_text)
        rent_new = re.search(r'Rs\.?\s*([\d,]+)', replace_text)
        if rent_old and rent_new and rent_old.group(1) != rent_new.group(1):
            if 'deposit' in find_text.lower() or 'deposit' in replace_text.lower():
                updates["security_deposit"] = rent_new.group(1).replace(",", "")
            else:
                updates["monthly_rent"] = rent_new.group(1).replace(",", "")

        # Increase percent
        inc_old = re.search(r'(\d+(?:\.\d+)?)\s*[-–]?\s*\d*%', find_text)
        inc_new = re.search(r'(\d+(?:\.\d+)?)\s*[-–]?\s*\d*%', replace_text)
        if inc_old and inc_new and inc_old.group(1) != inc_new.group(1):
            updates["increase_percent"] = inc_new.group(1)

        return updates
