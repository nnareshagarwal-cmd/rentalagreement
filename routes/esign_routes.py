"""
routes/esign_routes.py — Leegality Digital Signature (eSign) Endpoints
======================================================================
Digital eSign requests via Leegality API, status polling, and webhook verification.
"""

import json
import logging

from flask import Blueprint, request, jsonify

from database import execute_db
from services.leegality_service import leegality_service, LeegalityError

logger = logging.getLogger("AgreementAI")

esign_bp = Blueprint('esign', __name__)


@esign_bp.route('/api/rental/request-esign', methods=['POST'])
@esign_bp.route('/api/esign/request', methods=['POST'])
def api_rental_request_esign():
    """
    Generate the agreement PDF and dispatch digital eSign invitations
    via Leegality Sandbox/Production API.
    """
    data = request.get_json(silent=True) or {}
    irn = data.get('agreement_number') or data.get('irn')

    try:
        custom_invitees = data.get('custom_invitees') or data.get('invitees')
        result = leegality_service.initiate_esign(data, custom_invitees=custom_invitees, irn=irn)
        
        # If agreement exists in DB, update status
        agreement_id = data.get('agreement_id')
        if agreement_id:
            try:
                execute_db(
                    "UPDATE agreement.agr_agreements SET status = 'ESIGN_SENT', custom_clauses = jsonb_set(COALESCE(custom_clauses, '{}'::jsonb), '{leegality_doc_id}', %s) WHERE id = %s",
                    [json.dumps(result.get('document_id')), agreement_id]
                )
            except Exception as dbe:
                logger.warning(f"DB update notice on eSign dispatch: {dbe}")

        return jsonify(result)
    except LeegalityError as e:
        logger.warning(f"Leegality service rejected request: {e.message}")
        return jsonify({"success": False, "error": e.message, "details": e.details}), e.status_code
    except Exception as e:
        logger.exception("Unexpected error in request-esign endpoint")
        return jsonify({"success": False, "error": f"Failed to initiate eSign: {str(e)}"}), 500


@esign_bp.route('/api/rental/esign-status/<document_id>', methods=['GET'])
@esign_bp.route('/api/esign/status/<document_id>', methods=['GET'])
def api_rental_esign_status(document_id):
    """
    Query real-time document signing status and invitee progress.
    """
    include_file = request.args.get('file', 'false').lower() in ('1', 'true', 'yes')
    include_audit = request.args.get('audit', 'false').lower() in ('1', 'true', 'yes')

    try:
        details = leegality_service.get_document_details(
            document_id,
            include_file=include_file,
            include_audit=include_audit
        )
        return jsonify(details)
    except LeegalityError as e:
        return jsonify({"success": False, "error": e.message, "details": e.details}), e.status_code
    except Exception as e:
        logger.exception(f"Error fetching status for Leegality document {document_id}")
        return jsonify({"success": False, "error": str(e)}), 500


@esign_bp.route('/api/leegality/webhook', methods=['POST'])
def api_leegality_webhook():
    """
    Incoming webhook handler for Leegality eSign events.
    Verifies HMAC MAC header with Private Salt.
    """
    mac_header = request.headers.get('X-Leegality-Mac') or request.headers.get('Mac') or ''
    raw_data = request.get_data()

    if not leegality_service.verify_webhook_mac(raw_data, mac_header):
        logger.warning("Rejected Leegality webhook due to invalid MAC signature")
        return jsonify({"success": False, "error": "Invalid MAC signature"}), 401

    payload = request.get_json(silent=True) or {}
    doc_id = payload.get('documentId')
    status = payload.get('status')
    logger.info(f"Received verified Leegality webhook for document {doc_id} with status: {status}")

    # Optionally persist status update to database
    if doc_id and status:
        try:
            execute_db(
                "UPDATE agreement.agr_agreements SET status = %s WHERE custom_clauses->>'leegality_doc_id' = %s",
                [status, doc_id]
            )
        except Exception as dbe:
            logger.warning(f"DB update on webhook notice: {dbe}")

    return jsonify({"success": True, "message": "Webhook processed successfully"})
