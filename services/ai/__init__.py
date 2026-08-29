"""
services/ai — AI Subsystem Package
===================================
Modular components for LLM communication, deterministic entity extraction,
and Aadhaar OCR vision/parsing.
"""

from .entity_extractor import EntityExtractor
from .aadhaar_ocr import AadhaarOcrService, AadhaarOcrError
from .gemini_client import GeminiClient

__all__ = ["EntityExtractor", "AadhaarOcrService", "AadhaarOcrError", "GeminiClient"]
