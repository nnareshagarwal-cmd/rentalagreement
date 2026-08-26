"""
tests/test_places_service.py — Unit Tests for Google Places Service & Endpoints
"""

import unittest
import json
from unittest.mock import patch, MagicMock
from app import app
from services.places_service import PlacesService
from services.agreement_state import AgreementState
from services.ai_service import ai_service


class TestPlacesService(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_parse_new_places_response(self):
        """Tests structured component extraction from Google Places API (New) payload."""
        service = PlacesService(api_key="AIzaSyMockKeyForTesting1234567890")

        mock_place = {
            "id": "ChIJ_mock_smr_vinay",
            "displayName": {"text": "SMR Vinay City"},
            "formattedAddress": "SMR Vinay City, Bollaram Rd, Rajiv Gandhi Nagar, Miyapur, Hyderabad, Telangana 500049, India",
            "location": {"latitude": 17.5012, "longitude": 78.3621},
            "addressComponents": [
                {"longText": "SMR Vinay City", "shortText": "SMR Vinay City", "types": ["premise"]},
                {"longText": "Bollaram Road", "shortText": "Bollaram Rd", "types": ["route"]},
                {"longText": "Rajiv Gandhi Nagar", "shortText": "Rajiv Gandhi Nagar", "types": ["sublocality_level_1"]},
                {"longText": "Miyapur", "shortText": "Miyapur", "types": ["locality"]},
                {"longText": "Hyderabad", "shortText": "Hyderabad", "types": ["administrative_area_level_2"]},
                {"longText": "Telangana", "shortText": "TS", "types": ["administrative_area_level_1"]},
                {"longText": "500049", "shortText": "500049", "types": ["postal_code"]},
                {"longText": "India", "shortText": "IN", "types": ["country"]},
            ]
        }

        parsed = service._parse_new_place_result(mock_place)
        self.assertEqual(parsed["society_name"], "SMR Vinay City")
        self.assertEqual(parsed["city"], "Miyapur")  # or Hyderabad
        self.assertEqual(parsed["state"], "Telangana")
        self.assertEqual(parsed["state_code"], "TS")
        self.assertEqual(parsed["pincode"], "500049")
        self.assertIn("500049", parsed["property_address"])
        self.assertEqual(parsed["source"], "google_places")

    def test_places_cache_behavior(self):
        """Tests that repeated queries use the in-memory cache and don't make duplicate requests."""
        service = PlacesService(api_key="AIzaSyMockKeyForTesting1234567890")

        with patch.object(service, '_search_places_new') as mock_search:
            mock_search.return_value = {
                "society_name": "Brigade Gateway",
                "property_address": "Brigade Gateway, Malleshwaram, Bengaluru, Karnataka 560055",
                "city": "Bengaluru",
                "pincode": "560055",
                "state": "Karnataka",
            }

            # 1. First call -> hits search method
            res1 = service.search_and_resolve("Brigade Gateway Malleshwaram")
            self.assertIsNotNone(res1)
            self.assertEqual(res1["society_name"], "Brigade Gateway")
            self.assertEqual(mock_search.call_count, 1)

            # 2. Second call with same query -> returns from cache, search NOT called again
            res2 = service.search_and_resolve("Brigade Gateway Malleshwaram")
            self.assertIsNotNone(res2)
            self.assertEqual(res2["society_name"], "Brigade Gateway")
            self.assertEqual(mock_search.call_count, 1)

    def test_unconfigured_places_service_graceful_fallback(self):
        """Tests that service gracefully returns None/empty list when no API key is set."""
        service = PlacesService(api_key="")
        self.assertFalse(service.is_configured())
        self.assertIsNone(service.search_and_resolve("smr vinay city"))
        self.assertEqual(service.autocomplete("smr vinay"), [])

    @patch("services.places_service.places_service.search_and_resolve")
    @patch("services.places_service.places_service.is_configured")
    def test_ai_creator_chat_places_enrichment(self, mock_is_conf, mock_resolve):
        """Tests that understand_and_extract enriches property address and PIN code via PlacesService."""
        mock_is_conf.return_value = True
        mock_resolve.return_value = {
            "society_name": "SMR Vinay City",
            "property_address": "SMR Vinay City, Bollaram Road, Miyapur, Hyderabad, Telangana 500049",
            "city": "Hyderabad",
            "pincode": "500049",
            "state": "Telangana",
        }

        state = AgreementState(agreement_type="simple_rental", jurisdiction="KA")
        result = ai_service.understand_and_extract(
            "my flat is in smr vinay city , miyapur.. rent is 40K deposit is 80K, start date is 1st Sep",
            state
        )

        self.assertEqual(state.get_value("monthly_rent"), "40000")
        self.assertEqual(state.get_value("security_deposit"), "80000")
        self.assertEqual(state.get_value("society_name"), "SMR Vinay City")
        self.assertIn("500049", state.get_value("property_address"))
        self.assertEqual(state.get_value("pincode"), "500049")
        self.assertIn("500049", result["assistant_message"])

    def test_places_api_endpoints(self):
        """Tests /api/places/autocomplete and /api/places/resolve endpoints."""
        # 1. Autocomplete endpoint with short query returns empty list
        res_ac = self.app.get("/api/places/autocomplete?query=a")
        self.assertEqual(res_ac.status_code, 200)
        data_ac = res_ac.get_json()
        self.assertTrue(data_ac["success"])
        self.assertEqual(data_ac["suggestions"], [])

        # 2. Resolve endpoint with empty query
        res_res = self.app.get("/api/places/resolve?query=")
        self.assertEqual(res_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
