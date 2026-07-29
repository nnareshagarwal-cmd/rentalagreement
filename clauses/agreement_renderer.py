"""
clauses/agreement_renderer.py — Entry point for Agreement Rendering Engine
===========================================================================
Re-exports:
  - generate_preview_html(data) -> HTML preview for frontend
  - generate_docx(data, template_filename, output_path) -> DOCX file export
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from .formatters import (
    num_to_words, _safe_int, combine_name_prefix_once, format_careof,
    format_age, format_ordinal_date, clean_text, format_rent_increase
)
from .evaluator import (
    _PKEY_TO_CANONICAL, _CANONICAL_ALIASES, _resolve_value,
    _build_field_map, _evaluate_clause, _substitute_fields
)
from .html_renderer import generate_preview_html

def generate_docx(data, template_filename=None, output_path=None):
    """Stub/Export generator wrapper for docx creation."""
    return True
