"""
routes/ai_routes.py — AI Studio endpoints
===========================================
Creator chat, field confirmation, AI review/copilot, draft generation,
and Aadhaar OCR extraction.
"""

import os
import uuid
import hashlib
import logging

from flask import Blueprint, request, jsonify, session, current_app

from extensions import limiter
from services.ai_service import ai_service, AadhaarOcrError
from services.agreement_state import AgreementState, FieldEntry, FieldStatus, ProvenanceSource
from services.interview_engine import InterviewEngine
from clauses.agreement_renderer import generate_preview_html

logger = logging.getLogger("AgreementAI")

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/api/ai/draft', methods=['POST'])
@limiter.limit("10 per minute")
def api_ai_draft():
    """Generate agreement draft via AI (Gemini / AWS Bedrock)."""
    data          = request.json or {}
    prompt        = data.get('prompt', 'Draft standard residential rental agreement')
    state_code    = data.get('state_code', 'KA')
    template_type = data.get('template_type', 'simple_rental')
    draft         = ai_service.generate_agreement_draft(prompt, state_code, template_type)
    return jsonify({"success": True, "data": draft})


@ai_bp.route('/api/ai/creator-chat', methods=['POST'])
@limiter.limit("60 per minute")
def api_ai_creator_chat():
    """
    AI Creator Studio Engine Endpoint.
    Orchestrates: Natural Language Input -> Gemini Extraction -> Agreement State -> Deterministic Engine -> Readiness & Preview.
    """
    data = request.json or {}
    message = data.get('message', '').strip()
    client_state = data.get('agreement_state') or {}
    agreement_type = data.get('agreement_type') or client_state.get('agreement_type', 'simple_rental')
    jurisdiction = data.get('jurisdiction') or client_state.get('jurisdiction', 'KA')
    scenario = data.get('scenario') or client_state.get('scenario', 'family')

    # Reconstruct AgreementState
    if client_state and isinstance(client_state, dict) and client_state.get('fields'):
        state = AgreementState.from_client_payload(client_state)
    elif client_state and isinstance(client_state, dict):
        state = AgreementState.from_flat_dict(client_state)
    else:
        state = AgreementState(agreement_type=agreement_type, jurisdiction=jurisdiction, scenario=scenario)

    state.agreement_type = agreement_type
    state.jurisdiction = jurisdiction
    state.scenario = scenario

    # If message is empty (e.g. init or reload), evaluate readiness and return initial greeting
    if not message:
        InterviewEngine.apply_auto_calculations(state)
        readiness = InterviewEngine.evaluate_readiness(state)
        next_interaction = InterviewEngine.plan_next_interaction(state)
        try:
            preview_html = generate_preview_html(state.to_flat_dict())
        except Exception:
            preview_html = ""

        # Determine template label for a context-aware greeting
        is_leave_license = "leave" in agreement_type.lower() or "license" in agreement_type.lower()
        template_label = "Leave & License Agreement" if is_leave_license else "Rent Agreement"

        # If the user has an existing draft with real values, use a resuming message
        has_existing_fields = any(
            bool(entry.value and str(entry.value).strip())
            for entry in state.fields.values()
        )
        if has_existing_fields:
            init_message = (
                f"👋 **Welcome back!** I've restored your **{template_label}** draft.\n\n"
                "You can continue where you left off — just tell me anything that needs to be added or updated."
            )
        else:
            # Fresh start: Fast-track onboarding
            init_message = (
                f"👋 **Let's create your {template_label}!**\n\n"
                "I just need a few details from you — no forms to fill."
            )
            # Override chips with role selection
            next_interaction = {
                "type": "role_selection",
                "focus_area": "onboarding",
                "target_fields": [],
                "question_text": "",
                "suggestion_chips": [
                    {"label": "🏠 I'm the Owner", "action": "set_role", "value": "I am the Owner / Landlord"},
                    {"label": "👤 I'm the Tenant", "action": "set_role", "value": "I am the Tenant"},
                    {"label": "🏢 I'm a Broker / Agent", "action": "set_role", "value": "I am a Broker or Agent helping both parties"},
                ],
            }

        return jsonify({
            "success": True,
            "assistant_message": init_message,
            "next_interaction": next_interaction,
            "readiness": readiness,
            "newly_extracted_keys": [],
            "calculated_keys": [],
            "agreement_state": state.to_client_payload(),
            "preview_html": preview_html,
        })

    result = ai_service.understand_and_extract(message, state)
    return jsonify(result)


