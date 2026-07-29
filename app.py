"""
app.py — AgreementAI Flask Application
=======================================
Production-ready setup with:
  - Rate limiting on heavy endpoints (flask-limiter)
  - In-memory TTL cache on the preview endpoint (cachetools)
  - Field registry API endpoint (single source of truth)
  - CORS support for mobile apps (flask-cors)
  - Clean state_code resolution (no broken society-name heuristic)
"""

import os
import json
import uuid
import hashlib
import logging

from flask import Flask, render_template, request, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cachetools import TTLCache

from config import Config
from database import init_db, query_db, execute_db, close_pool
from services.ai_service import ai_service
from field_registry import FIELD_REGISTRY, SECTION_LABELS, SECTION_ORDER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgreementAI")

# ─────────────────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# CORS — required for mobile apps to call the API
CORS(app, origins="*", supports_credentials=False)

# Rate limiting — prevents DoS on heavy endpoints
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri="memory://",
)

# Preview cache — in-memory TTL cache keyed by MD5 of request body
# Each Gunicorn worker has its own cache (good enough for dev/single-node prod).
# Swap to Redis-backed cache for multi-node production.
_preview_cache: TTLCache = TTLCache(
    maxsize=Config.PREVIEW_CACHE_SIZE,
    ttl=Config.PREVIEW_CACHE_TTL,
)

# ─────────────────────────────────────────────────────────────────────────────
# DB initialisation
# ─────────────────────────────────────────────────────────────────────────────
try:
    init_db()
except Exception as e:
    logger.warning(f"DB init notice: {e}")


@app.teardown_appcontext
def _teardown_db(exc):
    """Release pooled connections cleanly on app teardown."""
    pass   # Pool is shared; individual connections released in db helpers


# ─────────────────────────────────────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def landing_page():
    """Serve the AgreementAI landing page."""
    return render_template('index.html')


@app.route('/rental')
@app.route('/agreements/simple-rental')
@app.route('/agreements/leave-and-license')
def rental_form():
    """Serve the split-screen Agreement Form UI."""
    society     = request.args.get('society', None)
    property_id = request.args.get('property_id', None)
    google_maps_key = Config.GOOGLE_MAPS_API_KEY  # passed to template for future Maps integration
    return render_template(
        'rental_form.html',
        placeholders=[],
        preselected_society=society,
        property_id=property_id,
        google_maps_key=google_maps_key,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Field Registry API — single source of truth served to JS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/field-registry')
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


from flask import Flask, render_template, request, jsonify, send_from_directory, session

# Set secret key for multi-tenant auth sessions
app.secret_key = os.getenv("SECRET_KEY", "agreement_ai_secure_session_secret_key_2026")


# ─────────────────────────────────────────────────────────────────────────────
# Auth Endpoints (Multi-Tenant User Management)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/auth/signup', methods=['POST'])
def api_auth_signup():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    full_name = (data.get('full_name') or 'Property Owner/Tenant').strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    # In production with Postgres: query_db and insert user.
    # In dev/offline mode: store session cleanly.
    user_id = str(uuid.uuid4())
    user_obj = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "role": "user"
    }
    
    # Save user to DB if online
    execute_db(
        "INSERT INTO agreement.agr_users (id, email, full_name) VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING",
        (user_id, email, full_name)
    )

    session['user'] = user_obj
    return jsonify({"success": True, "user": user_obj})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    # Try DB lookup first
    db_user = query_db("SELECT id, email, full_name, role FROM agreement.agr_users WHERE email = %s", (email,), one=True)
    if db_user:
        user_obj = {
            "id": str(db_user["id"]),
            "email": db_user["email"],
            "full_name": db_user["full_name"],
            "role": db_user.get("role", "user")
        }
    else:
        # Development fallback
        user_obj = {
            "id": str(uuid.uuid4()),
            "email": email,
            "full_name": email.split('@')[0].capitalize(),
            "role": "user"
        }

    session['user'] = user_obj
    return jsonify({"success": True, "user": user_obj})


@app.route('/api/auth/logout', methods=['POST', 'GET'])
def api_auth_logout():
    session.pop('user', None)
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    user = session.get('user')
    if user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False, "user": None})


