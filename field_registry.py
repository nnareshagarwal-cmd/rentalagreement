"""
field_registry.py — Single Source of Truth for AgreementAI Form Fields
=======================================================================
Every field that appears in the form AND/OR the document is defined here once.

Field schema:
    key         : canonical field name used in form data, document placeholders, and DB
    label       : human-readable label shown in the form
    emoji       : emoji prefix for the label
    type        : input type — text | date | select | textarea | checkbox | readonly | hidden
    options     : list of option strings (for type=select), or []
    required    : True/False — whether the field is required for form submission
    readonly    : True/False — user cannot edit (auto-calculated fields)
    wide        : True/False — field spans full width (e.g. address, annexure)
    rows        : int — number of rows for textarea type
    section     : which collapsible section this field belongs to
    placeholder : {key} used inside clause text for substitution
    party_index : 1=always shown, 2=shown when count>=2, 3=shown when count>=3, etc.
    party_type  : owner | tenant | agreement | property | financial | legal | meta | bachelor
    auto_calc   : None | 'today' | 'words_rent' | 'words_deposit' | 'end_date' |
                  'lockin_end_date' | 'opp_gender' | 'deposit_2x' | 'format_indian'
    depends_on  : dict of {field_key: value} — conditional visibility
    hint        : short helper text shown below the input (optional)

Sections (in render order):
    meta            — Agreement type, tenant type, counts, lockin toggle
    agreement_dates — Agreement date, start, end, lockin end
    property        — Address, type, block, flat no, area
    financial       — Rent, deposit, maintenance, increase
    legal_terms     — Lockin months, penalty, notice, annexure, services
    owner_1         — Owner 1 all fields
    owner_2         — Owner 2 (shown when owner_count >= 2)
    owner_3 .. 6    — Owners 3-6 (shown when owner_count >= N)
    tenant_1        — Tenant 1 all fields
    tenant_2        — Tenant 2 (shown when tenant_count >= 2)
    tenant_3 .. 6   — Tenants 3-6 (shown when tenant_count >= N)
    bachelor        — Bachelor-specific fields (POC, gender)
"""

from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Option lists (reusable)
# ─────────────────────────────────────────────────────────────────────────────
_OCCUPATION_OPTIONS = [
    "PRIVATE EMPLOYEE",
    "GOVERNMENT EMPLOYEE",
    "BUSINESS",
    "RETIRED GOVERNMENT EMPLOYEE",
    "RETIRED",
    "HOUSEWIFE",
    "PROFESSIONAL",
    "SELF EMPLOYED",
]
_CAREOF_OPTIONS = ["Father Name", "Husband Name"]
_PREFIX_OPTIONS = ["Mr.", "Ms.", "Mrs.", "Miss.", "Dr."]
_MAINTENANCE_OPTIONS = ["Including", "Excluding"]
_NOTICE_OPTIONS = ["1 Month", "2 Months", "3 Months"]
_AGREEMENT_TYPE_OPTIONS = ["Simple", "Leave&License"]
_TENANT_TYPE_OPTIONS = ["Family", "Bachelor"]
_COUNT_OPTIONS = ["1", "2", "3", "4", "5", "6"]
_PROPERTY_TYPE_OPTIONS = ["Apartment", "Villa", "Independent House"]
_RENT_INCREASE_TYPE_OPTIONS = ["% of Rent", "Fixed Increase"]
_GENDER_OPTIONS = ["Male", "Female"]


