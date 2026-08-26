"""
tests/test_interview_engine.py — Unit Tests for Agreement State & Interview Decision Engine
=============================================================================================
Tests provenance tracking, two-gate completion lifecycle, scenario rules, and auto-calculations.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agreement_state import AgreementState, FieldEntry, FieldStatus, ProvenanceSource
from services.interview_engine import InterviewEngine, FieldCategory
from clauses.agreement_renderer import generate_preview_html


class TestAgreementState(unittest.TestCase):
    def test_field_provenance_and_lifecycle(self):
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")

        # 1. Extracted from chat
        entry = state.set_field("monthly_rent", "35000", source=ProvenanceSource.EXTRACTED_CHAT, confidence=0.95)
        self.assertEqual(entry.status, FieldStatus.EXTRACTED)
        self.assertEqual(entry.source, ProvenanceSource.EXTRACTED_CHAT)
        self.assertEqual(entry.confidence, 0.95)
        self.assertIsNone(entry.confirmed_at)

        # 2. Confirm field
        confirmed = state.confirm_field("monthly_rent")
        self.assertTrue(confirmed)
        self.assertEqual(state.get_field("monthly_rent").status, FieldStatus.CONFIRMED)
        self.assertEqual(state.get_field("monthly_rent").source, ProvenanceSource.USER_CONFIRMED)
        self.assertIsNotNone(state.get_field("monthly_rent").confirmed_at)

    def test_flat_dict_compatibility_with_clause_renderer(self):
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")
        state.set_field("owner1_name", "Naresh Agarwal", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_name", "Rahul Sharma", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("monthly_rent", "35000", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("security_deposit", "150000", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("property_address", "Flat 302, Green Acres, Indiranagar, Bengaluru", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("agreement_start_date", "01-09-2026", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("today_date", "15-08-2026", source=ProvenanceSource.USER_EXPLICIT)

        InterviewEngine.apply_auto_calculations(state)
        flat_dict = state.to_flat_dict()

        self.assertIn("monthly_rent_words", flat_dict)
        self.assertIn("RUPEES THIRTY FIVE THOUSAND ONLY", flat_dict["monthly_rent_words"])
        self.assertIn("agreement_end_date", flat_dict)

        # Render preview HTML using flat dict
        html = generate_preview_html(flat_dict)
        self.assertIn("Naresh Agarwal", html)
        self.assertIn("Rahul Sharma", html)
        self.assertIn("35000", html)


class TestInterviewEngine(unittest.TestCase):
    def test_scenario_aware_rules(self):
        # 1. Simple rental in Karnataka
        rules_ka = InterviewEngine.get_field_rules("simple_rental", "KA", "family")
        self.assertEqual(rules_ka["monthly_rent"]["category"], FieldCategory.REQUIRED)
        self.assertEqual(rules_ka["notice_period"]["default"], "1 Month")

        # 2. Leave & License in Maharashtra
        rules_mh = InterviewEngine.get_field_rules("leave_license", "MH", "family")
        self.assertEqual(rules_mh["notice_period"]["default"], "2 Months")
        self.assertEqual(rules_mh["society_name"]["category"], FieldCategory.REQUIRED)

        # 3. Bachelor scenario
        rules_bachelor = InterviewEngine.get_field_rules("simple_rental", "KA", "bachelor")
        self.assertEqual(rules_bachelor["tenant_poc"]["category"], FieldCategory.REQUIRED)

    def test_two_gate_readiness_model(self):
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")

        # Initially 0 required fields complete
        r0 = InterviewEngine.evaluate_readiness(state)
        self.assertFalse(r0["ready_for_review"])
        self.assertFalse(r0["ready_for_generation"])
        self.assertGreater(r0["missing_count"], 5)

        # Populate all required fields as EXTRACTED
        field_rules = InterviewEngine.get_field_rules("simple_rental", "KA", "family")
        required_keys = [k for k, v in field_rules.items() if v.get("category") == FieldCategory.REQUIRED]

        for k in required_keys:
            state.set_field(k, "Sample Value", source=ProvenanceSource.EXTRACTED_CHAT)

        r1 = InterviewEngine.evaluate_readiness(state)
        # Gate 1 passes: All required are extracted, ready for review
        self.assertTrue(r1["ready_for_review"])
        # Gate 2 fails: Extracted != Confirmed yet
        self.assertFalse(r1["ready_for_generation"])
        self.assertEqual(len(r1["required_needs_confirmation"]), len(required_keys))

        # Confirm all required fields
        state.bulk_confirm()
        r2 = InterviewEngine.evaluate_readiness(state)
        # Gate 2 passes: Everything confirmed
        self.assertTrue(r2["ready_for_review"])
        self.assertTrue(r2["ready_for_generation"])
        self.assertEqual(len(r2["required_needs_confirmation"]), 0)

    def test_next_interaction_planner(self):
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")

        # Step 1: Empty state -> should ask for Owner Name / Parties first
        plan1 = InterviewEngine.plan_next_interaction(state)
        self.assertIn("owner", plan1["focus_area"])
        self.assertIn("owner1_name", plan1["target_fields"])

        # Fill Owner
        state.set_field("owner1_name", "Naresh Agarwal", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("owner1_age", "35", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("owner1_careofname", "Suresh Agarwal", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("owner1_address", "Indiranagar, Bengaluru", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("owner1_occupation", "PRIVATE EMPLOYEE", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("owner1_phone", "9876543210", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("owner1_email", "naresh@example.com", source=ProvenanceSource.USER_EXPLICIT)

        # Step 2: Should ask for Tenant
        plan2 = InterviewEngine.plan_next_interaction(state)
        self.assertIn("tenant", plan2["focus_area"])
        self.assertIn("tenant1_name", plan2["target_fields"])

        # Fill Tenant & Property
        state.set_field("tenant1_name", "Rahul Sharma", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_age", "28", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_careofname", "Ramesh Sharma", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_address", "HSR Layout, Bengaluru", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_occupation", "PRIVATE EMPLOYEE", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_phone", "9876543211", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("tenant1_email", "rahul@example.com", source=ProvenanceSource.USER_EXPLICIT)
        state.set_field("property_address", "Flat 302, Green Acres", source=ProvenanceSource.USER_EXPLICIT)

        # Step 3: Should ask for Financials with chips
        plan3 = InterviewEngine.plan_next_interaction(state)
        self.assertEqual(plan3["focus_area"], "financial")
        self.assertGreater(len(plan3["suggestion_chips"]), 0)


if __name__ == "__main__":
    unittest.main()