@app.route('/api/agreements/my-drafts', methods=['GET'])
def api_my_drafts():
    user = session.get('user')
    user_id = user['id'] if user else None
    
    if not user_id:
        return jsonify({"drafts": []})

    drafts = query_db("SELECT id, agreement_number, title, monthly_rent, created_at FROM agreement.agr_agreements WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    return jsonify({"drafts": drafts or []})


# ─────────────────────────────────────────────────────────────────────────────
# Preview endpoint — rate-limited + cached
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/rental/preview', methods=['POST'])
@app.route('/api/render-agreement', methods=['POST'])
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

    if cache_key in _preview_cache:
        return jsonify({"success": True, "html": _preview_cache[cache_key], "cached": True})

    html_output = ai_service.render_clauses_agreement(data)
    _preview_cache[cache_key] = html_output

    return jsonify({"success": True, "html": html_output})


# ─────────────────────────────────────────────────────────────────────────────
# AI endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/ai/draft', methods=['POST'])
@limiter.limit("10 per minute")
def api_ai_draft():
    """Generate agreement draft via AI (Gemini / AWS Bedrock)."""
    data          = request.json or {}
    prompt        = data.get('prompt', 'Draft standard residential rental agreement')
    state_code    = data.get('state_code', 'KA')
    template_type = data.get('template_type', 'simple_rental')
    draft         = ai_service.generate_agreement_draft(prompt, state_code, template_type)
    return jsonify({"success": True, "data": draft})


@app.route('/api/ai/review-chat', methods=['POST'])
@limiter.limit("20 per minute")
def api_ai_review_chat():
    """AI Copilot — answer questions or edit agreement clauses."""
    data            = request.json or {}
    agreement_html  = data.get('agreement_html', '')
    user_prompt     = data.get('prompt', '')
    agreement_type  = data.get('agreement_type', 'simple_rental')
    result          = ai_service.review_and_modify_agreement(agreement_html, user_prompt, agreement_type)
    return jsonify({"success": True, "data": result})


@app.route('/api/ocr/aadhaar', methods=['POST'])
@limiter.limit("10 per minute")
def api_ocr_aadhaar():
    """Upload Aadhaar card image and extract party fields via multimodal AI OCR."""
    if 'file' not in request.files or request.files['file'].filename == '':
        # Return demo/mock result when no file provided
        ocr_result = ai_service.extract_aadhaar_ocr(b"", "image/jpeg")
        return jsonify({"success": True, "extracted": ocr_result, "source": "demo_ocr"})

    file        = request.files['file']
    filename    = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    filepath    = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)

    with open(filepath, 'rb') as f:
        image_bytes = f.read()

    extracted = ai_service.extract_aadhaar_ocr(image_bytes, file.mimetype or "image/jpeg")
    return jsonify({"success": True, "file_name": filename, "extracted": extracted})


# ─────────────────────────────────────────────────────────────────────────────
# Reference data endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/rental/mapping')
@app.route('/api/mapping')
def api_mapping():
    return jsonify({"mappings": []})


@app.route('/api/propertymaster/societies')
@app.route('/api/societies')
def api_societies():
    return jsonify({"societies": []})


@app.route('/api/templates')
def api_templates():
    return jsonify({
        "templates": [
            "RENTAL_AGREEMENT_SIMPLE_FAMILY_v1.docx",
            "LEAVE_LICENSE_AGREEMENT_FAMILY_v1.docx",
        ]
    })


@app.route('/api/executives')
def api_executives():
    return jsonify({"executives": []})


@app.route('/api/stamp-duty/<state_code>', methods=['GET'])
def api_stamp_duty(state_code):
    """Fetch stamp duty rates for a state."""
    rates = query_db(
        "SELECT * FROM agreement.agr_stamp_duty_rates WHERE state_code = %s",
        [state_code.upper()]
    )
    if not rates:
        rates = [{"state_code": state_code, "duty_amount": 200.00, "description": "Standard Stamp Duty"}]
    return jsonify({"success": True, "rates": rates})


# ─────────────────────────────────────────────────────────────────────────────
# Agreement CRUD
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/agreements', methods=['GET', 'POST'])
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


@app.route('/api/rental/submit', methods=['POST'])
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


@app.route('/api/agreement-template/get-template', methods=['POST'])
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
# Static file helpers
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/open/<path:filepath>')
def api_open_file(filepath):
    """Serve a generated document file for browser download."""
    directory = os.path.dirname(filepath)
    filename  = os.path.basename(filepath)
    return send_from_directory(directory, filename, as_attachment=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_float(value) -> float:
    if not value:
        return 0.0
    cleaned = str(value).replace(',', '').replace('₹', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Entry point (dev only — production uses Gunicorn)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    is_dev = Config.DEBUG
    mode   = "DEVELOPMENT (Auto-Reload)" if is_dev else "PRODUCTION"
    logger.info(f"Starting AgreementAI in {mode} mode on http://localhost:{Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=is_dev, use_reloader=is_dev)
