"""
clauses/evaluator.py — Clause Conditions, Field Resolution & Substitution Engine
==================================================================================
"""

import sys, os
import re
import html as _html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from field_registry import FIELD_REGISTRY
from .formatters import (
    _safe_int, clean_text, combine_name_prefix_once, format_careof,
    format_age, format_ordinal_date, format_rent_increase, extract_city,
    format_indian_currency
)

_PKEY_TO_CANONICAL = {
    "P1": "agreement_date",
    "P2": "owner1_name",
    "P3": "owner1_age",
    "P4": "owner1_careofname",
    "P5": "owner1_occupation",
    "P6": "owner1_address",
    "P7": "tenant1_name",
    "P8": "tenant1_age",
    "P9": "tenant1_careofname",
    "P10": "tenant1_occupation",
    "P11": "tenant1_address",
    "P12": "property_address",
    "P13": "monthly_rent",
    "P14": "monthly_rent_words",
    "P15": "maintenance",
    "P16": "agreement_start_date",
    "P17": "agreement_end_date",
    "P18": "increase_percent",
    "P19": "security_deposit",
    "P20": "security_deposit_words",
    "P21": "lockin_months",
    "P22": "penalty_deduction",
    "P23": "notice_period",
    "P24": "owner1_careof",
    "P25": "tenant1_careof",
    "P26": "annexure",
    "P27": "services_enrolled",
    "P28": "lockin_end_date",
    "P29": "tenant2_name",
    "P30": "tenant2_age",
    "P31": "tenant2_careof",
    "P32": "tenant2_careofname",
    "P33": "tenant2_occupation",
    "P34": "tenant2_address",
    "P41": "owner2_name",
    "P42": "owner2_age",
    "P43": "owner2_careof",
    "P44": "owner2_careofname",
    "P45": "owner2_occupation",
    "P46": "owner2_address",
    "P51": "tenant_poc",
    "P52": "tenant_gender",
    "P53": "opp_gender",
}

