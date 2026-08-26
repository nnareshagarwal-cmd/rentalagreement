"""
tests/test_leegality_service.py — Unit and Integration Tests for Leegality eSign
==============================================================================
Tests:
  - Invitee extraction from form payload
  - Phone normalization logic
  - Webhook HMAC signature verification
  - Flask API endpoint dispatch (/api/rental/request-esign)
  - Live Leegality Sandbox API integration
"""

import unittest
import json
from unittest.mock import patch, MagicMock

from services.leegality_service import LeegalityService, LeegalityError
from app import app


class TestLeegalityService(unittest.TestCase):
    def setUp(self):
        self.service = LeegalityService()
        self.client = app.test_client()

    def test_phone_normalization(self):
        """Test Indian mobile number normalization to 10 digits."""
        self.assertEqual(self.service._clean_phone("9876543210"), "9876543210")
        self.assertEqual(self.service._clean_phone("+91 98765 43210"), "9876543210")
        self.assertEqual(self.service._clean_phone("09876543210"), "9876543210")
        self.assertEqual(self.service._clean_phone("919876543210"), "9876543210")
        self.assertEqual(self.service._clean_phone(""), "")
        self.assertEqual(self.service._clean_phone(None), "")

    def test_extract_invitees(self):
        """Test extraction of Lessors (owners) and Lessees (tenants) from agreement payload."""
        sample_data = {
            "owner1_name": "Ramesh Gupta",
            "owner1_email": "ramesh@example.com",
            "owner1_phone": "9876543210",
            "tenant1_name": "Suresh Patel",
            "tenant1_email": "suresh@example.com",
            "tenant1_phone": "9123456789",
            "owner2_name": "Pooja Gupta",
            "owner2_email": "pooja@example.com",
            "owner2_phone": "9999988888"
        }

        invitees = self.service.extract_invitees(sample_data)
        self.assertEqual(len(invitees), 3)

        self.assertEqual(invitees[0]["name"], "Ramesh Gupta")
        self.assertEqual(invitees[0]["email"], "ramesh@example.com")
        self.assertEqual(invitees[0]["phone"], "9876543210")
        self.assertEqual(invitees[0]["role"], "OWNER")

        self.assertEqual(invitees[1]["name"], "Pooja Gupta")
        self.assertEqual(invitees[1]["role"], "OWNER")

        self.assertEqual(invitees[2]["name"], "Suresh Patel")
        self.assertEqual(invitees[2]["role"], "TENANT")

    def test_webhook_mac_verification(self):
        """Test HMAC MAC signature verification for incoming webhooks."""
        import hmac
        import hashlib

        salt = self.service.private_salt or "test_salt"
        self.service.private_salt = salt

        raw_payload = b'{"documentId": "DOC123", "status": "COMPLETED"}'
        valid_mac = hmac.new(salt.encode('utf-8'), raw_payload, hashlib.sha256).hexdigest()

        self.assertTrue(self.service.verify_webhook_mac(raw_payload, valid_mac))
        self.assertFalse(self.service.verify_webhook_mac(raw_payload, "invalid_mac_hash"))

    @patch("clauses.pdf_renderer.generate_pdf")
    @patch("requests.post")
    def test_initiate_esign_success_mock(self, mock_post, mock_pdf):
        """Test initiate_esign with mocked Leegality response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "data": {
                "documentId": "TEST_DOC_999",
                "irn": "AGR-TEST-1",
                "invitees": [
                    {
                        "name": "Owner 1",
                        "email": "owner@example.com",
                        "phone": "9876543210",
                        "signUrl": "https://sandbox.leegality.com/sign/abc123",
                        "active": True
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        # Mock PDF file generation
        def fake_pdf(data, output_path=None):
            with open(output_path, 'wb') as f:
                f.write(b"%PDF-1.4 mock pdf content")
            return output_path

        mock_pdf.side_effect = fake_pdf

        data = {
            "owner1_name": "Owner 1",
            "owner1_email": "owner@example.com",
            "owner1_phone": "9876543210",
            "monthly_rent": "25000",
            "security_deposit": "50000"
        }

        res = self.service.initiate_esign(data)
        self.assertTrue(res["success"])
        self.assertEqual(res["document_id"], "TEST_DOC_999")
        self.assertEqual(len(res["invitees"]), 1)
        self.assertEqual(res["invitees"][0]["signUrl"], "https://sandbox.leegality.com/sign/abc123")

    def test_flask_endpoint_request_esign_validation(self):
        """Test validation error when no signers are provided to endpoint."""
        res = self.client.post(
            "/api/rental/request-esign",
            data=json.dumps({}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        body = res.get_json()
        self.assertFalse(body["success"])

    def test_live_leegality_sandbox_flow(self):
        """Live sandbox verification test with the user's active sandbox profile."""
        if not self.service.is_configured():
            self.skipTest("Leegality API not configured")

        sample_agreement = {
            "owner1_name": "Sandesh Sharma",
            "owner1_email": "sandesh.sharma@example.com",
            "owner1_phone": "9876543210",
            "tenant1_name": "Ananya Roy",
            "tenant1_email": "ananya.roy@example.com",
            "tenant1_phone": "9123456789",
            "monthly_rent": "30000",
            "monthly_rent_words": "Rupees Thirty Thousand Only",
            "security_deposit": "60000",
            "security_deposit_words": "Rupees Sixty Thousand Only",
            "agreement_start_date": "2026-09-01",
            "agreement_end_date": "2027-07-31",
            "property_address": "Flat 402, Sunshine Heights, Koramangala, Bengaluru",
            "society_name": "Sunshine Heights"
        }

        res = self.client.post(
            "/api/rental/request-esign",
            data=json.dumps(sample_agreement),
            content_type="application/json"
        )

        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertTrue(bool(body.get("document_id")))
        self.assertGreaterEqual(len(body.get("invitees", [])), 1)

        # Check status query endpoint
        doc_id = body["document_id"]
        status_res = self.client.get(f"/api/rental/esign-status/{doc_id}")
        self.assertEqual(status_res.status_code, 200)
        status_body = status_res.get_json()
        self.assertTrue(status_body["success"])
        self.assertEqual(status_body["document_id"], doc_id)

    @patch("clauses.pdf_renderer.generate_pdf")
    @patch("requests.post")
    def test_dynamic_verification_payload_construction(self, mock_post, mock_pdf):
        """Test dynamic injection of photo capture, liveness, face auth, and GPS into Leegality payload."""
        def fake_pdf(data, output_path=None):
            with open(output_path, 'wb') as f:
                f.write(b"%PDF-1.4 mock pdf content")
            return output_path

        mock_pdf.side_effect = fake_pdf

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "data": {"documentId": "DOC_DYNAMIC_1", "invitees": [{"name": "Landlord", "signUrl": "url1"}]}
        }
        mock_post.return_value = mock_response

        # 1. Enabled dynamic flags
        data_enabled = {
            "owner1_name": "Landlord",
            "owner1_phone": "9876543210",
            "capture_photo": True,
            "smart_liveliness": True,
            "liveliness_retries": 4,
            "enable_face_auth": True,
            "enable_gps": True
        }

        self.service.initiate_esign(data_enabled)
        called_payload = mock_post.call_args[1]["json"]

        self.assertTrue(called_payload["invitees"][0]["capturePhoto"])
        self.assertTrue(called_payload["invitees"][0]["userLiveliness"])
        self.assertTrue(called_payload["invitees"][0]["smartUserLivelinessConfig"]["enableSmartUserLiveliness"])
        self.assertEqual(called_payload["invitees"][0]["smartUserLivelinessConfig"]["smartUserLivelinessRetryAttempts"], 4)
        self.assertEqual(called_payload["signatureConfig"]["authTypes"], ["OTP", "FACE"])
        self.assertIn("gpsConfig", called_payload)

        # 2. Disabled dynamic flags
        data_disabled = {
            "owner1_name": "Landlord",
            "owner1_phone": "9876543210",
            "capture_photo": False,
            "enable_face_auth": False,
            "enable_gps": False
        }

        self.service.initiate_esign(data_disabled)
        called_payload_disabled = mock_post.call_args[1]["json"]

        self.assertFalse(called_payload_disabled["invitees"][0].get("capturePhoto", False))
        self.assertNotIn("smartUserLivelinessConfig", called_payload_disabled["invitees"][0])
        self.assertEqual(called_payload_disabled["signatureConfig"]["authTypes"], ["OTP"])
        self.assertNotIn("gpsConfig", called_payload_disabled)

    @patch("clauses.pdf_renderer.generate_pdf")
    @patch("requests.post")
    def test_signature_type_selection(self, mock_post, mock_pdf):
        """Test that AADHAAR, VIRTUAL_SIGN, and ALLOW_EITHER signature types generate correct signatures payload."""
        def fake_pdf(data, output_path=None):
            with open(output_path, 'wb') as f:
                f.write(b"%PDF-1.4 mock pdf content")
            return output_path

        mock_pdf.side_effect = fake_pdf

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "data": {"documentId": "DOC_SIG_1", "invitees": [{"name": "Lessor", "signUrl": "url1"}]}
        }
        mock_post.return_value = mock_response

        # Test AADHAAR signature type
        custom_invitees_aadhaar = [
            {"name": "Owner 1", "phone": "9876543210", "role": "OWNER", "signType": "AADHAAR"}
        ]
        self.service.initiate_esign({}, custom_invitees=custom_invitees_aadhaar)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["invitees"][0]["signatures"], [{"type": "AADHAAR"}])

        # Test VIRTUAL_SIGN signature type
        custom_invitees_virtual = [
            {"name": "Tenant 1", "email": "tenant@example.com", "role": "TENANT", "signType": "VIRTUAL_SIGN"}
        ]
        self.service.initiate_esign({}, custom_invitees=custom_invitees_virtual)
        payload_virtual = mock_post.call_args[1]["json"]
        self.assertEqual(payload_virtual["invitees"][0]["signatures"], [{"type": "VIRTUAL_SIGN"}])

        # Test ALLOW_EITHER signature type
        custom_invitees_either = [
            {"name": "Owner 2", "phone": "9988776655", "role": "OWNER", "signType": "ALLOW_EITHER"}
        ]
        self.service.initiate_esign({}, custom_invitees=custom_invitees_either)
        payload_either = mock_post.call_args[1]["json"]
        self.assertEqual(payload_either["invitees"][0]["signatures"], [{"type": "AADHAAR"}, {"type": "VIRTUAL_SIGN"}])

    @patch("clauses.pdf_renderer.generate_pdf")
    @patch("requests.post")
    def test_dynamic_signature_placement_auto(self, mock_post, mock_pdf):
        """Test that default auto-placement places Owners on Left and Tenants on Right with staggered Y."""
        def fake_pdf(data, output_path=None):
            with open(output_path, 'wb') as f:
                f.write(b"%PDF-1.4 mock pdf content")
            return output_path

        mock_pdf.side_effect = fake_pdf

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "data": {"documentId": "DOC_PLACE_1", "invitees": [{"name": "Owner 1", "signUrl": "url1"}]}
        }
        mock_post.return_value = mock_response

        # Multi-party: 2 Owners, 2 Tenants
        custom_invitees = [
            {"name": "Owner 1", "phone": "9876543210", "role": "OWNER"},
            {"name": "Owner 2", "phone": "9876543211", "role": "OWNER"},
            {"name": "Tenant 1", "phone": "9876543212", "role": "TENANT"},
            {"name": "Tenant 2", "phone": "9876543213", "role": "TENANT"}
        ]

        self.service.initiate_esign({"enable_auto_placement": True}, custom_invitees=custom_invitees)
        payload = mock_post.call_args[1]["json"]
        invitees = payload["invitees"]

        # Owner 1 (Left column, slot 0): x1=45, x2=245, y1=120, y2=175
        self.assertEqual(invitees[0]["appearances"], [{"page": "L", "x1": 45, "y1": 120, "x2": 245, "y2": 175}])
        # Owner 2 (Left column, slot 1): x1=45, x2=245, y1=195, y2=250
        self.assertEqual(invitees[1]["appearances"], [{"page": "L", "x1": 45, "y1": 195, "x2": 245, "y2": 250}])
        # Tenant 1 (Right column, slot 0): x1=345, x2=545, y1=120, y2=175
        self.assertEqual(invitees[2]["appearances"], [{"page": "L", "x1": 345, "y1": 120, "x2": 545, "y2": 175}])
        # Tenant 2 (Right column, slot 1): x1=345, x2=545, y1=195, y2=250
        self.assertEqual(invitees[3]["appearances"], [{"page": "L", "x1": 345, "y1": 195, "x2": 545, "y2": 250}])

    @patch("clauses.pdf_renderer.generate_pdf")
    @patch("requests.post")
    def test_dynamic_signature_placement_custom(self, mock_post, mock_pdf):
        """Test that explicit custom appearances override auto-placement."""
        def fake_pdf(data, output_path=None):
            with open(output_path, 'wb') as f:
                f.write(b"%PDF-1.4 mock pdf content")
            return output_path

        mock_pdf.side_effect = fake_pdf

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "data": {"documentId": "DOC_PLACE_CUSTOM", "invitees": [{"name": "Owner Custom", "signUrl": "url1"}]}
        }
        mock_post.return_value = mock_response

        custom_invitees = [
            {
                "name": "Owner Custom",
                "phone": "9876543210",
                "role": "OWNER",
                "appearances": [{"page": "2", "x1": 100, "y1": 200, "x2": 300, "y2": 260}]
            }
        ]

        self.service.initiate_esign({}, custom_invitees=custom_invitees)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["invitees"][0]["appearances"], [{"page": "2", "x1": 100, "y1": 200, "x2": 300, "y2": 260}])


if __name__ == "__main__":
    unittest.main()

