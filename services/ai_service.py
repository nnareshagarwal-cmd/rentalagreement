"""
services/ai_service.py — AgreementAI Unified AI Service Facade
==============================================================
Provides a high-level facade for:
  - services.ai.gemini_client: Conversation understanding & legal copilot
  - services.ai.entity_extractor: Deterministic rule-based extraction
  - services.ai.aadhaar_ocr: Digital PDF parsing & Gemini Vision OCR

Maintains full backward compatibility for all existing service consumers.
"""

import logging
from config import Config
from clauses.agreement_renderer import generate_preview_html
from services.agreement_state import AgreementState
from services.ai.aadhaar_ocr import AadhaarOcrService, AadhaarOcrError
from services.ai.entity_extractor import EntityExtractor
from services.ai.gemini_client import GeminiClient

logger = logging.getLogger("AgreementAI_Service")


class AIService:
    """Unified AI service facade combining LLM intelligence, deterministic extraction, and Aadhaar OCR."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.gemini_key = Config.GEMINI_API_KEY
        self._gemini = GeminiClient()
        self._extractor = EntityExtractor()
        self._ocr = AadhaarOcrService()

    def render_clauses_agreement(self, data: dict) -> str:
        """Render complete HTML agreement using exact static clauses from simple_rental or leave_license."""
        agr_type = data.get("agreement_type", "simple_rental")
        data["agreement_type"] = agr_type

        # Supply defaults if missing
        if not data.get("P1") and not data.get("today_date") and not data.get("agreement_date"):
            data["P1"] = "24th day of July 2026"
        if not data.get("P16") and not data.get("agreement_start_date"):
            data["P16"] = "1st day of August 2026"
        if not data.get("P17") and not data.get("agreement_end_date"):
            data["P17"] = "30th day of June 2027"
        if not data.get("P14") and not data.get("rent_amount_words"):
            data["P14"] = "Twenty Five Thousand"
        if not data.get("P20") and not data.get("security_deposit_words"):
            data["P20"] = "One Lakh Fifty Thousand"

        return generate_preview_html(data)

    def review_and_modify_agreement(self, agreement_html: str, user_prompt: str, agreement_type: str = "simple_rental") -> dict:
        """AI Legal Copilot — answers legal questions and modifies agreement clauses."""
        return self._gemini.review_and_modify_agreement(agreement_html, user_prompt, agreement_type)

    def understand_and_extract(self, user_message: str, current_state: AgreementState) -> dict:
        """AI Natural Language Understanding & Extraction Adapter."""
        return self._gemini.understand_and_extract(user_message, current_state)

    def _extract_entities_rule_based(self, text: str, current_state: AgreementState = None) -> dict:
        """High-precision regex/rule-based extractor for Indian rental expressions."""
        return self._extractor.extract_entities_rule_based(text, current_state)

    def _detect_field_updates(self, find_text: str, replace_text: str) -> dict:
        """Server-side fallback: detect which form field was changed based on find/replace text."""
        return self._extractor.detect_field_updates(find_text, replace_text)

    def extract_aadhaar_ocr(self, document_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Extract structured party details from an Aadhaar image or a multi-page PDF."""
        return self._ocr.extract_aadhaar_ocr(document_bytes, mime_type)

    def _parse_digital_aadhaar_text(self, raw_text: str) -> dict:
        """Parse structured Aadhaar attributes directly from digital PDF text stream."""
        return self._ocr._parse_digital_aadhaar_text(raw_text)

    def generate_agreement_draft(self, prompt: str, state_code: str = "KA", template_type: str = "simple_rental") -> dict:
        """Generate agreement draft via mock or AI."""
        return self._gemini._mock_agreement_draft(prompt, state_code, template_type)

    def _mock_agreement_draft(self, prompt: str, state_code: str, agr_type: str) -> dict:
        """Return fallback mock agreement draft."""
        return self._gemini._mock_agreement_draft(prompt, state_code, agr_type)

    def _mock_aadhaar_ocr(self) -> dict:
        """Return fallback mock Aadhaar OCR extraction."""
        return self._ocr._mock_aadhaar_ocr()


ai_service = AIService()