_CANONICAL_ALIASES = {
    # Agreement / Dates
    "agreement_date": ["agreement_date", "P1", "today_date"],
    "agreement_start_date": ["agreement_start_date", "P16", "start_date"],
    "agreement_end_date": ["agreement_end_date", "P17", "end_date"],
    "lockin_end_date": ["lockin_end_date", "P28"],
    "agreement_type": ["agreement_type", "TEMPLATE_USED"],
    "tenant_type": ["tenant_type", "TENANT_TYPE"],
    "owner_count": ["owner_count", "Owner_count"],
    "tenant_count": ["tenant_count", "Tenant_Count"],
    "lockin": ["lockin", "Renewal"],

    # Property
    "property_address": ["property_address", "P12"],
    "society_name": ["society_name", "PROP_SOCIETYNAME"],
    "block": ["block", "PROP_BLOCK"],
    "flat_no": ["flat_no", "PROP_NO"],
    "area": ["area", "PROP_AREA"],
    "property_type": ["property_type", "PROP_TYPE"],
    "property_id": ["property_id"],

    # Financial
    "monthly_rent": ["monthly_rent", "P13"],
    "monthly_rent_words": ["monthly_rent_words", "P14", "rent_words"],
    "maintenance": ["maintenance", "P15"],
    "increase_percent": ["increase_percent", "P18"],
    "rent_increase_type": ["rent_increase_type", "rent_increase"],
    "security_deposit": ["security_deposit", "P19"],
    "security_deposit_words": ["security_deposit_words", "P20", "deposit_words"],

    # Legal
    "lockin_months": ["lockin_months", "P21"],
    "penalty_deduction": ["penalty_deduction", "P22"],
    "notice_period": ["notice_period", "P23"],
    "annexure": ["annexure", "P26"],
    "services_enrolled": ["services_enrolled", "P27"],

    # Owner 1
    "owner1_prefix": ["owner1_prefix", "OWNER_NAME_PREFIX"],
    "owner1_name": ["owner1_name", "P2"],
    "owner1_age": ["owner1_age", "P3"],
    "owner1_careof": ["owner1_careof", "P24", "OWNER_CAREOF"],
    "owner1_careofname": ["owner1_careofname", "P4"],
    "owner1_careofname_prefix": ["owner1_careofname_prefix", "OWNER_CAREOFNAME_PREFIX"],
    "owner1_occupation": ["owner1_occupation", "P5"],
    "owner1_address": ["owner1_address", "P6"],
    "owner1_email": ["owner1_email", "OWNER_EMAILID", "owner1_emailid"],
    "owner1_phone": ["owner1_phone", "owner1_phonenumber"],

    # Owner 2
    "owner2_prefix": ["owner2_prefix", "OWNER2_NAME_PREFIX"],
    "owner2_name": ["owner2_name", "P41"],
    "owner2_age": ["owner2_age", "P42"],
    "owner2_careof": ["owner2_careof", "P43", "OWNER2_CAREOF"],
    "owner2_careofname": ["owner2_careofname", "P44"],
    "owner2_careofname_prefix": ["owner2_careofname_prefix", "OWNER2_CAREOFNAME_PREFIX"],
    "owner2_occupation": ["owner2_occupation", "P45"],
    "owner2_address": ["owner2_address", "P46"],
    "owner2_email": ["owner2_email", "owner2_emailid"],
    "owner2_phone": ["owner2_phone", "owner2_phonenumber"],

    # Owner 3-6
    "owner3_prefix": ["owner3_prefix", "OWNER3_NAME_PREFIX"],
    "owner3_name": ["owner3_name"], "owner3_age": ["owner3_age"], "owner3_careof": ["owner3_careof"], "owner3_careofname": ["owner3_careofname"], "owner3_occupation": ["owner3_occupation"], "owner3_address": ["owner3_address"],
    "owner4_prefix": ["owner4_prefix"], "owner4_name": ["owner4_name"], "owner4_age": ["owner4_age"], "owner4_careof": ["owner4_careof"], "owner4_careofname": ["owner4_careofname"], "owner4_occupation": ["owner4_occupation"], "owner4_address": ["owner4_address"],
    "owner5_prefix": ["owner5_prefix"], "owner5_name": ["owner5_name"], "owner5_age": ["owner5_age"], "owner5_careof": ["owner5_careof"], "owner5_careofname": ["owner5_careofname"], "owner5_occupation": ["owner5_occupation"], "owner5_address": ["owner5_address"],
    "owner6_prefix": ["owner6_prefix"], "owner6_name": ["owner6_name"], "owner6_age": ["owner6_age"], "owner6_careof": ["owner6_careof"], "owner6_careofname": ["owner6_careofname"], "owner6_occupation": ["owner6_occupation"], "owner6_address": ["owner6_address"],

    # Tenant 1
    "tenant1_prefix": ["tenant1_prefix", "TENANT_NAME_PREFIX"],
    "tenant1_name": ["tenant1_name", "P7"],
    "tenant1_age": ["tenant1_age", "P8"],
    "tenant1_careof": ["tenant1_careof", "P25", "TENANT_CAREOF"],
    "tenant1_careofname": ["tenant1_careofname", "P9"],
    "tenant1_careofname_prefix": ["tenant1_careofname_prefix", "TENANT_CAREOFNAME_PREFIX"],
    "tenant1_occupation": ["tenant1_occupation", "P10"],
    "tenant1_address": ["tenant1_address", "P11"],
    "tenant1_email": ["tenant1_email", "TENANT_EMAILID", "tenant1_emailid"],
    "tenant1_phone": ["tenant1_phone", "tenant1_phonenumber"],

    # Tenant 2
    "tenant2_prefix": ["tenant2_prefix", "TENANT2_NAME_PREFIX"],
    "tenant2_name": ["tenant2_name", "P29"],
    "tenant2_age": ["tenant2_age", "P30"],
    "tenant2_careof": ["tenant2_careof", "P31", "TENANT2_CAREOF"],
    "tenant2_careofname": ["tenant2_careofname", "P32"],
    "tenant2_careofname_prefix": ["tenant2_careofname_prefix", "TENANT2_CAREOFNAME_PREFIX"],
    "tenant2_occupation": ["tenant2_occupation", "P33"],
    "tenant2_address": ["tenant2_address", "P34"],
    "tenant2_email": ["tenant2_email", "tenant2_emailid"],
    "tenant2_phone": ["tenant2_phone", "tenant2_phonenumber"],

    # Tenant 3-6
    "tenant3_prefix": ["tenant3_prefix"], "tenant3_name": ["tenant3_name"], "tenant3_age": ["tenant3_age"], "tenant3_careof": ["tenant3_careof"], "tenant3_careofname": ["tenant3_careofname"], "tenant3_occupation": ["tenant3_occupation"], "tenant3_address": ["tenant3_address"],
    "tenant4_prefix": ["tenant4_prefix"], "tenant4_name": ["tenant4_name"], "tenant4_age": ["tenant4_age"], "tenant4_careof": ["tenant4_careof"], "tenant4_careofname": ["tenant4_careofname"], "tenant4_occupation": ["tenant4_occupation"], "tenant4_address": ["tenant4_address"],
    "tenant5_prefix": ["tenant5_prefix"], "tenant5_name": ["tenant5_name"], "tenant5_age": ["tenant5_age"], "tenant5_careof": ["tenant5_careof"], "tenant5_careofname": ["tenant5_careofname"], "tenant5_occupation": ["tenant5_occupation"], "tenant5_address": ["tenant5_address"],
    "tenant6_prefix": ["tenant6_prefix"], "tenant6_name": ["tenant6_name"], "tenant6_age": ["tenant6_age"], "tenant6_careof": ["tenant6_careof"], "tenant6_careofname": ["tenant6_careofname"], "tenant6_occupation": ["tenant6_occupation"], "tenant6_address": ["tenant6_address"],

    # Bachelor
    "tenant_poc": ["tenant_poc", "P51"],
    "tenant_gender": ["tenant_gender", "P52"],
    "opp_gender": ["opp_gender", "P53"],
}

