"""
routes/pages.py — Page rendering routes
========================================
HTML template routes for landing, studio, rental form, and onboarding pages.
"""

from flask import Blueprint, render_template, request
from config import Config

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def landing_page():
    """Serve the AgreementAI landing page."""
    return render_template('index.html')


@pages_bp.route('/create')
@pages_bp.route('/studio')
def ai_creator_studio():
    """Serve the modern AI Creator Studio workspace."""
    agreement_type = request.args.get('type', 'simple_rental')
    state_code = request.args.get('state', 'KA')
    scenario = request.args.get('scenario', 'family')
    return render_template(
        'ai_creator_studio.html',
        agreement_type=agreement_type,
        state_code=state_code,
        scenario=scenario,
    )


@pages_bp.route('/start-agreement')
def start_agreement():
    """Aadhaar-first agreement onboarding with manual drafting still available."""
    return render_template('aadhaar_onboarding.html')


@pages_bp.route('/rental')
@pages_bp.route('/agreements/simple-rental')
@pages_bp.route('/agreements/leave-and-license')
def rental_form():
    """Serve the split-screen Agreement Form UI."""
    path = request.path
    if 'leave-and-license' in path:
        agreement_title = "Leave and License Agreement Form"
    else:
        agreement_title = "Rental Agreement Form"

    society     = request.args.get('society', None)
    property_id = request.args.get('property_id', None)
    google_maps_key = Config.GOOGLE_MAPS_API_KEY
    return render_template(
        'rental_form.html',
        placeholders=[],
        preselected_society=society,
        property_id=property_id,
        google_maps_key=google_maps_key,
        agreement_title=agreement_title,
    )
