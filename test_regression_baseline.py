"""
test_regression_baseline.py — Phase 0 Regression Baseline Test Suite
=====================================================================
Validates that existing rendering pipelines (HTML preview, DOCX export, Field Registry)
work as expected before building the new AI-First Agreement State and Decision Engine.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clauses.agreement_renderer import generate_preview_html, generate_docx
from field_registry import FIELD_REGISTRY, SECTION_LABELS, SECTION_ORDER


class TestRegressionBaseline(unittest.TestCase):
    def setUp(self):
        self.sample_rental = {
            "agreement_type": "simple_rental",
            "today_date": "15th day of August 2026",
            "agreement_start_date": "1st day of September 2026",
            "agreement_end_date": "31st day of July 2027",
            "owner1_name": "Naresh Agarwal",
            "owner1_age": "45",
            "owner1_careof": "Father Name",
            "owner1_careofname": "Late Ramaswamy Agarwal",
            "owner1_occupation": "Business",
            "owner1_address": "Flat 101, Prestige High, Indiranagar, Bengaluru, Karnataka 560038",
            "tenant1_name": "Rahul Ramesh Sharma",
            "tenant1_age": "30",
            "tenant1_careof": "Father Name",
            "tenant1_careofname": "Ramesh Sharma",
            "tenant1_occupation": "Software Engineer",
            "tenant1_address": "HSR Layout Sector 2, Bengaluru, Karnataka 560102",
            "property_address": "Flat 302, Green Acres Apartment, 10th Main, Indiranagar, Bengaluru 560038",
            "monthly_rent": "35,000",
            "monthly_rent_words": "Thirty Five Thousand",
            "security_deposit": "1,50,000",
            "security_deposit_words": "One Lakh Fifty Thousand",
            "notice_period": "1 Month",
            "lockin_months": "6",
            "penalty_deduction": "60",
            "maintenance": "Including",
            "increase_percent": "5",
        }

        self.sample_leave_license = {
            "agreement_type": "leave_license",
            "today_date": "15th day of August 2026",
            "agreement_start_date": "1st day of September 2026",
            "agreement_end_date": "31st day of July 2027",
            "owner1_name": "Naresh Agarwal",
            "owner1_age": "45",
            "owner1_careof": "Father Name",
            "owner1_careofname": "Late Ramaswamy Agarwal",
            "owner1_occupation": "Business",
            "owner1_address": "Bandra West, Mumbai, Maharashtra 400050",
            "tenant1_name": "Rahul Ramesh Sharma",
            "tenant1_age": "30",
            "tenant1_careof": "Father Name",
            "tenant1_careofname": "Ramesh Sharma",
            "tenant1_occupation": "Software Engineer",
            "tenant1_address": "Andheri East, Mumbai, Maharashtra 400069",
            "property_address": "Flat 804, Sea Breeze Towers, Bandra West, Mumbai 400050",
            "monthly_rent": "45,000",
            "monthly_rent_words": "Forty Five Thousand",
            "security_deposit": "2,00,000",
            "security_deposit_words": "Two Lakhs",
            "notice_period": "2 Months",
            "lockin_months": "6",
            "penalty_deduction": "60",
            "maintenance": "Excluding",
            "increase_percent": "5",
        }

    def test_field_registry_structure(self):
        """Field registry must contain valid field definitions and non-empty section metadata."""
        self.assertGreater(len(FIELD_REGISTRY), 30)
        self.assertGreater(len(SECTION_LABELS), 5)
        self.assertGreater(len(SECTION_ORDER), 5)

        # Essential canonical keys must be present in field registry
        registered_keys = {f["key"] for f in FIELD_REGISTRY}
        essential_keys = [
            "owner1_name", "tenant1_name", "monthly_rent",
            "security_deposit", "notice_period", "agreement_start_date"
        ]
        for key in essential_keys:
            self.assertIn(key, registered_keys, f"Missing critical field in registry: {key}")

    def test_simple_rental_preview_html(self):
        """Simple Rental preview HTML must render preamble, parties, rent, and clauses."""
        html = generate_preview_html(self.sample_rental)
        self.assertIsInstance(html, str)
        self.assertIn("RENTAL AGREEMENT", html.upper())
        self.assertIn("Naresh Agarwal", html)
        self.assertIn("Rahul Ramesh Sharma", html)
        self.assertTrue("35,000" in html or "35000" in html)
        self.assertIn("clause-block", html)

    def test_leave_license_preview_html(self):
        """Leave & License preview HTML must render Licensor/Licensee terminology."""
        html = generate_preview_html(self.sample_leave_license)
        self.assertIsInstance(html, str)
        self.assertIn("LEAVE AND LICENSE", html.upper())
        self.assertIn("Naresh Agarwal", html)
        self.assertIn("Rahul Ramesh Sharma", html)
        self.assertTrue("45,000" in html or "45000" in html)
        self.assertIn("clause-block", html)

    def test_docx_generation(self):
        """DOCX export must create a valid .docx file on disk."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            generate_docx(self.sample_rental, output_path=tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 5000)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
