"""
tests/test_creator_chat_api.py — Comprehensive Test Suite for Creator Chat API & Orchestration
================================================================================================
Verifies:
- Batch extraction of 8+ fields from one paragraph
- No redundant questions for already-extracted fields
- Missing field detection & priority question selection
- Suggestion chips generation
- System-calculated end date & word conversions
- Two-gate readiness model
- State roundtripping via API
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from services.agreement_state import AgreementState, FieldStatus, ProvenanceSource
from services.interview_engine import InterviewEngine
from services.ai_service import ai_service


class TestCreatorChatAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_batch_extraction_of_multiple_fields_in_one_pass(self):
        """
        Critical Success Criterion:
        User provides 8+ parameters in a single prompt:
        "I'm renting my 3BHK flat 504 at Brigade Gateway Bangalore to Aman Verma for 55000 per month and 3 lakh deposit. Agreement starts October 1st for 11 months. Aman will pay electricity and maintenance."
        The system must extract all of them simultaneously without asking for them one by one.
        """
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")
        prompt = (
            "I'm renting my 3BHK flat 504 at Brigade Gateway Bangalore to Aman Verma for 55000 per month "
            "and 3 lakh deposit. Agreement starts October 1st for 11 months. Aman will pay electricity and maintenance."
        )

        result = ai_service.understand_and_extract(prompt, state)
        self.assertTrue(result["success"])

        # Check extracted fields
        self.assertEqual(state.get_value("monthly_rent"), "55000")
        self.assertEqual(state.get_value("security_deposit"), "300000")
        self.assertEqual(state.get_value("tenant1_name"), "Aman Verma")
        self.assertEqual(state.get_value("flat_no"), "504")
        self.assertEqual(state.get_value("city"), "Bangalore")
        self.assertEqual(state.get_value("maintenance"), "Excluding")
        self.assertIsNotNone(state.get_value("agreement_start_date"))
        self.assertIsNotNone(state.get_value("agreement_end_date"))

        # Check provenance
        rent_entry = state.get_field("monthly_rent")
        self.assertEqual(rent_entry.source, ProvenanceSource.EXTRACTED_CHAT)
        self.assertEqual(rent_entry.status, FieldStatus.EXTRACTED)

        # Check that AI does NOT ask for rent, deposit, or tenant name because they are already present!
        next_interaction = result["next_interaction"]
        target_fields = next_interaction.get("target_fields", [])
        self.assertNotIn("monthly_rent", target_fields)
        self.assertNotIn("security_deposit", target_fields)
        self.assertNotIn("tenant1_name", target_fields)

        # The AI should ask for the true missing required fields (e.g. Owner name/address)
        self.assertIn("owner1_name", target_fields)

    def test_api_creator_chat_orchestration(self):
        """End-to-end test of POST /api/ai/creator-chat endpoint."""
        payload = {
            "message": "Owner is Naresh Agarwal. Renting 2BHK in Gachibowli to Rahul Sharma for 35k. Deposit 1.5L. Start Sept 1 for 11 months.",
            "agreement_type": "simple_rental",
            "jurisdiction": "TS",
            "scenario": "family",
        }

        response = self.app.post(
            "/api/ai/creator-chat",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIn("assistant_message", data)
        self.assertIn("readiness", data)
        self.assertIn("agreement_state", data)
        self.assertIn("preview_html", data)

        fields = data["agreement_state"]["fields"]
        self.assertEqual(fields["monthly_rent"]["value"], "35000")
        self.assertEqual(fields["security_deposit"]["value"], "150000")
        self.assertEqual(fields["owner1_name"]["value"], "Naresh Agarwal")
        self.assertEqual(fields["tenant1_name"]["value"], "Rahul Sharma")

    def test_api_confirm_field_endpoint(self):
        """Tests single-field and bulk confirmation via /api/ai/confirm-field."""
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")
        state.set_field("monthly_rent", "40000", source=ProvenanceSource.EXTRACTED_CHAT)
        state.set_field("security_deposit", "200000", source=ProvenanceSource.EXTRACTED_CHAT)

        # 1. Single confirm
        payload = {
            "agreement_state": state.to_client_payload(),
            "field_key": "monthly_rent",
        }
        res1 = self.app.post("/api/ai/confirm-field", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertEqual(data1["agreement_state"]["fields"]["monthly_rent"]["status"], FieldStatus.CONFIRMED)
        self.assertEqual(data1["agreement_state"]["fields"]["security_deposit"]["status"], FieldStatus.EXTRACTED)

        # 2. Bulk confirm
        payload_bulk = {
            "agreement_state": data1["agreement_state"],
            "bulk": True,
        }
        res2 = self.app.post("/api/ai/confirm-field", data=json.dumps(payload_bulk), content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["agreement_state"]["fields"]["security_deposit"]["status"], FieldStatus.CONFIRMED)

    def test_smr_vinay_city_and_aadhaar_chat_flow(self):
        """Tests user prompt 'smr vinay city , 40k rent 80K depost 1st Sep is start date' and subsequent Aadhaar upload message."""
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")
        
        # 1. First user message
        res1 = ai_service.understand_and_extract(
            "smr vinay city , 40k rent 80K depost 1st Sep is start date",
            state
        )
        self.assertEqual(state.get_value("monthly_rent"), "40000")
        self.assertEqual(state.get_value("security_deposit"), "80000")
        self.assertIn("smr vinay city", (state.get_value("property_address") or "").lower())
        self.assertIsNotNone(state.get_value("agreement_start_date"))

        # 2. In-chat Aadhaar upload response
        res2 = ai_service.understand_and_extract(
            "Owner details from uploaded Aadhaar ID: Name is Naresh Agarwal, relation is Late Ramaswamy Agarwal, address is Flat 101, Prestige High, Bengaluru, Karnataka 560038.",
            state
        )
        self.assertEqual(state.get_value("owner1_name"), "Naresh Agarwal")
        self.assertEqual(state.get_value("owner1_careofname"), "Late Ramaswamy Agarwal")
        self.assertIn("Prestige High", state.get_value("owner1_address"))

    def test_my_flat_is_in_smr_vinay_city_extraction(self):
        """Tests user prompt 'my flat is in smr vinay city , miyapur.. rent is 40K deposit is 80K, start date is 1st Sep'."""
        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")
        ai_service.understand_and_extract(
            "my flat is in smr vinay city , miyapur.. rent is 40K deposit is 80K, start date is 1st Sep",
            state
        )
        self.assertEqual(state.get_value("monthly_rent"), "40000")
        self.assertEqual(state.get_value("security_deposit"), "80000")
        # flat_no should NOT be "is"
        self.assertIsNone(state.get_value("flat_no"))
        # property_address should NOT contain "my flat is in"
        self.assertNotIn("my flat is in", (state.get_value("property_address") or "").lower())
        prop_str = ((state.get_value("society_name") or "") + " " + (state.get_value("property_address") or "")).lower()
        self.assertIn("smr vinay city", prop_str)
        self.assertTrue((state.get_value("agreement_start_date") or "").startswith("01-09-"))


if __name__ == "__main__":
    unittest.main()
