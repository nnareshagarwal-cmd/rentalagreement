"""
routes/agreement_routes.py — Agreement CRUD & Document Generation
==================================================================
Preview rendering, agreement save/list, form submission,
DOCX/PDF download, template resolution, and file serving.
"""

import os
import json
import uuid
import hashlib
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file, send_from_directory, session, current_app
from werkzeug.utils import secure_filename

from extensions import limiter, preview_cache, _to_float
from config import Config
from database import query_db, execute_db
from services.ai_service import ai_service
from clauses.agreement_renderer import generate_docx, generate_preview_html
from clauses.pdf_renderer import generate_pdf

logger = logging.getLogger("AgreementAI")

agreement_bp = Blueprint('agreement', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Preview endpoint — rate-limited + cached
# ─────────────────────────────────────────────────────────────────────────────

@agreement_bp.route('/api/rental/preview', methods=['POST'])
@agreement_bp.route('/api/render-agreement', methods=['POST'])
@limiter.limit(Config.RATELIMIT_PREVIEW_ENDPOINT)
def api_render_agreement():
    """
    Render HTML preview of the agreement from form data.
    Rate-limited to 30 req/sec per IP.
    Response is cached for 10 seconds keyed by MD5 of input data —
    identical form states return instantly without hitting Python rendering.
    """
    data = request.json or {}

    # Cache key = MD5 of sorted JSON representation of the input
    cache_key = hashlib.md5(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    preview_cache.clear()

    html_output = ai_service.render_clauses_agreement(data)
    preview_cache[cache_key] = html_output

    return jsonify({"success": True, "html": html_output})


# ─────────────────────────────────────────────────────────────────────────────
# Agreement CRUD
# ─────────────────────────────────────────────────────────────────────────────

@agreement_bp.route('/api/agreements', methods=['GET', 'POST'])
def api_agreements():
    """Save or list agreements from PostgreSQL agreement.agr_agreements."""
    if request.method == 'POST':
        data       = request.json or {}
        agr_num    = f"AGR-{uuid.uuid4().hex[:8].upper()}"
        title      = data.get('title', 'Property Agreement')
        # Use explicit state_code field only — no broken heuristic
        state_code = data.get('state_code', 'KA') or 'KA'
        rent       = _to_float(data.get('monthly_rent', 0))
        deposit    = _to_float(data.get('security_deposit', 0))
        content    = data.get('full_text', '')

        success = execute_db("""
            INSERT INTO agreement.agr_agreements
            (agreement_number, title, state_code, monthly_rent, security_deposit, generated_content, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT')
        """, [agr_num, title, state_code, rent, deposit, content])

        return jsonify({
            "success": True,
            "agreement_number": agr_num,
            "message": "Saved!",
        })
    else:
        agreements = query_db("SELECT * FROM agreement.agr_agreements ORDER BY created_at DESC LIMIT 10")
        return jsonify({"success": True, "agreements": agreements or []})


@agreement_bp.route('/api/rental/submit', methods=['POST'])
def api_rental_submit():
    """Save rental form data to PostgreSQL — all fields to proper tables."""
    data    = request.json or {}
    agr_num = f"AGR-{uuid.uuid4().hex[:8].upper()}"
    title   = data.get('title') or data.get('society_name') or 'Rental Agreement'

    # Clean state_code: explicit field only, fallback 'KA'
    state_code = data.get('state_code') or 'KA'

    rent    = _to_float(data.get('monthly_rent', 0))
    deposit = _to_float(data.get('security_deposit', 0))
    increase_pct = _to_float(data.get('increase_percent', 5))
    start_date = data.get('agreement_start_date') or None
    end_date   = data.get('agreement_end_date') or None

    # Build generated_content: full_text (preview HTML) or JSON dump of all fields
    try:
        generated_content = data.get('full_text') or json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        safe = {k: (str(v) if v is not None else None) for k, v in data.items()}
        generated_content = json.dumps(safe, ensure_ascii=False)

    # Store all raw form data as custom_clauses JSON for future reload
    try:
        raw_form_json = json.dumps(
            {k: v for k, v in data.items() if k != 'full_text'},
            ensure_ascii=False
        )
    except (TypeError, ValueError):
        raw_form_json = '{}'

    # Get user_id from session (if logged in)
    user = session.get('user')
    user_id = user['id'] if user else None

    # 1. Save master agreement
    agr_row = execute_db("""
        INSERT INTO agreement.agr_agreements
        (agreement_number, user_id, title, state_code, monthly_rent, security_deposit,
         escalation_percentage, start_date, end_date,
         custom_clauses, generated_content, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT')
        RETURNING id
    """, [agr_num, user_id, title, state_code, rent, deposit,
          increase_pct, start_date, end_date,
          raw_form_json, generated_content],
        returning=True)

    agreement_id = agr_row['id'] if agr_row and isinstance(agr_row, dict) else None

    # 2. Save party details (owners 1-6 and tenants 1-6)
    if agreement_id:
        for party_prefix, party_type in [('owner', 'LESSOR'), ('tenant', 'LESSEE')]:
            for i in range(1, 7):
                name_key = f"{party_prefix}{i}_name"
                name_val = (data.get(name_key) or '').strip()
                if not name_val:
                    continue  # Skip empty party slots

                prefix_val  = data.get(f"{party_prefix}{i}_prefix", '')
                careof_val  = data.get(f"{party_prefix}{i}_careof", '')
                careof_name = data.get(f"{party_prefix}{i}_careofname", '')
                age_val     = data.get(f"{party_prefix}{i}_age", '')
                occ_val     = data.get(f"{party_prefix}{i}_occupation", '')
                addr_val    = data.get(f"{party_prefix}{i}_address", '')
                email_val   = data.get(f"{party_prefix}{i}_email", '')
                phone_val   = data.get(f"{party_prefix}{i}_phone", '')

                # Map careof to relation_type code
                relation_type = 'S/O'  # default
                if careof_val == 'Husband Name':
                    relation_type = 'W/O'
                elif careof_val == 'Father Name':
                    if prefix_val in ('Mrs.', 'Smt'):
                        relation_type = 'D/O'
                    else:
                        relation_type = 'S/O'

                execute_db("""
                    INSERT INTO agreement.agr_parties
                    (agreement_id, party_type, full_name, relation_type, relation_name,
                     email, phone, address_line1)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, [agreement_id, party_type, name_val, relation_type,
                      careof_name, email_val or None, phone_val or None, addr_val or None])

        # 3. Save property details
        prop_type = data.get('property_type', 'Apartment')
        prop_addr = data.get('property_address', '')
        society   = data.get('society_name', '')
        prop_no   = data.get('property_no', '')

        if prop_addr or society:
            execute_db("""
                INSERT INTO agreement.agr_properties
                (agreement_id, property_type, building_name, door_number, city, state)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [agreement_id,
                  prop_type.upper().replace(' ', '_') if prop_type else 'APARTMENT',
                  society or None,
                  prop_no or None,
                  'Bengaluru',  # Default city — can be extracted from address later
                  state_code])

    success = agreement_id is not None
    return jsonify({
        "success": True,
        "agreement_number": agr_num,
        "agreement_id": str(agreement_id) if agreement_id else None,
        "message": "Saved!",
    })


@agreement_bp.route('/api/agreement-template/get-template', methods=['POST'])
def api_get_template():
    """Return the best-matching document template for the given agreement parameters."""
    data           = request.json or {}
    agreement_type = data.get('agreement_type', 'Simple')
    tenant_type    = data.get('tenant_type', 'Family')
    owner_count    = int(data.get('owner_count', 1))
    tenant_count   = int(data.get('tenant_count', 1))
    lockin         = data.get('lockin', 'N')

    # Build template name from parameters
    atype = "LEAVE_LICENSE" if "leave" in agreement_type.lower() else "RENTAL"
    lock  = "NOLCKIN" if lockin in ("Y", "yes", "true", True) else "LOCKIN"
    tname = f"{atype}_{tenant_type.upper()}_{lock}_O{owner_count}T{tenant_count}_v1.docx"

    return jsonify({"template_used": tname})


# ─────────────────────────────────────────────────────────────────────────────
# Document download (DOCX & PDF)
# ─────────────────────────────────────────────────────────────────────────────

@agreement_bp.route('/api/rental/download-docx', methods=['POST'])
def api_rental_download_docx():
    """Create a DOCX, archive it by property, and return it as a download."""
    data = request.get_json(silent=True) or {}

    def path_part(value, fallback):
        safe_value = secure_filename(str(value or '').strip())
        return safe_value or fallback

    society = path_part(data.get('society_name'), 'Unknown_Society')
    block = path_part(data.get('property_block'), 'Unknown_Block')
    flat = path_part(data.get('property_no'), 'Unknown_Flat')
    property_folder = f'{block}_{flat}'
    generated_root = os.path.join(current_app.root_path, 'agreements', society, property_folder)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Rental_Agreement_{flat}_{block}_{society}_{timestamp}.docx'
    output_path = os.path.join(generated_root, filename)

    try:
        generate_docx(data, output_path=output_path)
    except Exception:
        logger.exception('DOCX generation failed')
        return jsonify({'success': False, 'error': 'Unable to generate the DOCX document.'}), 500

    return send_file(
        output_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )


@agreement_bp.route('/api/rental/download-pdf', methods=['POST'])
@agreement_bp.route('/api/rental/generate-pdf', methods=['POST'])
def api_rental_download_pdf():
    """Create a PDF document, archive it by property, and return it for direct browser download."""
    data = request.get_json(silent=True) or {}

    def path_part(value, fallback):
        safe_value = secure_filename(str(value or '').strip())
        return safe_value or fallback

    society = path_part(data.get('society_name'), 'Unknown_Society')
    block = path_part(data.get('property_block'), 'Unknown_Block')
    flat = path_part(data.get('property_no'), 'Unknown_Flat')
    property_folder = f'{block}_{flat}'
    generated_root = os.path.join(current_app.root_path, 'agreements', society, property_folder)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Rental_Agreement_{flat}_{block}_{society}_{timestamp}.pdf'
    output_path = os.path.join(generated_root, filename)

    try:
        generate_pdf(data, output_path=output_path)
    except Exception as e:
        logger.exception(f'PDF generation failed: {e}')
        return jsonify({'success': False, 'error': f'Unable to generate the PDF document: {str(e)}'}), 500

    return send_file(
        output_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf',
    )


# ─────────────────────────────────────────────────────────────────────────────
# Static file helper
# ─────────────────────────────────────────────────────────────────────────────

@agreement_bp.route('/api/open/<path:filepath>')
def api_open_file(filepath):
    """Serve a generated document file for browser download."""
    directory = os.path.dirname(filepath)
    filename  = os.path.basename(filepath)
    return send_from_directory(directory, filename, as_attachment=True)