def _resolve_value(data, key):
    """
    Resolve a single registry field value from form data.
    Checks canonical key first, then fallback aliases (legacy P-keys, uppercase names).
    """
    if not data or not isinstance(data, dict):
        return ""

    val = data.get(key)
    if val is not None and str(val).strip() != "":
        return clean_text(str(val).strip())

    aliases = _CANONICAL_ALIASES.get(key, [])
    for alias in aliases:
        val = data.get(alias)
        if val is not None and str(val).strip() != "":
            return clean_text(str(val).strip())

    for pkey, canonical in _PKEY_TO_CANONICAL.items():
        if canonical == key:
            val = data.get(pkey)
            if val is not None and str(val).strip() != "":
                return clean_text(str(val).strip())

    return ""

def _build_field_map(data):
    """Build placeholder -> value dictionary using FIELD_REGISTRY."""
    owner_count = _safe_int(_resolve_value(data, "owner_count") or "1")
    tenant_count = _safe_int(_resolve_value(data, "tenant_count") or "1")
    
    licensor_word = "Licensors" if owner_count > 1 else "Licensor"
    licensee_word = "Licensees" if tenant_count > 1 else "Licensee"
    owner_word    = "Owners"    if owner_count > 1 else "Owner"
    tenant_word   = "Tenants"   if tenant_count > 1 else "Tenant"
    pronoun_his   = "his/her"   if tenant_count > 1 else "his"
    pronoun_they  = "they"      if tenant_count > 1 else "he"

    prop_addr = _resolve_value(data, "property_address") or ""
    prop_city_input = _resolve_value(data, "property_city") or _resolve_value(data, "city")
    if prop_city_input and str(prop_city_input).strip():
        property_city = str(prop_city_input).strip().title()
    else:
        property_city = extract_city(prop_addr)

    field_map = {
        "{licensor_word}": licensor_word,
        "{licensee_word}": licensee_word,
        "{owner_word}":    owner_word,
        "{tenant_word}":   tenant_word,
        "{pronoun_his}":   pronoun_his,
        "{pronoun_they}":  pronoun_they,
        "{property_city}": property_city,
    }

    raw_increase   = _resolve_value(data, "increase_percent")
    rent_inc_type  = _resolve_value(data, "rent_increase_type")

    for field_def in FIELD_REGISTRY:
        key         = field_def["key"]
        placeholder = field_def["placeholder"]
        auto_calc   = field_def.get("auto_calc")
        party_type  = field_def.get("party_type", "")

        raw = _resolve_value(data, key)

        if auto_calc == "today" or key == "agreement_date":
            val = format_ordinal_date(raw)
        elif key in ("agreement_start_date", "agreement_end_date", "lockin_end_date"):
            val = format_ordinal_date(raw)
        elif auto_calc == "format_indian" or key in ("monthly_rent", "security_deposit"):
            val = format_indian_currency(raw)
        elif key == "property_address":
            val = raw.upper()
        elif key == "increase_percent":
            val = format_rent_increase(raw_increase, rent_inc_type)
        elif key.endswith("_name") and party_type in ("owner", "tenant"):
            prefix_key = key.replace("_name", "_prefix")
            prefix = _resolve_value(data, prefix_key)
            val = combine_name_prefix_once(prefix, raw)
        elif key.endswith("_age") and party_type in ("owner", "tenant"):
            val = format_age(raw)
        elif key.endswith("_address") and party_type in ("owner", "tenant", "property"):
            val = raw.upper()
        elif key.endswith("_careof") and not key.endswith("_careofname"):
            prefix_key = key.replace("_careof", "_prefix")
            prefix = _resolve_value(data, prefix_key)
            val = format_careof(prefix, raw)
        elif key.endswith("_careofname"):
            pfx_key = key + "_prefix"
            prefix = _resolve_value(data, pfx_key) or "Mr."
            val = combine_name_prefix_once(prefix, raw)
        elif auto_calc in ("words_rent", "words_deposit") or key in ("monthly_rent_words", "security_deposit_words"):
            val = raw
        elif auto_calc == "opp_gender" or key == "opp_gender":
            tg = _resolve_value(data, "tenant_gender").lower()
            val = "Female" if tg == "male" else ("Male" if tg == "female" else raw)
        else:
            val = raw

        field_map[placeholder] = val

    # Dynamically populate all owner1..6 and tenant1..6 fields into field_map
    for party_type in ("owner", "tenant"):
        for i in range(1, 7):
            name_raw = _resolve_value(data, f"{party_type}{i}_name")
            if name_raw:
                pfx = _resolve_value(data, f"{party_type}{i}_prefix")
                field_map[f"{{{party_type}{i}_name}}"] = combine_name_prefix_once(pfx, name_raw)
            
            age_raw = _resolve_value(data, f"{party_type}{i}_age")
            if age_raw:
                field_map[f"{{{party_type}{i}_age}}"] = format_age(age_raw)

            careof_raw = _resolve_value(data, f"{party_type}{i}_careof")
            if careof_raw:
                pfx = _resolve_value(data, f"{party_type}{i}_prefix")
                field_map[f"{{{party_type}{i}_careof}}"] = format_careof(pfx, careof_raw)

            careofname_raw = _resolve_value(data, f"{party_type}{i}_careofname")
            if careofname_raw:
                c_pfx = _resolve_value(data, f"{party_type}{i}_careofname_prefix") or "Mr."
                field_map[f"{{{party_type}{i}_careofname}}"] = combine_name_prefix_once(c_pfx, careofname_raw)

            occ_raw = _resolve_value(data, f"{party_type}{i}_occupation")
            if occ_raw:
                field_map[f"{{{party_type}{i}_occupation}}"] = occ_raw

            addr_raw = _resolve_value(data, f"{party_type}{i}_address")
            if addr_raw:
                field_map[f"{{{party_type}{i}_address}}"] = addr_raw.upper()

    return field_map