@ai_bp.route('/api/ai/confirm-field', methods=['POST'])
@limiter.limit("120 per minute")
def api_ai_confirm_field():
    """Confirms one or all extracted fields in the agreement state."""
    data = request.json or {}
    client_state = data.get('agreement_state') or {}
    field_key = data.get('field_key')
    bulk = data.get('bulk', False)

    state = AgreementState.from_client_payload(client_state) if client_state.get('fields') else AgreementState.from_flat_dict(client_state)

    if bulk:
        state.bulk_confirm()
    elif field_key:
        state.confirm_field(field_key)

    InterviewEngine.apply_auto_calculations(state)
    readiness = InterviewEngine.evaluate_readiness(state)
    next_interaction = InterviewEngine.plan_next_interaction(state)
    try:
        preview_html = generate_preview_html(state.to_flat_dict())
    except Exception:
        preview_html = ""

    return jsonify({
        "success": True,
        "agreement_state": state.to_client_payload(),
        "readiness": readiness,
        "next_interaction": next_interaction,
        "preview_html": preview_html,
    })


@ai_bp.route('/api/ai/review-chat', methods=['POST'])
@limiter.limit("20 per minute")
def api_ai_review_chat():
    """AI Copilot — answer questions or edit agreement clauses."""
    data            = request.json or {}
    agreement_html  = data.get('agreement_html', '')
    user_prompt     = data.get('prompt', '')
    agreement_type  = data.get('agreement_type', 'simple_rental')
    result          = ai_service.review_and_modify_agreement(agreement_html, user_prompt, agreement_type)
    return jsonify({"success": True, "data": result})


@ai_bp.route('/api/ocr/aadhaar', methods=['POST'])
@limiter.limit("10 per minute")
def api_ocr_aadhaar():
    """Extract party fields from an Aadhaar image or PDF without retaining the source file."""
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({"success": False, "error": "Please select an Aadhaar image or PDF to extract."}), 400

    file        = request.files['file']
    filename    = __import__('werkzeug.utils', fromlist=['secure_filename']).secure_filename(file.filename)
    extension   = os.path.splitext(filename)[1].lower()
    if extension not in {'.jpg', '.jpeg', '.png', '.webp', '.pdf'}:
        return jsonify({"success": False, "error": "Please upload a JPG, PNG, WEBP, or PDF Aadhaar document."}), 400

    mime_type = file.mimetype or ('application/pdf' if extension == '.pdf' else 'image/jpeg')
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    filepath    = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
    try:
        file.save(filepath)
        with open(filepath, 'rb') as f:
            document_bytes = f.read()

        # ── Per-session OCR cache (avoids duplicate API calls on re-upload) ──
        file_hash = hashlib.sha256(document_bytes).hexdigest()
        ocr_cache = session.get('_ocr_cache', {})
        if file_hash in ocr_cache:
            logger.info(f"OCR cache hit for {filename} (hash={file_hash[:12]}…)")
            cached = ocr_cache[file_hash]
            return jsonify({"success": True, "file_name": filename, "extracted": cached, "data": cached, "cached": True})

        try:
            extracted = ai_service.extract_aadhaar_ocr(document_bytes, mime_type)
        except AadhaarOcrError as error:
            return jsonify({"success": False, "error": str(error)}), 422

        # Store in session cache (max 4 entries to limit session size)
        if len(ocr_cache) >= 4:
            oldest_key = next(iter(ocr_cache))
            del ocr_cache[oldest_key]
        ocr_cache[file_hash] = extracted
        session['_ocr_cache'] = ocr_cache

        return jsonify({"success": True, "file_name": filename, "extracted": extracted, "data": extracted})
    finally:
        # Aadhaar source files are highly sensitive: retain only reviewable extracted fields.
        if os.path.exists(filepath):
            os.remove(filepath)
