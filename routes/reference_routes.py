"""
routes/reference_routes.py — Reference data endpoints
=======================================================
Field registry, Google Places proxy, societies, templates,
executives, stamp duty rates.
"""

import logging

from flask import Blueprint, request, jsonify

from database import query_db
from services.places_service import places_service
from field_registry import FIELD_REGISTRY, SECTION_LABELS, SECTION_ORDER

logger = logging.getLogger("AgreementAI")

reference_bp = Blueprint('reference', __name__)


@reference_bp.route('/api/field-registry')
def api_field_registry():
    """
    Returns the complete field registry as JSON.
    The JS form renderer fetches this once on init and uses it to:
      - Render all form fields generically (no hardcoded if/else chains)
      - Know which section each field belongs to
      - Know field types, options, required status, etc.
    """
    return jsonify({
        "fields":        FIELD_REGISTRY,
        "section_labels": SECTION_LABELS,
        "section_order": SECTION_ORDER,
    })


@reference_bp.route('/api/rental/mapping')
@reference_bp.route('/api/mapping')
def api_mapping():
    return jsonify({"mappings": []})


@reference_bp.route('/api/places/autocomplete', methods=['GET'])
def api_places_autocomplete():
    """Returns autocomplete suggestions from Google Places API for address input."""
    query = request.args.get('query', '').strip()
    if not query or len(query) < 2:
        return jsonify({"success": True, "suggestions": []})

    suggestions = places_service.autocomplete(query)
    return jsonify({"success": True, "suggestions": suggestions})


@reference_bp.route('/api/places/resolve', methods=['GET'])
def api_places_resolve():
    """Resolves a society name or place_id into a full structured postal address with PIN code."""
    query = request.args.get('query', '').strip()
    place_id = request.args.get('place_id', '').strip()

    result = None
    if place_id:
        result = places_service.get_place_details(place_id)
    elif query:
        result = places_service.search_and_resolve(query)

    if result:
        return jsonify({"success": True, "place": result})
    return jsonify({"success": False, "error": "Could not resolve place"}), 404


@reference_bp.route('/api/propertymaster/societies')
@reference_bp.route('/api/societies')
def api_societies():
    return jsonify({"societies": []})


@reference_bp.route('/api/templates')
def api_templates():
    return jsonify({
        "templates": [
            "RENTAL_AGREEMENT_SIMPLE_FAMILY_v1.docx",
            "LEAVE_LICENSE_AGREEMENT_FAMILY_v1.docx",
        ]
    })


@reference_bp.route('/api/executives')
def api_executives():
    return jsonify({"executives": []})


@reference_bp.route('/api/stamp-duty/<state_code>', methods=['GET'])
def api_stamp_duty(state_code):
    """Fetch stamp duty rates for a state."""
    rates = query_db(
        "SELECT * FROM agreement.agr_stamp_duty_rates WHERE state_code = %s",
        [state_code.upper()]
    )
    if not rates:
        rates = [{"state_code": state_code, "duty_amount": 200.00, "description": "Standard Stamp Duty"}]
    return jsonify({"success": True, "rates": rates})