def _evaluate_clause(clause, data):
    """Determine if a clause should be included based on form data (like lock-in and tenant type)."""
    lockin_raw = str(_resolve_value(data, "lockin")).lower()
    has_lockin = lockin_raw in ("yes", "y", "true", "1", "on")
    is_bachelor = str(_resolve_value(data, "tenant_type")).lower() == "bachelor"
    
    c_id = clause["id"]
    text = clause["text"]
    
    if (c_id in ("lock_in", "clause_29") or "minimum tenure" in text.lower()) and not has_lockin:
        return None
    if clause.get("condition") == "tenant_type == 'bachelor'" and not is_bachelor:
        return None
        
    if not has_lockin:
        if c_id == "notice_period":
            text = text.replace("after completion of Lock in Period", "").replace("  ", " ")
        elif c_id == "termination_by_licensees":
            text = text.replace(", after completion of Lock in Period,", "").replace("  ", " ")
        elif c_id == "forfeiture":
            text = text.replace(", and the Lock-in Period clause shall stand terminated", "")
            text = text.replace("and the Lock-in Period clause shall stand terminated", "")

    return text

def _substitute_fields(text, field_map):
    """Replace all {placeholder} tokens in clause text with resolved values."""
    if not text:
        return ""

    for key, val in field_map.items():
        text = text.replace(key, str(val) if val is not None else "")

    def replace_pkey_tag(m):
        pkey = m.group(2).strip()
        canonical = _PKEY_TO_CANONICAL.get(pkey)
        if canonical:
            placeholder = f"{{{canonical}}}"
            if placeholder in field_map:
                return str(field_map[placeholder])
        if f"{{{pkey}}}" in field_map:
            return str(field_map[f"{{{pkey}}}"])
        return m.group(0)

    text = re.sub(r'<([^>]*?:)?\s*(P\d+)\s*>', replace_pkey_tag, text)
    text = text.replace('\t', ' ')
    return text
