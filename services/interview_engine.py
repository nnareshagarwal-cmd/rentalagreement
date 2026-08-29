"""
services/interview_engine.py — Deterministic Legal Interview & Decision Engine
================================================================================
Legal Source of Truth for AgreementAI.
Evaluates scenario-based required/recommended/conditional fields, calculates readiness,
detects dependencies, and computes deterministic next questions and suggestion chips.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from clauses.formatters import num_to_words, _safe_int, format_indian_currency
from field_registry import FIELD_REGISTRY
from services.agreement_state import AgreementState, FieldEntry, FieldStatus, ProvenanceSource

# Build lookup by canonical key
_REGISTRY_MAP: Dict[str, Dict[str, Any]] = {f["key"]: f for f in FIELD_REGISTRY}


class FieldCategory:
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"


class InterviewEngine:
    """
    Deterministic rule engine that orchestrates the agreement creation interview.
    Ensures LLM does not hallucinate legal requirements or question flows.
    """

    @staticmethod
    def get_field_rules(
        agreement_type: str = "simple_rental",
        jurisdiction: str = "KA",
        scenario: str = "family",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Dynamically classifies fields into REQUIRED, RECOMMENDED, or CONDITIONAL
        based on agreement template, jurisdiction, and scenario.
        """
        is_leave_license = "leave" in agreement_type.lower() or "license" in agreement_type.lower()
        is_bachelor = scenario.lower() == "bachelor"
        is_maharashtra = jurisdiction.upper() == "MH"

        # Baseline Core Required Fields
        rules: Dict[str, Dict[str, Any]] = {
            # Owner Party Details (Sequential Steps)
            "owner1_name": {"category": FieldCategory.REQUIRED, "label": "Owner Full Name", "priority": 10},
            "owner1_age": {"category": FieldCategory.REQUIRED, "label": "Owner Age", "priority": 11},
            "owner1_careofname": {"category": FieldCategory.REQUIRED, "label": "Owner Father / Husband Name", "priority": 12},
            "owner1_address": {"category": FieldCategory.REQUIRED, "label": "Owner Permanent Address", "priority": 13},
            "owner1_occupation": {"category": FieldCategory.REQUIRED, "label": "Owner Occupation", "priority": 14},
            "owner1_phone": {"category": FieldCategory.OPTIONAL, "label": "Owner Mobile Number", "priority": 15},
            "owner1_email": {"category": FieldCategory.OPTIONAL, "label": "Owner Email ID", "priority": 16},

            # Tenant Party Details (Sequential Steps)
            "tenant1_name": {"category": FieldCategory.REQUIRED, "label": "Tenant Full Name", "priority": 17},
            "tenant1_age": {"category": FieldCategory.REQUIRED, "label": "Tenant Age", "priority": 18},
            "tenant1_careofname": {"category": FieldCategory.REQUIRED, "label": "Tenant Father / Husband Name", "priority": 19},
            "tenant1_address": {"category": FieldCategory.REQUIRED, "label": "Tenant Permanent Address", "priority": 20},
            "tenant1_occupation": {"category": FieldCategory.REQUIRED, "label": "Tenant Occupation", "priority": 21},
            "tenant1_phone": {"category": FieldCategory.OPTIONAL, "label": "Tenant Mobile Number", "priority": 22},
            "tenant1_email": {"category": FieldCategory.OPTIONAL, "label": "Tenant Email ID", "priority": 23},

            # Property
            "property_address": {"category": FieldCategory.REQUIRED, "label": "Rented Property Address", "priority": 20},

            # Financials
            "monthly_rent": {"category": FieldCategory.REQUIRED, "label": "Monthly Rent / License Fee", "priority": 30},
            "security_deposit": {"category": FieldCategory.REQUIRED, "label": "Security Deposit", "priority": 32},

            # Term & Dates
            "agreement_start_date": {"category": FieldCategory.REQUIRED, "label": "Agreement Start Date", "priority": 40},
            "agreement_end_date": {"category": FieldCategory.REQUIRED, "label": "Agreement End Date", "priority": 42},

            # Recommended Standard Terms
            "notice_period": {"category": FieldCategory.RECOMMENDED, "label": "Notice Period", "priority": 50, "default": "1 Month"},
            "maintenance": {"category": FieldCategory.RECOMMENDED, "label": "Society Maintenance", "priority": 52, "default": "Including"},
            "rent_increase_type": {"category": FieldCategory.RECOMMENDED, "label": "Rent Increase Type", "priority": 53, "default": "% of Rent"},
            "increase_percent": {"category": FieldCategory.RECOMMENDED, "label": "Rent Increase Value", "priority": 54, "default": "5%"},

            # Conditional / Context-Specific
            "lockin_months": {"category": FieldCategory.CONDITIONAL, "label": "Lock-in Period (Months)", "priority": 60, "parent": "lockin"},
            "penalty_deduction": {"category": FieldCategory.CONDITIONAL, "label": "Early Exit Penalty (Days Rent)", "priority": 62, "parent": "lockin_months", "default": "30"},
            "tenant_poc": {"category": FieldCategory.CONDITIONAL, "label": "Bachelor Group SPOC", "priority": 70, "parent": "scenario"},
            "annexure": {"category": FieldCategory.CONDITIONAL, "label": "Fittings & Fixtures Annexure", "priority": 80},
        }

        # Jurisdiction / Template Specific Adaptations
        if is_maharashtra or is_leave_license:
            rules["notice_period"]["default"] = "2 Months"
            rules["flat_no"] = {"category": FieldCategory.REQUIRED, "label": "Flat / Unit Number", "priority": 22}
            rules["society_name"] = {"category": FieldCategory.REQUIRED, "label": "Society / Building Name", "priority": 24}

        if is_bachelor:
            rules["tenant_poc"]["category"] = FieldCategory.REQUIRED

        return rules

    @classmethod
    def evaluate_readiness(cls, state: AgreementState) -> Dict[str, Any]:
        """
        Calculates exact readiness status, separating Required gaps from Recommendations.
        Enforces two-gate model:
          - ready_for_review: 100% required fields are at least extracted/suggested/confirmed.
          - ready_for_generation: 100% required fields are confirmed.
        """
        rules = cls.get_field_rules(state.agreement_type, state.jurisdiction, state.scenario)

        required_keys = [k for k, r in rules.items() if r["category"] == FieldCategory.REQUIRED]
        recommended_keys = [k for k, r in rules.items() if r["category"] == FieldCategory.RECOMMENDED]

        # Check Active Conditionals
        has_lockin = state.get_value("lockin") == "Y" or bool(state.get_value("lockin_months"))
        if has_lockin:
            if "lockin_months" not in required_keys:
                required_keys.append("lockin_months")

        required_completed = []
        required_missing = []
        required_needs_confirmation = []

        for key in required_keys:
            entry = state.get_field(key)
            label = rules.get(key, {}).get("label", key.replace("_", " ").title())
            if not entry or entry.value is None or str(entry.value).strip() == "":
                required_missing.append({"key": key, "label": label, "category": "required"})
            else:
                if entry.status == FieldStatus.CONFIRMED:
                    required_completed.append({"key": key, "label": label, "value": entry.value, "status": "confirmed"})
                else:
                    required_needs_confirmation.append({
                        "key": key,
                        "label": label,
                        "value": entry.value,
                        "status": entry.status,
                        "source": entry.source,
                    })

        recommended_status = []
        for key in recommended_keys:
            entry = state.get_field(key)
            label = rules.get(key, {}).get("label", key.replace("_", " ").title())
            val = entry.value if entry else None
            recommended_status.append({
                "key": key,
                "label": label,
                "value": val,
                "is_set": bool(val),
                "status": entry.status if entry else FieldStatus.MISSING,
            })

        total_required = len(required_keys)
        completed_count = len(required_completed) + len(required_needs_confirmation)
        missing_count = len(required_missing)

        # Two-Gate Checks
        ready_for_review = missing_count == 0
        ready_for_generation = missing_count == 0 and len(required_needs_confirmation) == 0

        # Headline — avoid exposing raw field counts to not overwhelm users
        if missing_count == 0:
            if ready_for_generation:
                headline = "✓ All required details verified · Ready to generate"
            else:
                headline = "✓ All required details present · Please review & confirm"
        elif completed_count == 0:
            headline = "Let's get started · A few details needed"
        elif missing_count == 1:
            headline = f"{completed_count} of {total_required} complete · Just 1 more detail needed"
        else:
            headline = f"{completed_count} of {total_required} complete · A few more details needed"

        return {
            "total_required": total_required,
            "completed_count": completed_count,
            "missing_count": missing_count,
            "ready_for_review": ready_for_review,
            "ready_for_generation": ready_for_generation,
            "headline": headline,
            "required_completed": required_completed,
            "required_needs_confirmation": required_needs_confirmation,
            "required_missing": required_missing,
            "recommended_status": recommended_status,
        }

    @classmethod
    def plan_next_interaction(cls, state: AgreementState) -> Dict[str, Any]:
        """
        Determines the next logical question cluster and interactive chips.
        Follows a focused, step-by-step interview flow:
          1. Owner Party (Name -> Age -> Father/Husband -> Address) [Skipped entirely if Aadhaar uploaded]
          2. Tenant Party (Name -> Age -> Father/Husband -> Address) [Skipped entirely if Aadhaar uploaded]
          3. Property Address
          4. Financials (Rent -> Deposit)
          5. Term & Dates (Start Date -> Duration)
        """
        readiness = cls.evaluate_readiness(state)
        missing = readiness["required_missing"]
        missing_keys = {m["key"] for m in missing}
        user_role = getattr(state, "user_role", "owner").lower()

        # ── FLOW FOR TENANT USER ──────────────────────────────────────────────
        if user_role == "tenant":
            # 1. Tenant's own details first (4 sequential steps)
            if "tenant1_name" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "tenant_name",
                    "target_fields": ["tenant1_name"],
                    "question_text": "Great! What is your **full name**? (Or upload your Aadhaar ID to auto-fill all your details at once).",
                    "suggestion_chips": [
                        {"label": "📎 Upload My Aadhaar (Tenant)", "action": "upload_aadhaar_tenant"},
                    ],
                }
            if "tenant1_age" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "tenant_age",
                    "target_fields": ["tenant1_age"],
                    "question_text": "What is your **age**?",
                    "suggestion_chips": [
                        {"label": "25", "value": "25"},
                        {"label": "28", "value": "28"},
                        {"label": "32", "value": "32"},
                        {"label": "35", "value": "35"},
                        {"label": "40", "value": "40"},
                    ],
                }
            if "tenant1_careofname" in missing_keys:
                careof_type = state.get_value("tenant1_careof")
                if careof_type == "Husband Name":
                    q_text = "What is your **Husband's full name**?"
                    chips = []
                elif careof_type == "Father Name":
                    q_text = "What is your **Father's full name**?"
                    chips = []
                else:
                    q_text = "Please provide your **Father's Name** (or Husband's Name if married female):"
                    chips = [
                        {"label": "👨 Father's Name", "value": "Father's Name"},
                        {"label": "💍 Husband's Name", "value": "Husband's Name"},
                    ]
                return {
                    "type": "question",
                    "focus_area": "tenant_careof",
                    "target_fields": ["tenant1_careofname", "tenant1_careof"],
                    "question_text": q_text,
                    "suggestion_chips": chips,
                }
            if "tenant1_address" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "tenant_address",
                    "target_fields": ["tenant1_address"],
                    "question_text": "What is your **permanent address**?",
                    "suggestion_chips": [],
                }
            if "tenant1_occupation" in missing_keys or "tenant1_phone" in missing_keys or "tenant1_email" in missing_keys:
                t_name = state.get_value("tenant1_name") or "Tenant"
                return {
                    "type": "party_profile",
                    "focus_area": "tenant_profile",
                    "party_role": "tenant",
                    "party_name": t_name,
                    "target_fields": ["tenant1_occupation", "tenant1_phone", "tenant1_email"],
                    "question_text": "Tenant Details",
                    "occupations": [
                        "PRIVATE EMPLOYEE",
                        "BUSINESS",
                    ],
                }

            # 2. Property Address
            if "property_address" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "property",
                    "target_fields": ["property_address"],
                    "question_text": "What is the full address of the property you are renting (including Flat/Unit No, Society, and City)?",
                    "suggestion_chips": [],
                }

            # 3. Owner Details
            if "owner1_name" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_name",
                    "target_fields": ["owner1_name"],
                    "question_text": "Who is the property owner (landlord)? Please provide their **full name** (or upload owner's Aadhaar).",
                    "suggestion_chips": [
                        {"label": "📎 Upload Owner Aadhaar", "action": "upload_aadhaar_owner"},
                    ],
                }
            if "owner1_age" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_age",
                    "target_fields": ["owner1_age"],
                    "question_text": "What is the owner's **age**?",
                    "suggestion_chips": [
                        {"label": "40", "value": "40"},
                        {"label": "45", "value": "45"},
                        {"label": "50", "value": "50"},
                        {"label": "55", "value": "55"},
                        {"label": "60", "value": "60"},
                    ],
                }
            if "owner1_careofname" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_careof",
                    "target_fields": ["owner1_careofname", "owner1_careof"],
                    "question_text": "Please provide the owner's **Father's or Husband's Name**:",
                    "suggestion_chips": [
                        {"label": "👨 Father's Name", "action": "fill_input", "value": "Father name is "},
                        {"label": "💍 Husband's Name", "action": "fill_input", "value": "Husband name is "},
                    ],
                }
            if "owner1_address" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_address",
                    "target_fields": ["owner1_address"],
                    "question_text": "What is the owner's **permanent address**?",
                    "suggestion_chips": [],
                }
            if not state.get_value("owner1_occupation"):
                o_name = state.get_value("owner1_name") or "Owner"
                return {
                    "type": "party_profile",
                    "focus_area": "owner_profile",
                    "party_role": "owner",
                    "party_name": o_name,
                    "target_fields": ["owner1_occupation", "owner1_phone", "owner1_email"],
                    "question_text": f"Please provide **occupation and contact details** for **{o_name}**:",
                    "occupations": [
                        "PRIVATE EMPLOYEE",
                        "BUSINESS",
                        "PROFESSIONAL",
                        "GOVERNMENT EMPLOYEE",
                        "SELF EMPLOYED",
                        "HOUSEWIFE",
                        "RETIRED",
                        "RETIRED GOVERNMENT EMPLOYEE",
                    ],
                }

        # ── FLOW FOR OWNER USER (DEFAULT) ─────────────────────────────────────
        else:
            # 1. Owner's own details first (sequential steps)
            if "owner1_name" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_name",
                    "target_fields": ["owner1_name"],
                    "question_text": "Great! As the owner, what is your **full name**? (Or upload your Aadhaar ID to auto-fill all your details at once).",
                    "suggestion_chips": [
                        {"label": "📎 Upload My Aadhaar (Owner)", "action": "upload_aadhaar_owner"},
                    ],
                }
            if "owner1_age" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_age",
                    "target_fields": ["owner1_age"],
                    "question_text": "What is your **age**?",
                    "suggestion_chips": [
                        {"label": "30", "value": "30"},
                        {"label": "35", "value": "35"},
                        {"label": "40", "value": "40"},
                        {"label": "45", "value": "45"},
                        {"label": "50", "value": "50"},
                        {"label": "55", "value": "55"},
                    ],
                }
            if "owner1_careofname" in missing_keys:
                careof_type = state.get_value("owner1_careof")
                if careof_type == "Husband Name":
                    q_text = "What is your **Husband's full name**?"
                    chips = []
                elif careof_type == "Father Name":
                    q_text = "What is your **Father's full name**?"
                    chips = []
                else:
                    q_text = "Please provide your **Father's Name** (or Husband's Name if married female):"
                    chips = [
                        {"label": "👨 Father's Name", "value": "Father's Name"},
                        {"label": "💍 Husband's Name", "value": "Husband's Name"},
                    ]
                return {
                    "type": "question",
                    "focus_area": "owner_careof",
                    "target_fields": ["owner1_careofname", "owner1_careof"],
                    "question_text": q_text,
                    "suggestion_chips": chips,
                }
            if "owner1_address" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "owner_address",
                    "target_fields": ["owner1_address"],
                    "question_text": "What is your **permanent address**?",
                    "suggestion_chips": [],
                }
            # 2. Tenant Details (sequential steps)
            if "tenant1_name" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "tenant_name",
                    "target_fields": ["tenant1_name"],
                    "question_text": "Who is the tenant moving in? Please provide their **full name** (or upload tenant's Aadhaar ID).",
                    "suggestion_chips": [
                        {"label": "📎 Upload Tenant Aadhaar", "action": "upload_aadhaar_tenant"},
                    ],
                }
            if "tenant1_age" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "tenant_age",
                    "target_fields": ["tenant1_age"],
                    "question_text": "What is the tenant's **age**?",
                    "suggestion_chips": [
                        {"label": "25", "value": "25"},
                        {"label": "28", "value": "28"},
                        {"label": "32", "value": "32"},
                        {"label": "35", "value": "35"},
                        {"label": "40", "value": "40"},
                    ],
                }
            if "tenant1_careofname" in missing_keys:
                careof_type = state.get_value("tenant1_careof")
                if careof_type == "Husband Name":
                    q_text = "What is the tenant's **Husband's full name**?"
                    chips = []
                elif careof_type == "Father Name":
                    q_text = "What is the tenant's **Father's full name**?"
                    chips = []
                else:
                    q_text = "Please provide the tenant's **Father's or Husband's Name**:"
                    chips = [
                        {"label": "👨 Father's Name", "value": "Father's Name"},
                        {"label": "💍 Husband's Name", "value": "Husband's Name"},
                    ]
                return {
                    "type": "question",
                    "focus_area": "tenant_careof",
                    "target_fields": ["tenant1_careofname", "tenant1_careof"],
                    "question_text": q_text,
                    "suggestion_chips": chips,
                }
            if "tenant1_address" in missing_keys:
                return {
                    "type": "question",
                    "focus_area": "tenant_address",
                    "target_fields": ["tenant1_address"],
                    "question_text": "What is the tenant's **permanent address**?",
                    "suggestion_chips": [],
                }
            # Both parties' profile details together (if both parties are known or entering profiles)
            owner_profile_missing = not state.get_value("owner1_occupation")
            tenant_profile_missing = not state.get_value("tenant1_occupation")

            if (owner_profile_missing or tenant_profile_missing) and (state.get_value("tenant1_name") or "tenant1_name" not in missing_keys):
                o_name = state.get_value("owner1_name") or "Owner"
                t_name = state.get_value("tenant1_name") or "Tenant"
                return {
                    "type": "party_profile",
                    "focus_area": "parties_profile",
                    "party_role": "dual",
                    "owner_name": o_name,
                    "tenant_name": t_name,
                    "target_fields": [
                        "owner1_occupation", "owner1_phone", "owner1_email",
                        "tenant1_occupation", "tenant1_phone", "tenant1_email",
                    ],
                    "question_text": "Owner & Tenant Details",
                    "occupations": [
                        "PRIVATE EMPLOYEE",
                        "BUSINESS",
                    ],
                }

        # 3. Property Address
        if "property_address" in missing_keys:
            return {
                "type": "question",
                "focus_area": "property",
                "target_fields": ["property_address"],
                "question_text": "What is the full address of the property being rented (including Flat/Unit No, Society/Building, and City)?",
                "suggestion_chips": [],
            }

        # 4. Missing Financials
        if "monthly_rent" in missing_keys:
            return {
                "type": "question",
                "focus_area": "financial",
                "target_fields": ["monthly_rent"],
                "question_text": "What is the monthly rent amount?",
                "suggestion_chips": [
                    {"label": "₹15,000", "value": "15000"},
                    {"label": "₹25,000", "value": "25000"},
                    {"label": "₹35,000", "value": "35000"},
                    {"label": "₹50,000", "value": "50000"},
                ],
            }

        if "security_deposit" in missing_keys:
            rent_val = state.get_value("monthly_rent", 0)
            rent_num = _safe_int(str(rent_val).replace(",", "")) if rent_val else 25000
            suggested_deposit = rent_num * 2
            
            # Dynamic multiples based on actual monthly rent
            chips = [
                {"label": f"₹{rent_num * 2:,} (2× Rent)", "value": str(rent_num * 2)},
                {"label": f"₹{rent_num * 3:,} (3× Rent)", "value": str(rent_num * 3)},
                {"label": f"₹{rent_num * 4:,} (4× Rent)", "value": str(rent_num * 4)},
                {"label": f"₹{rent_num * 5:,} (5× Rent)", "value": str(rent_num * 5)},
                {"label": f"₹{rent_num * 6:,} (6× Rent)", "value": str(rent_num * 6)},
            ]
            return {
                "type": "question",
                "focus_area": "financial",
                "target_fields": ["security_deposit"],
                "question_text": f"What is the security deposit amount? (Common practice is 2 months of rent: ₹{suggested_deposit:,})",
                "suggestion_chips": chips,
            }

        if not state.get_value("maintenance"):
            return {
                "type": "question",
                "focus_area": "maintenance",
                "target_fields": ["maintenance"],
                "question_text": "Is society maintenance included in the rent, or extra?",
                "suggestion_chips": [
                    {"label": "Excluding Maintenance (Extra)", "value": "Maintenance is excluding, tenant pays extra"},
                    {"label": "Including Maintenance", "value": "Maintenance is included in rent"},
                ],
            }

        # 3.2. Rent Escalation Type
        if not state.get_value("rent_increase_type") and not state.get_value("increase_percent"):
            return {
                "type": "question",
                "focus_area": "rent_increase_type",
                "target_fields": ["rent_increase_type"],
                "question_text": "How would you like the annual rent increase to be calculated?",
                "suggestion_chips": [
                    {"label": "📈 % of Rent", "value": "% of Rent"},
                    {"label": "💵 Fixed Increase", "value": "Fixed Increase"},
                ],
            }

        # 3.3. Rent Escalation Value
        if not state.get_value("increase_percent"):
            inc_type = (state.get_value("rent_increase_type") or "% of rent").lower()
            if "fixed" in inc_type:
                # Dynamic calculation based on monthly rent: 5%, 7.5%, 10%
                rent_val = state.get_value("monthly_rent")
                rent_num = 20000
                try:
                    rent_num = int(str(rent_val).replace(",", "").replace("₹", "").strip())
                except Exception:
                    pass

                v5 = int(round((rent_num * 0.05) / 100) * 100)
                v75 = int(round((rent_num * 0.075) / 100) * 100)
                v10 = int(round((rent_num * 0.10) / 100) * 100)

                return {
                    "type": "question",
                    "focus_area": "rent_increase_value",
                    "target_fields": ["increase_percent"],
                    "question_text": f"What is the fixed annual rent increase amount? (Suggestions based on ₹{rent_num:,} rent)",
                    "suggestion_chips": [
                        {"label": f"₹{v5:,} (5%)", "value": f"₹{v5:,} Fixed Increase"},
                        {"label": f"₹{v75:,} (7.5%)", "value": f"₹{v75:,} Fixed Increase"},
                        {"label": f"₹{v10:,} (10%)", "value": f"₹{v10:,} Fixed Increase"},
                    ],
                }
            else:
                return {
                    "type": "question",
                    "focus_area": "rent_increase_value",
                    "target_fields": ["increase_percent"],
                    "question_text": "What percentage should rent increase on annual renewal?",
                    "suggestion_chips": [
                        {"label": "5%", "value": "5%"},
                        {"label": "5% - 10% (Most Used)", "value": "5-10%"},
                        {"label": "10%", "value": "10%"},
                    ],
                }

        # 4. Missing Start Date
        if "agreement_start_date" in missing_keys:
            now = datetime.now()
            if now.month == 12:
                next_month_dt = datetime(now.year + 1, 1, 1)
            else:
                next_month_dt = datetime(now.year, now.month + 1, 1)
            next_month_str = next_month_dt.strftime("%d-%m-%Y")
            today_str = now.strftime("%d-%m-%Y")

            return {
                "type": "question",
                "focus_area": "dates",
                "target_fields": ["agreement_start_date"],
                "question_text": "When will the agreement start?",
                "suggestion_chips": [
                    {"label": f"📅 1st of next month ({next_month_str})", "value": f"Start from {next_month_str}"},
                    {"label": f"📅 Today ({today_str})", "value": f"Start from {today_str}"},
                ],
            }

        # 5. Missing Tenure / Duration
        if not state.get_value("tenure_months"):
            return {
                "type": "question",
                "focus_area": "duration",
                "target_fields": ["tenure_months"],
                "question_text": "What is the duration of the agreement?",
                "suggestion_chips": [
                    {"label": "🗓️ 11 Months (Standard)", "value": "11 Months"},
                    {"label": "🗓️ 6 Months", "value": "6 Months"},
                    {"label": "🗓️ 12 Months (1 Year)", "value": "12 Months"},
                    {"label": "🗓️ 5 Months (Short Stay)", "value": "5 Months"},
                ],
            }

        # 6. Recommended: Notice Period
        if not state.get_value("notice_period"):
            default_notice = "2 Months" if state.jurisdiction.upper() == "MH" else "1 Month"
            return {
                "type": "question",
                "focus_area": "notice",
                "target_fields": ["notice_period"],
                "question_text": f"What notice period should be required before vacating? (Commonly {default_notice})",
                "suggestion_chips": [
                    {"label": "1 Month (Standard)", "value": "1 Month notice period"},
                    {"label": "2 Months", "value": "2 Months notice period"},
                    {"label": "3 Months", "value": "3 Months notice period"},
                ],
            }

        # 7. Optional Protections: Lock-in Period
        if not state.get_value("lockin") and not state.get_value("lockin_months"):
            return {
                "type": "question",
                "focus_area": "lockin",
                "target_fields": ["lockin_months"],
                "question_text": "Would you like to add a Lock-in Period (minimum stay duration)?",
                "info_tip": {
                    "title": "What is a Lock-in Period?",
                    "content": "It is a minimum stay guarantee. During the lock-in months, neither the owner can ask the tenant to leave, nor can the tenant vacate (otherwise deposit penalty applies).\n\nAfter the lock-in ends, either party can exit anytime with standard notice."
                },
                "suggestion_chips": [
                    {"label": "🚫 No Lock-in (Exit anytime with notice)", "value": "No lock-in period"},
                    {"label": "🔒 6 Months Lock-in (Standard practice)", "value": "6 months lock-in period"},
                    {"label": "🔒 3 Months Lock-in (Short guarantee)", "value": "3 months lock-in period"},
                    {"label": "🔒 Full 11 Months", "value": "11 months lock-in period"},
                ],
            }

        # 8. Property Inventory / Fittings & Fixtures Annexure
        if "annexure" not in (state.fields or {}) and state.get_value("annexure") is None:
            return {
                "type": "question",
                "focus_area": "annexure",
                "target_fields": ["annexure"],
                "question_text": "Would you like to attach a Property Inventory / Fixtures list (Annexure)?",
                "info_tip": {
                    "title": "What is an Inventory Annexure?",
                    "content": "An Annexure lists all electrical fittings, appliances, and furniture provided with the property. It helps prevent deposit disputes at the time of vacating."
                },
                "suggestion_chips": [
                    {"label": "🛋️ Semi-Furnished", "value": "Semi-Furnished", "action": "select_furnishing", "furnishing_type": "Semi-Furnished"},
                    {"label": "🛋️ Fully Furnished", "value": "Fully Furnished", "action": "select_furnishing", "furnishing_type": "Fully Furnished"},
                    {"label": "🏢 Unfurnished", "value": "Unfurnished", "action": "select_furnishing", "furnishing_type": "Unfurnished"},
                ],
            }

        # If everything is answered, return ready state
        return {
            "type": "ready",
            "focus_area": "review",
            "target_fields": [],
            "question_text": "🎉 All agreement details have been collected! You can now review the agreement summary or preview the full legal document.",
            "suggestion_chips": [
                {"label": "📄 Preview Full Document", "action": "preview_document"},
                {"label": "🚀 Download Agreement", "action": "generate_agreement"},
            ],
        }

    @classmethod
    def apply_auto_calculations(cls, state: AgreementState) -> List[str]:
        """
        Applies deterministic calculations with system_calculated provenance.
        - Computes rent and deposit in words.
        - Computes end date from start date and tenure.
        """
        calculated = []

        # 1. Rent in words
        rent = state.get_value("monthly_rent")
        if rent and not state.get_value("monthly_rent_words"):
            words = num_to_words(rent)
            state.set_field("monthly_rent_words", words, source=ProvenanceSource.SYSTEM_CALCULATED)
            calculated.append("monthly_rent_words")

        # 2. Deposit in words
        deposit = state.get_value("security_deposit")
        if deposit and not state.get_value("security_deposit_words"):
            words = num_to_words(deposit)
            state.set_field("security_deposit_words", words, source=ProvenanceSource.SYSTEM_CALCULATED)
            calculated.append("security_deposit_words")

        # 3. Auto-calculate End Date if start date provided (default 11 months or custom tenure)
        start_date_str = state.get_value("agreement_start_date")
        if start_date_str:
            tenure_val = state.get_value("tenure_months", "11")
            try:
                t_months = int(str(tenure_val).strip())
            except Exception:
                t_months = 11

            parsed_start = cls._parse_flexible_date(start_date_str)
            if parsed_start:
                year = parsed_start.year
                month = parsed_start.month + t_months
                if month > 12:
                    year += (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                try:
                    end_dt = datetime(year, month, parsed_start.day) - timedelta(days=1)
                except ValueError:
                    end_dt = datetime(year, month, 28)
                end_str = end_dt.strftime("%d-%m-%Y")
                if not state.get_value("agreement_end_date"):
                    state.set_field("agreement_end_date", end_str, source=ProvenanceSource.SYSTEM_CALCULATED)
                    calculated.append("agreement_end_date")

        # 4. Auto-calculate Lock-in End Date & Penalty Deduction
        lockin_months_val = state.get_value("lockin_months")
        if lockin_months_val and str(lockin_months_val).strip() not in ("0", ""):
            try:
                l_months = int(re.sub(r'[^\d]', '', str(lockin_months_val)))
            except Exception:
                l_months = 0

            if l_months > 0:
                state.set_field("lockin", "Y", source=ProvenanceSource.SYSTEM_CALCULATED)
                if start_date_str:
                    parsed_start = cls._parse_flexible_date(start_date_str)
                    if parsed_start:
                        year = parsed_start.year
                        month = parsed_start.month + l_months
                        if month > 12:
                            year += (month - 1) // 12
                            month = ((month - 1) % 12) + 1
                        try:
                            l_end_dt = datetime(year, month, parsed_start.day) - timedelta(days=1)
                        except ValueError:
                            l_end_dt = datetime(year, month, 28)
                        l_end_str = l_end_dt.strftime("%d-%m-%Y")
                        state.set_field("lockin_end_date", l_end_str, source=ProvenanceSource.SYSTEM_CALCULATED)
                        calculated.append("lockin_end_date")

                if not state.get_value("penalty_deduction"):
                    state.set_field("penalty_deduction", "30", source=ProvenanceSource.SYSTEM_CALCULATED)
                    calculated.append("penalty_deduction")

        return calculated

    @staticmethod
    def _parse_flexible_date(date_str: str) -> Optional[datetime]:
        """Parses various date formats commonly entered by users."""
        if not date_str:
            return None
        cleaned = str(date_str).strip()
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None