def _field(
    key: str,
    label: str,
    emoji: str,
    type_: str,
    section: str,
    placeholder: str,
    party_type: str,
    *,
    options: List[str] = None,
    required: bool = True,
    readonly: bool = False,
    wide: bool = False,
    rows: int = 3,
    party_index: int = 1,
    auto_calc: Optional[str] = None,
    depends_on: Optional[Dict[str, Any]] = None,
    hint: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "emoji": emoji,
        "type": type_,
        "section": section,
        "placeholder": f"{{{key}}}",   # e.g. {owner1_name}
        "party_type": party_type,
        "options": options or [],
        "required": required,
        "readonly": readonly,
        "wide": wide,
        "rows": rows,
        "party_index": party_index,
        "auto_calc": auto_calc,
        "depends_on": depends_on or {},
        "hint": hint,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FIELD REGISTRY — authoritative ordered list
# ─────────────────────────────────────────────────────────────────────────────
FIELD_REGISTRY: List[Dict[str, Any]] = [

    # ── AGREEMENT DATES & TYPE ───────────────────────────────────────────────
    _field("agreement_type",  "Agreement Type",  "📝", "hidden", "agreement_dates", "{agreement_type}",
           "agreement", required=False),

    _field("tenant_type",     "Tenant Type",     "👥", "select", "agreement_dates", "{tenant_type}",
           "agreement", options=_TENANT_TYPE_OPTIONS),

    _field("owner_count",     "Owner Count",     "👤", "hidden", "agreement_dates", "{owner_count}",
           "agreement", required=False),

    _field("tenant_count",    "Tenant Count",    "👪", "hidden", "agreement_dates", "{tenant_count}",
           "agreement", required=False),

    _field("lockin",          "Lock-in Period",  "🔒", "checkbox", "agreement_dates", "{lockin}",
           "agreement", required=False,
           hint="Check to enable lock-in clause"),

    _field("agreement_date",      "Today's Date",        "📅", "date",     "agreement_dates",
           "{agreement_date}",  "agreement", readonly=True,
           auto_calc="today"),

    _field("agreement_start_date","Agreement Start Date", "📅", "date",     "agreement_dates",
           "{agreement_start_date}", "agreement"),

    _field("agreement_end_date",  "Agreement End Date",   "📅", "date",     "agreement_dates",
           "{agreement_end_date}",  "agreement",
           auto_calc="end_date",
           hint="Auto-calculated as start date + 11 months"),

    _field("lockin_months",    "Lock-in Months",           "🔒", "text",     "agreement_dates",
           "{lockin_months}",  "agreement", required=False,
           hint="Number of months tenant must stay"),

    _field("lockin_end_date",     "Lock-in End Date",     "🔓", "date",     "agreement_dates",
           "{lockin_end_date}",     "agreement", required=False,
           auto_calc="lockin_end_date",
           hint="Auto-calculated from start date + lock-in months"),

    _field("penalty_deduction","Penalty Deduction (days)", "⚠️",  "text",     "agreement_dates",
           "{penalty_deduction}","agreement", required=False,
           hint="Days of rent forfeited if vacated during lock-in"),

    # ── PROPERTY ─────────────────────────────────────────────────────────────
    _field("property_type",    "Property Type",           "🏛️",  "select",   "property",
           "{property_type}",  "property", options=_PROPERTY_TYPE_OPTIONS, required=False),

    _field("property_block",   "Block / Tower",           "🏘️",  "text",     "property",
           "{property_block}", "property", required=False),

    _field("property_no",      "Flat / Door Number",      "🏠", "text",     "property",
           "{property_no}",    "property", required=False),

    _field("society_name",     "Society Name / Project",  "🏢", "text",     "property",
           "{society_name}",   "property", required=False),

    _field("property_city",    "City",                    "🏙️", "text",     "property",
           "{property_city}",  "property", required=False,
           hint="City where the property is located (e.g., Hyderabad, Bangalore, Mumbai)"),

    _field("property_address", "Rental Property Address", "📍", "textarea", "property",
           "{property_address}", "property", wide=True, rows=3,
           hint="Full address of the rental property"),

    _field("property_area",    "Area (sq ft)",            "📐", "hidden",   "property",
           "{property_area}",  "property", required=False),

    # ── FINANCIAL ────────────────────────────────────────────────────────────
    _field("monthly_rent",        "Rent",                      "💰", "text",     "financial",
           "{monthly_rent}",       "agreement",
           auto_calc="format_indian"),

    _field("monthly_rent_words",  "Rent in Words",             "✍️",  "text",     "financial",
           "{monthly_rent_words}", "agreement", readonly=True, required=False, wide=True,
           auto_calc="words_rent"),

    _field("maintenance",         "Maintenance",               "🛠️",  "select",   "financial",
           "{maintenance}",        "agreement", options=_MAINTENANCE_OPTIONS),

    _field("rent_increase_type",  "Rent Increase Type",        "📈", "select",   "financial",
           "{rent_increase_type}", "agreement",
           options=_RENT_INCREASE_TYPE_OPTIONS, required=False),

    _field("increase_percent",    "Rent Increase Value",       "📈", "text",     "financial",
           "{increase_percent}",   "agreement", required=False,
           hint="e.g. 5% or 1500 (Fixed). Appends % automatically for % type"),

    _field("security_deposit",    "Security Deposit",          "💎", "text",     "financial",
           "{security_deposit}",   "agreement",
           auto_calc="format_indian",
           hint="Auto-calculated as 2× rent. Override if needed"),

    _field("security_deposit_words","Security Deposit in Words","✍️", "text",       "financial",
           "{security_deposit_words}","agreement", readonly=True, required=False, wide=True,
           auto_calc="words_deposit"),

    _field("notice_period",    "Notice Period",            "⏳", "select",   "dates",
           "{notice_period}",  "agreement", options=_NOTICE_OPTIONS),

    _field("annexure",         "Annexure",                 "📎", "textarea", "financial",
           "{annexure}",       "agreement", required=False, wide=True, rows=6,
           hint="Additional terms (optional)"),

    # ── OWNER 1 ──────────────────────────────────────────────────────────────
    _field("owner1_prefix",      "Owner Name Prefix",             "👤", "select",  "owner_1",
           "{owner1_prefix}",     "owner", options=_PREFIX_OPTIONS, required=False),

    _field("owner1_name",        "Owner Full Name",               "👤", "text",    "owner_1",
           "{owner1_name}",       "owner"),

    _field("owner1_age",         "Owner Age",                     "🧓", "text",    "owner_1",
           "{owner1_age}",        "owner"),

    _field("owner1_careof",      "Owner Father / Husband",        "👪", "select",  "owner_1",
           "{owner1_careof}",     "owner", options=_CAREOF_OPTIONS),

    _field("owner1_careofname",  "Owner Father / Husband Name",   "👨", "text",    "owner_1",
           "{owner1_careofname}", "owner"),

    _field("owner1_occupation",  "Owner Occupation",              "💼", "select",  "owner_1",
           "{owner1_occupation}", "owner", options=_OCCUPATION_OPTIONS),

    _field("owner1_address",     "Owner Permanent Address",       "🏠", "textarea","owner_1",
           "{owner1_address}",    "owner", wide=False, rows=2),

    _field("owner1_email",       "Owner Email",                   "📧", "text",    "owner_1",
           "{owner1_email}",      "owner", required=False),

    _field("owner1_phone",       "Owner Phone",                   "📞", "text",    "owner_1",
           "{owner1_phone}",      "owner", required=False),

    # ── OWNER 2 ──────────────────────────────────────────────────────────────
    _field("owner2_prefix",      "Owner 2 Name Prefix",           "👤", "select",  "owner_2",
           "{owner2_prefix}",     "owner", options=_PREFIX_OPTIONS,
           required=False, party_index=2),

    _field("owner2_name",        "Owner 2 Full Name",             "👤", "text",    "owner_2",
           "{owner2_name}",       "owner", party_index=2),

    _field("owner2_age",         "Owner 2 Age",                   "🧓", "text",    "owner_2",
           "{owner2_age}",        "owner", party_index=2),

    _field("owner2_careof",      "Owner 2 Father / Husband",      "👪", "select",  "owner_2",
           "{owner2_careof}",     "owner", options=_CAREOF_OPTIONS, party_index=2),

    _field("owner2_careofname",  "Owner 2 Father / Husband Name", "👨", "text",    "owner_2",
           "{owner2_careofname}", "owner", party_index=2),

    _field("owner2_occupation",  "Owner 2 Occupation",            "💼", "select",  "owner_2",
           "{owner2_occupation}", "owner",
           options=_OCCUPATION_OPTIONS, party_index=2),

    _field("owner2_address",     "Owner 2 Permanent Address",     "🏠", "textarea","owner_2",
           "{owner2_address}",    "owner", wide=False, rows=2, party_index=2),

    _field("owner2_email",       "Owner 2 Email",                 "📧", "text",    "owner_2",
           "{owner2_email}",      "owner", required=False, party_index=2),

    _field("owner2_phone",       "Owner 2 Phone",                 "📞", "text",    "owner_2",
           "{owner2_phone}",      "owner", required=False, party_index=2),

    # ── OWNER 3 ──────────────────────────────────────────────────────────────
    _field("owner3_prefix",     "Owner 3 Name Prefix",            "👤", "select",  "owner_3",
           "{owner3_prefix}",    "owner", options=_PREFIX_OPTIONS, required=False, party_index=3),
    _field("owner3_name",       "Owner 3 Full Name",              "👤", "text",    "owner_3",
           "{owner3_name}",      "owner", party_index=3),
    _field("owner3_age",        "Owner 3 Age",                    "🧓", "text",    "owner_3",
           "{owner3_age}",       "owner", party_index=3),
    _field("owner3_careof",     "Owner 3 Father / Husband",       "👪", "select",  "owner_3",
           "{owner3_careof}",    "owner", options=_CAREOF_OPTIONS, party_index=3),
    _field("owner3_careofname", "Owner 3 Father / Husband Name",  "👨", "text",    "owner_3",
           "{owner3_careofname}","owner", party_index=3),
    _field("owner3_occupation", "Owner 3 Occupation",             "💼", "select",  "owner_3",
           "{owner3_occupation}","owner", options=_OCCUPATION_OPTIONS, party_index=3),
    _field("owner3_address",    "Owner 3 Permanent Address",      "🏠", "textarea","owner_3",
           "{owner3_address}",   "owner", wide=False, rows=2, party_index=3),

    # ── OWNER 4 ──────────────────────────────────────────────────────────────
    _field("owner4_prefix",     "Owner 4 Name Prefix",            "👤", "select",  "owner_4",
           "{owner4_prefix}",    "owner", options=_PREFIX_OPTIONS, required=False, party_index=4),
    _field("owner4_name",       "Owner 4 Full Name",              "👤", "text",    "owner_4",
           "{owner4_name}",      "owner", party_index=4),
    _field("owner4_age",        "Owner 4 Age",                    "🧓", "text",    "owner_4",
           "{owner4_age}",       "owner", party_index=4),
    _field("owner4_careof",     "Owner 4 Father / Husband",       "👪", "select",  "owner_4",
           "{owner4_careof}",    "owner", options=_CAREOF_OPTIONS, party_index=4),
    _field("owner4_careofname", "Owner 4 Father / Husband Name",  "👨", "text",    "owner_4",
           "{owner4_careofname}","owner", party_index=4),
    _field("owner4_occupation", "Owner 4 Occupation",             "💼", "select",  "owner_4",
           "{owner4_occupation}","owner", options=_OCCUPATION_OPTIONS, party_index=4),
    _field("owner4_address",    "Owner 4 Permanent Address",      "🏠", "textarea","owner_4",
           "{owner4_address}",   "owner", wide=False, rows=2, party_index=4),

    # ── OWNER 5 ──────────────────────────────────────────────────────────────
    _field("owner5_prefix",     "Owner 5 Name Prefix",            "👤", "select",  "owner_5",
           "{owner5_prefix}",    "owner", options=_PREFIX_OPTIONS, required=False, party_index=5),
    _field("owner5_name",       "Owner 5 Full Name",              "👤", "text",    "owner_5",
           "{owner5_name}",      "owner", party_index=5),
    _field("owner5_age",        "Owner 5 Age",                    "🧓", "text",    "owner_5",
           "{owner5_age}",       "owner", party_index=5),
    _field("owner5_careof",     "Owner 5 Father / Husband",       "👪", "select",  "owner_5",
           "{owner5_careof}",    "owner", options=_CAREOF_OPTIONS, party_index=5),
    _field("owner5_careofname", "Owner 5 Father / Husband Name",  "👨", "text",    "owner_5",
           "{owner5_careofname}","owner", party_index=5),
    _field("owner5_occupation", "Owner 5 Occupation",             "💼", "select",  "owner_5",
           "{owner5_occupation}","owner", options=_OCCUPATION_OPTIONS, party_index=5),
    _field("owner5_address",    "Owner 5 Permanent Address",      "🏠", "textarea","owner_5",
           "{owner5_address}",   "owner", wide=False, rows=2, party_index=5),

    # ── OWNER 6 ──────────────────────────────────────────────────────────────
    _field("owner6_prefix",     "Owner 6 Name Prefix",            "👤", "select",  "owner_6",
           "{owner6_prefix}",    "owner", options=_PREFIX_OPTIONS, required=False, party_index=6),
    _field("owner6_name",       "Owner 6 Full Name",              "👤", "text",    "owner_6",
           "{owner6_name}",      "owner", party_index=6),
    _field("owner6_age",        "Owner 6 Age",                    "🧓", "text",    "owner_6",
           "{owner6_age}",       "owner", party_index=6),
    _field("owner6_careof",     "Owner 6 Father / Husband",       "👪", "select",  "owner_6",
           "{owner6_careof}",    "owner", options=_CAREOF_OPTIONS, party_index=6),
    _field("owner6_careofname", "Owner 6 Father / Husband Name",  "👨", "text",    "owner_6",
           "{owner6_careofname}","owner", party_index=6),
    _field("owner6_occupation", "Owner 6 Occupation",             "💼", "select",  "owner_6",
           "{owner6_occupation}","owner", options=_OCCUPATION_OPTIONS, party_index=6),
    _field("owner6_address",    "Owner 6 Permanent Address",      "🏠", "textarea","owner_6",
           "{owner6_address}",   "owner", wide=False, rows=2, party_index=6),

    # ── TENANT 1 ─────────────────────────────────────────────────────────────
    _field("tenant1_prefix",     "Tenant Name Prefix",             "👤", "select",  "tenant_1",
           "{tenant1_prefix}",    "tenant", options=_PREFIX_OPTIONS, required=False),

    _field("tenant1_name",       "Tenant Full Name",               "👤", "text",    "tenant_1",
           "{tenant1_name}",      "tenant"),

    _field("tenant1_age",        "Tenant Age",                     "🧓", "text",    "tenant_1",
           "{tenant1_age}",       "tenant"),

    _field("tenant1_careof",     "Tenant Father / Husband",        "👪", "select",  "tenant_1",
           "{tenant1_careof}",    "tenant", options=_CAREOF_OPTIONS),

    _field("tenant1_careofname", "Tenant Father / Husband Name",   "👨", "text",    "tenant_1",
           "{tenant1_careofname}","tenant"),

    _field("tenant1_occupation", "Tenant Occupation",              "💼", "select",  "tenant_1",
           "{tenant1_occupation}","tenant", options=_OCCUPATION_OPTIONS),

    _field("tenant1_address",    "Tenant Permanent Address",       "🏠", "textarea","tenant_1",
           "{tenant1_address}",   "tenant", wide=False, rows=2),

    _field("tenant1_email",      "Tenant Email",                   "📧", "text",    "tenant_1",
           "{tenant1_email}",     "tenant", required=False),

    _field("tenant1_phone",      "Tenant Phone",                   "📞", "text",    "tenant_1",
           "{tenant1_phone}",     "tenant", required=False),

    # ── TENANT 2 ─────────────────────────────────────────────────────────────
    _field("tenant2_prefix",     "Tenant 2 Name Prefix",           "👤", "select",  "tenant_2",
           "{tenant2_prefix}",    "tenant", options=_PREFIX_OPTIONS, required=False, party_index=2),
    _field("tenant2_name",       "Tenant 2 Full Name",             "👤", "text",    "tenant_2",
           "{tenant2_name}",      "tenant", party_index=2),
    _field("tenant2_age",        "Tenant 2 Age",                   "🧓", "text",    "tenant_2",
           "{tenant2_age}",       "tenant", party_index=2),
    _field("tenant2_careof",     "Tenant 2 Father / Husband",      "👪", "select",  "tenant_2",
           "{tenant2_careof}",    "tenant", options=_CAREOF_OPTIONS, party_index=2),
    _field("tenant2_careofname", "Tenant 2 Father / Husband Name", "👨", "text",    "tenant_2",
           "{tenant2_careofname}","tenant", party_index=2),
    _field("tenant2_occupation", "Tenant 2 Occupation",            "💼", "select",  "tenant_2",
           "{tenant2_occupation}","tenant", options=_OCCUPATION_OPTIONS, party_index=2),
    _field("tenant2_address",    "Tenant 2 Permanent Address",     "🏠", "textarea","tenant_2",
           "{tenant2_address}",   "tenant", wide=False, rows=2, party_index=2),
    _field("tenant2_email",      "Tenant 2 Email",                 "📧", "text",    "tenant_2",
           "{tenant2_email}",     "tenant", required=False, party_index=2),
    _field("tenant2_phone",      "Tenant 2 Phone",                 "📞", "text",    "tenant_2",
           "{tenant2_phone}",     "tenant", required=False, party_index=2),

    # ── TENANT 3 ─────────────────────────────────────────────────────────────
    _field("tenant3_prefix",     "Tenant 3 Name Prefix",           "👤", "select",  "tenant_3",
           "{tenant3_prefix}",    "tenant", options=_PREFIX_OPTIONS, required=False, party_index=3),
    _field("tenant3_name",       "Tenant 3 Full Name",             "👤", "text",    "tenant_3",
           "{tenant3_name}",      "tenant", party_index=3),
    _field("tenant3_age",        "Tenant 3 Age",                   "🧓", "text",    "tenant_3",
           "{tenant3_age}",       "tenant", party_index=3),
    _field("tenant3_careof",     "Tenant 3 Father / Husband",      "👪", "select",  "tenant_3",
           "{tenant3_careof}",    "tenant", options=_CAREOF_OPTIONS, party_index=3),
    _field("tenant3_careofname", "Tenant 3 Father / Husband Name", "👨", "text",    "tenant_3",
           "{tenant3_careofname}","tenant", party_index=3),
    _field("tenant3_occupation", "Tenant 3 Occupation",            "💼", "select",  "tenant_3",
           "{tenant3_occupation}","tenant", options=_OCCUPATION_OPTIONS, party_index=3),
    _field("tenant3_address",    "Tenant 3 Permanent Address",     "🏠", "textarea","tenant_3",
           "{tenant3_address}",   "tenant", wide=False, rows=2, party_index=3),

    # ── TENANT 4 ─────────────────────────────────────────────────────────────
    _field("tenant4_prefix",     "Tenant 4 Name Prefix",           "👤", "select",  "tenant_4",
           "{tenant4_prefix}",    "tenant", options=_PREFIX_OPTIONS, required=False, party_index=4),
    _field("tenant4_name",       "Tenant 4 Full Name",             "👤", "text",    "tenant_4",
           "{tenant4_name}",      "tenant", party_index=4),
    _field("tenant4_age",        "Tenant 4 Age",                   "🧓", "text",    "tenant_4",
           "{tenant4_age}",       "tenant", party_index=4),
    _field("tenant4_careof",     "Tenant 4 Father / Husband",      "👪", "select",  "tenant_4",
           "{tenant4_careof}",    "tenant", options=_CAREOF_OPTIONS, party_index=4),
    _field("tenant4_careofname", "Tenant 4 Father / Husband Name", "👨", "text",    "tenant_4",
           "{tenant4_careofname}","tenant", party_index=4),
    _field("tenant4_occupation", "Tenant 4 Occupation",            "💼", "select",  "tenant_4",
           "{tenant4_occupation}","tenant", options=_OCCUPATION_OPTIONS, party_index=4),
    _field("tenant4_address",    "Tenant 4 Permanent Address",     "🏠", "textarea","tenant_4",
           "{tenant4_address}",   "tenant", wide=False, rows=2, party_index=4),

    # ── TENANT 5 ─────────────────────────────────────────────────────────────
    _field("tenant5_prefix",     "Tenant 5 Name Prefix",           "👤", "select",  "tenant_5",
           "{tenant5_prefix}",    "tenant", options=_PREFIX_OPTIONS, required=False, party_index=5),
    _field("tenant5_name",       "Tenant 5 Full Name",             "👤", "text",    "tenant_5",
           "{tenant5_name}",      "tenant", party_index=5),
    _field("tenant5_age",        "Tenant 5 Age",                   "🧓", "text",    "tenant_5",
           "{tenant5_age}",       "tenant", party_index=5),
    _field("tenant5_careof",     "Tenant 5 Father / Husband",      "👪", "select",  "tenant_5",
           "{tenant5_careof}",    "tenant", options=_CAREOF_OPTIONS, party_index=5),
    _field("tenant5_careofname", "Tenant 5 Father / Husband Name", "👨", "text",    "tenant_5",
           "{tenant5_careofname}","tenant", party_index=5),
    _field("tenant5_occupation", "Tenant 5 Occupation",            "💼", "select",  "tenant_5",
           "{tenant5_occupation}","tenant", options=_OCCUPATION_OPTIONS, party_index=5),
    _field("tenant5_address",    "Tenant 5 Permanent Address",     "🏠", "textarea","tenant_5",
           "{tenant5_address}",   "tenant", wide=False, rows=2, party_index=5),

    # ── TENANT 6 ─────────────────────────────────────────────────────────────
    _field("tenant6_prefix",     "Tenant 6 Name Prefix",           "👤", "select",  "tenant_6",
           "{tenant6_prefix}",    "tenant", options=_PREFIX_OPTIONS, required=False, party_index=6),
    _field("tenant6_name",       "Tenant 6 Full Name",             "👤", "text",    "tenant_6",
           "{tenant6_name}",      "tenant", party_index=6),
    _field("tenant6_age",        "Tenant 6 Age",                   "🧓", "text",    "tenant_6",
           "{tenant6_age}",       "tenant", party_index=6),
    _field("tenant6_careof",     "Tenant 6 Father / Husband",      "👪", "select",  "tenant_6",
           "{tenant6_careof}",    "tenant", options=_CAREOF_OPTIONS, party_index=6),
    _field("tenant6_careofname", "Tenant 6 Father / Husband Name", "👨", "text",    "tenant_6",
           "{tenant6_careofname}","tenant", party_index=6),
    _field("tenant6_occupation", "Tenant 6 Occupation",            "💼", "select",  "tenant_6",
           "{tenant6_occupation}","tenant", options=_OCCUPATION_OPTIONS, party_index=6),
    _field("tenant6_address",    "Tenant 6 Permanent Address",     "🏠", "textarea","tenant_6",
           "{tenant6_address}",   "tenant", wide=False, rows=2, party_index=6),

    # ── BACHELOR FIELDS (visible only when tenant_type = Bachelor) ────────────
    _field("tenant_poc",     "Single Point of Contact (SPOC)",  "👤", "select_dynamic", "bachelor",
           "{tenant_poc}",    "bachelor",
           hint="Select which tenant is the SPOC",
           depends_on={"tenant_type": "Bachelor"}),

    _field("tenant_gender",  "Tenant Gender",           "⚧️",  "select",        "bachelor",
           "{tenant_gender}", "bachelor", options=_GENDER_OPTIONS,
           depends_on={"tenant_type": "Bachelor"}),

    _field("opp_gender",     "Opposite Gender",         "⚧️",  "hidden",        "bachelor",
           "{opp_gender}",    "bachelor", readonly=True, required=False,
           auto_calc="opp_gender",
           depends_on={"tenant_type": "Bachelor"}),

    # ── HIDDEN (exist in form data but not shown as editable fields) ─────────
    _field("property_id",  "Property ID", "🆔", "hidden", "meta",
           "{property_id}", "meta", required=False, readonly=True),
]


# ─────────────────────────────────────────────────────────────────────────────
# Convenience lookups built from registry (generated once at import time)
# ─────────────────────────────────────────────────────────────────────────────

# key → field definition
FIELD_BY_KEY: Dict[str, Dict] = {f["key"]: f for f in FIELD_REGISTRY}

# section → ordered list of fields
FIELDS_BY_SECTION: Dict[str, List[Dict]] = {}
for _f in FIELD_REGISTRY:
    FIELDS_BY_SECTION.setdefault(_f["section"], []).append(_f)

# All placeholder strings that must be resolved in clause text
ALL_PLACEHOLDERS: List[str] = [f["placeholder"] for f in FIELD_REGISTRY]

# Section display labels (used by both Python and JS)
SECTION_LABELS: Dict[str, str] = {
    "agreement_dates":  "📅 Agreement Dates",
    "property":         "🏠 Property Details",
    "financial":        "💰 Financial Terms",
    "owner_1":          "👤 Owner Details",
    "owner_2":          "👤 Owner 2 Details",
    "owner_3":          "👤 Owner 3 Details",
    "owner_4":          "👤 Owner 4 Details",
    "owner_5":          "👤 Owner 5 Details",
    "owner_6":          "👤 Owner 6 Details",
    "tenant_1":         "🧑 Tenant Details",
    "tenant_2":         "🧑 Tenant 2 Details",
    "tenant_3":         "🧑 Tenant 3 Details",
    "tenant_4":         "🧑 Tenant 4 Details",
    "tenant_5":         "🧑 Tenant 5 Details",
    "tenant_6":         "🧑 Tenant 6 Details",
    "bachelor":         "🎓 Bachelor Tenant Details",
}

# Ordered list of sections for rendering
SECTION_ORDER: List[str] = [
    "agreement_dates", "property",
    "owner_1", "owner_2", "owner_3", "owner_4", "owner_5", "owner_6",
    "tenant_1", "tenant_2", "tenant_3", "tenant_4", "tenant_5", "tenant_6",
    "financial", "bachelor",
]
