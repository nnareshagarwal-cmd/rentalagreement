"""
routes/auth_routes.py — Authentication endpoints
==================================================
Signup, login, logout, session info, and user drafts.
"""

import os
import uuid
import logging

from flask import Blueprint, request, jsonify, session

from database import query_db, execute_db

logger = logging.getLogger("AgreementAI")

auth_bp = Blueprint('auth', __name__)

# Set secret key for multi-tenant auth sessions
# (Will be overridden by app.secret_key in app.py if set there)


@auth_bp.route('/api/auth/signup', methods=['POST'])
def api_auth_signup():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    full_name = (data.get('full_name') or 'Property Owner/Tenant').strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

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


@auth_bp.route('/api/auth/login', methods=['POST'])
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


@auth_bp.route('/api/auth/logout', methods=['POST', 'GET'])
def api_auth_logout():
    session.pop('user', None)
    return jsonify({"success": True, "message": "Logged out successfully"})


@auth_bp.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    user = session.get('user')
    if user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False, "user": None})


@auth_bp.route('/api/agreements/my-drafts', methods=['GET'])
def api_my_drafts():
    user = session.get('user')
    user_id = user['id'] if user else None

    if not user_id:
        return jsonify({"drafts": []})

    drafts = query_db("SELECT id, agreement_number, title, monthly_rent, created_at FROM agreement.agr_agreements WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    return jsonify({"drafts": drafts or []})
