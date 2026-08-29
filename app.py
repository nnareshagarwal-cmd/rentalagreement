"""
app.py — AgreementAI Flask Application
=======================================
Slim modular application entry point registering Blueprints:
  - routes.pages: HTML views (landing, studio, rental form, onboarding)
  - routes.auth_routes: Authentication & user session management
  - routes.agreement_routes: Agreement CRUD, preview, DOCX/PDF downloads
  - routes.ai_routes: AI Creator Studio chat, confirmation, review, Aadhaar OCR
  - routes.reference_routes: Field registry, Google Places proxy, stamp duty
  - routes.esign_routes: Leegality digital eSign integration & webhooks
"""

import os
import time
import logging

from flask import Flask, request
from flask_cors import CORS

from config import Config
from database import init_db
from extensions import limiter

# Import Blueprints
from routes.pages import pages_bp
from routes.auth_routes import auth_bp
from routes.agreement_routes import agreement_bp
from routes.ai_routes import ai_bp
from routes.reference_routes import reference_bp
from routes.esign_routes import esign_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgreementAI")

# ─────────────────────────────────────────────────────────────────────────────
# App setup & configuration
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file browser caching for live updates
app.secret_key = os.getenv("SECRET_KEY", "agreement_ai_secure_session_secret_key_2026")

# Centralized static asset cache-busting version (Single Source of Truth)
STATIC_VERSION = os.getenv("STATIC_VERSION", "20260826_v54_ocr_cache_and_debounce")


@app.context_processor
def inject_static_version():
    """Inject static_v version string globally into all Jinja templates."""
    return dict(static_v=f"{STATIC_VERSION}_{int(time.time())}")


@app.after_request
def add_no_cache_headers(response):
    """Ensure browser never serves stale JS/CSS or draft responses."""
    if request.path.startswith(('/create', '/creator-chat', '/api/', '/static/')):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# CORS — required for mobile apps to call the API
CORS(app, origins="*", supports_credentials=False)

# Rate limiting
limiter.init_app(app)

# ─────────────────────────────────────────────────────────────────────────────
# Register Blueprints
# ─────────────────────────────────────────────────────────────────────────────
app.register_blueprint(pages_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(agreement_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(reference_bp)
app.register_blueprint(esign_bp)

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
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Entry point (dev only — production uses Gunicorn)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    is_dev = Config.DEBUG
    mode = "DEVELOPMENT (Auto-Reload)" if is_dev else "PRODUCTION"
    logger.info(f"Starting AgreementAI in {mode} mode on http://localhost:{Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=is_dev, use_reloader=is_dev)
