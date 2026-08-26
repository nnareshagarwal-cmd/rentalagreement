"""
services/leegality_service.py — Leegality Digital Signature (eSign) Integration Service
====================================================================================
Integrates SafeKeys / AgreementAI with Leegality's Document Execution API (v3.0).
Supports:
  - Dynamic extraction of Lessors (Owners 1..N) and Lessees (Tenants 1..N)
  - Seamless PDF generation & Base64 encoding
  - Aadhaar / OTP eSign request initiation
  - Document status polling & audit trail download
  - Webhook HMAC signature validation
"""

import os
import re
import json
import hmac
import hashlib
import base64
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple
import requests

from config import Config

logger = logging.getLogger("SafeKeys_Leegality")


class LeegalityError(Exception):
    """Custom exception for Leegality API errors."""
    def __init__(self, message: str, status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class LeegalityService:
    def __init__(self):
        self.base_url = Config.LEEGALITY_BASE_URL.rstrip('/')
        self.auth_token = Config.LEEGALITY_AUTH_TOKEN
        self.profile_id = Config.LEEGALITY_PROFILE_ID
        self.private_salt = Config.LEEGALITY_PRIVATE_SALT
        self.env = Config.LEEGALITY_ENV

    def is_configured(self) -> bool:
        """Check if Leegality API credentials and profile are configured."""
        return bool(self.auth_token and self.profile_id)

    @staticmethod
    def _clean_phone(phone: Optional[str]) -> str:
        """Normalize Indian phone numbers to exactly 10 digits."""
        if not phone:
            return ""
        digits = re.sub(r'\D', '', str(phone).strip())
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith('0'):
            digits = digits[1:]
        elif len(digits) > 10:
            digits = digits[-10:]
        return digits if len(digits) == 10 else ""

    @staticmethod
    def calculate_default_appearances(role: str, slot_index: int = 0, page: str = "L") -> List[Dict[str, Any]]:
        """
        Calculate smart default signature placement coordinates on standard A4 (595 x 842 pt).
        - Owners/Lessors: Left Column (x1: 45, x2: 245)
        - Tenants/Lessees: Right Column (x1: 345, x2: 545)
        - y1, y2 vertically staggered per slot to prevent overlap
        """
        box_width = 200
        box_height = 55
        y_start = 120
        y_spacing = 75

        is_owner = str(role or '').upper() in ('OWNER', 'LESSOR', 'LANDLORD')
        x1 = 45 if is_owner else 345
        x2 = x1 + box_width
        y1 = y_start + (slot_index * y_spacing)
        y2 = y1 + box_height

        return [{
            "page": str(page),
            "x1": int(x1),
            "y1": int(y1),
            "x2": int(x2),
            "y2": int(y2)
        }]

    def extract_invitees(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract invitees (Owners / Lessors and Tenants / Lessees) from agreement form data.
        Returns a list of invitee dicts: [{'name': ..., 'email': ..., 'phone': ..., 'role': ...}]
        """
        invitees: List[Dict[str, Any]] = []

        # 1. Extract Owners / Lessors (Slots 1 to 6)
        for i in range(1, 7):
            name = (data.get(f'owner{i}_name') or data.get(f'owner_{i}_name') or '').strip()
            if not name and i == 1:
                # Check legacy / flat aliases
                name = (data.get('owner_name') or data.get('lessor_name') or data.get('p5') or data.get('P5') or '').strip()

            if name:
                email = (data.get(f'owner{i}_email') or (data.get('owner_email') if i == 1 else '') or '').strip()
                phone = (data.get(f'owner{i}_phone') or (data.get('owner_phone') if i == 1 else '') or '').strip()
                
                invitees.append({
                    "name": name,
                    "email": email or None,
                    "phone": phone or None,
                    "role": "OWNER"
                })

        # 2. Extract Tenants / Lessees (Slots 1 to 6)
        for i in range(1, 7):
            name = (data.get(f'tenant{i}_name') or data.get(f'tenant_{i}_name') or '').strip()
            if not name and i == 1:
                # Check legacy / flat aliases
                name = (data.get('tenant_name') or data.get('lessee_name') or data.get('p8') or data.get('P8') or '').strip()

            if name:
                email = (data.get(f'tenant{i}_email') or (data.get('tenant_email') if i == 1 else '') or '').strip()
                phone = (data.get(f'tenant{i}_phone') or (data.get('tenant_phone') if i == 1 else '') or '').strip()

                invitees.append({
                    "name": name,
                    "email": email or None,
                    "phone": phone or None,
                    "role": "TENANT"
                })

        return invitees

    def initiate_esign(
        self,
        data: Dict[str, Any],
        custom_invitees: Optional[List[Dict[str, Any]]] = None,
        irn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate an eSigning request via Leegality API v3.0 with dynamic verification settings.
        
        Args:
            data: Agreement form payload.
            custom_invitees: Optional override list of invitee objects.
            irn: Optional Internal Reference Number.
            
        Returns:
            Dict with documentId, invitees list (with signUrls), status, and messages.
        """
        if not self.is_configured():
            raise LeegalityError(
                "Leegality API is not configured. Please set LEEGALITY_AUTH_TOKEN and LEEGALITY_PROFILE_ID in your environment.",
                status_code=500
            )

        def _resolve_bool(val: Any, default: bool) -> bool:
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            if isinstance(val, dict):
                return bool(val.get('enableSmartUserLiveliness', default))
            return str(val).strip().lower() in ("true", "1", "yes", "y")

        # Resolve dynamic settings
        capture_photo = _resolve_bool(data.get('capture_photo'), getattr(Config, 'LEEGALITY_CAPTURE_PHOTO', True))
        smart_liveliness = _resolve_bool(data.get('smart_liveliness'), getattr(Config, 'LEEGALITY_SMART_LIVELINESS', True))
        liveliness_retries = int(data.get('liveliness_retries') or getattr(Config, 'LEEGALITY_LIVELINESS_RETRIES', 3))
        enable_face_auth = _resolve_bool(data.get('enable_face_auth'), getattr(Config, 'LEEGALITY_ENABLE_FACE_AUTH', True))
        gps_val = data.get('enable_gps') if 'enable_gps' in data else data.get('apply_gps')
        enable_gps = _resolve_bool(gps_val, getattr(Config, 'LEEGALITY_ENABLE_GPS', True))
        enable_auto_placement = _resolve_bool(data.get('enable_auto_placement', data.get('auto_placement')), True)

        # 1. Resolve invitees
        invitees_raw = custom_invitees or self.extract_invitees(data)
        if not invitees_raw:
            raise LeegalityError(
                "No valid signers found. Please provide at least one Landlord or Tenant with name and contact details.",
                status_code=400
            )

        # Ensure each invitee has at least email or 10-digit phone
        formatted_invitees = []
        role_counts: Dict[str, int] = {}
        for inv in invitees_raw:
            name = (inv.get('name') or '').strip()
            raw_email = (inv.get('email') or '').strip()
            raw_phone = (inv.get('phone') or '').strip()
            role = inv.get('role') or 'Party'

            if not name:
                continue

            email = raw_email if (raw_email and '@' in raw_email and '.' in raw_email) else None
            cleaned_phone = self._clean_phone(raw_phone)
            phone = cleaned_phone if len(cleaned_phone) == 10 else None

            # Validate non-empty but invalid phone
            if raw_phone and not phone:
                raise LeegalityError(
                    f"Invalid mobile number '{raw_phone}' for {role} '{name}'. Indian mobile numbers must be 10 digits (e.g. 9876543210).",
                    status_code=400
                )

            # Validate non-empty but invalid email
            if raw_email and not email:
                raise LeegalityError(
                    f"Invalid email address '{raw_email}' for {role} '{name}'. Please provide a valid email (e.g. name@example.com).",
                    status_code=400
                )

            if not email and not phone:
                raise LeegalityError(
                    f"{role} '{name}' must have at least a valid 10-digit Mobile number or Email address to receive the digital signing invitation.",
                    status_code=400
                )
            
            inv_obj = {"name": name}
            if email:
                inv_obj["email"] = email
            if phone:
                inv_obj["phone"] = phone

            # Dynamic Signature Type Selection (AADHAAR vs VIRTUAL_SIGN vs ALLOW_EITHER)
            if 'signatures' in inv and isinstance(inv['signatures'], list) and inv['signatures']:
                inv_obj["signatures"] = inv['signatures']
            else:
                raw_sign_type = str(inv.get('signType') or inv.get('sign_type') or inv.get('signature_type') or 'AADHAAR').strip().upper()
                if raw_sign_type in ('VIRTUAL_SIGN', 'VIRTUAL'):
                    inv_obj["signatures"] = [{"type": "VIRTUAL_SIGN"}]
                elif raw_sign_type in ('ALLOW_EITHER', 'EITHER', 'BOTH', 'ALL'):
                    inv_obj["signatures"] = [{"type": "AADHAAR"}, {"type": "VIRTUAL_SIGN"}]
                elif raw_sign_type == 'AADHAAR':
                    inv_obj["signatures"] = [{"type": "AADHAAR"}]

            # Dynamic Signature Placement (appearances)
            custom_appearances = inv.get('appearances')
            if custom_appearances and isinstance(custom_appearances, list) and len(custom_appearances) > 0:
                clean_appearances = []
                for app in custom_appearances:
                    if isinstance(app, dict):
                        page_val = app.get('page', 'L')
                        clean_appearances.append({
                            "page": page_val,
                            "x1": int(round(float(app.get('x1', 45)))),
                            "y1": int(round(float(app.get('y1', 120)))),
                            "x2": int(round(float(app.get('x2', 245)))),
                            "y2": int(round(float(app.get('y2', 175))))
                        })
                inv_obj["appearances"] = clean_appearances if clean_appearances else self.calculate_default_appearances(role, slot_index=0, page="L")
            elif enable_auto_placement:
                slot_idx = role_counts.get(role, 0)
                role_counts[role] = slot_idx + 1
                inv_obj["appearances"] = self.calculate_default_appearances(role, slot_index=slot_idx, page="L")

            # Signer-level or dynamic photo capture
            inv_capture_photo = _resolve_bool(inv.get('capturePhoto', inv.get('capture_photo')), capture_photo)
            if inv_capture_photo:
                inv_obj["capturePhoto"] = True
                inv_liveliness = _resolve_bool(inv.get('smartUserLiveliness', inv.get('smart_liveliness')), smart_liveliness)
                if inv_liveliness:
                    inv_obj["userLiveliness"] = True
                    inv_obj["smartUserLivelinessConfig"] = {
                        "enableSmartUserLiveliness": True,
                        "smartUserLivelinessRetryAttempts": liveliness_retries
                    }
            elif 'capturePhoto' in inv or 'capture_photo' in inv:
                inv_obj["capturePhoto"] = False

            formatted_invitees.append(inv_obj)

        if not formatted_invitees:
            raise LeegalityError("No valid invitees with contact information provided.", status_code=400)

        # 2. Generate PDF of agreement
        tmp_pdf_path = None
        try:
            from clauses.pdf_renderer import generate_pdf
            tmp_fd, tmp_pdf_path = tempfile.mkstemp(suffix='.pdf')
            os.close(tmp_fd)

            generate_pdf(data, output_path=tmp_pdf_path)

            if not os.path.exists(tmp_pdf_path) or os.path.getsize(tmp_pdf_path) == 0:
                raise LeegalityError("PDF generation produced an empty file. Cannot send for eSign.", status_code=500)

            with open(tmp_pdf_path, 'rb') as f:
                pdf_bytes = f.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        except Exception as e:
            logger.exception("Failed to generate PDF for Leegality eSign")
            raise LeegalityError(f"Failed to generate agreement PDF: {str(e)}", status_code=500)
        finally:
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.remove(tmp_pdf_path)
                except OSError:
                    pass

        # 3. Construct Leegality API Payload
        doc_no = data.get('agreement_number') or irn or f"AGR-{int(os.times().system * 1000)}"
        doc_filename = f"Rental_Agreement_{doc_no}.pdf"

        payload = {
            "profileId": self.profile_id,
            "file": {
                "name": doc_filename,
                "file": pdf_base64
            },
            "invitees": formatted_invitees,
            "irn": irn or doc_no
        }

        # Dynamic Aadhaar Authentication Types (OTP + optional Face RD)
        auth_types = ["OTP"]
        if enable_face_auth:
            auth_types.append("FACE")
        if _resolve_bool(data.get('enable_biometric'), False):
            auth_types.extend(["BIO", "IRIS"])

        payload["signatureConfig"] = {
            "authTypes": auth_types
        }

        # Optional GPS configuration
        if enable_gps:
            payload["gpsConfig"] = {
                "applyLocationRestriction": False
            }

        headers = {
            "X-Auth-Token": self.auth_token,
            "Content-Type": "application/json"
        }

        endpoint = f"{self.base_url}/sign/request"
        logger.info(f"Submitting Leegality eSign request for {len(formatted_invitees)} invitees to {endpoint}")

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=35)
        except requests.RequestException as e:
            logger.exception("Leegality API connection failed")
            raise LeegalityError(f"Unable to connect to Leegality API: {str(e)}", status_code=502)

        try:
            resp_data = response.json()
        except ValueError:
            logger.error(f"Leegality API non-JSON response ({response.status_code}): {response.text[:300]}")
            raise LeegalityError("Invalid response received from Leegality API.", status_code=502)

        if response.status_code != 200 or resp_data.get('status') != 1:
            messages = resp_data.get('messages', [])
            error_msg = "; ".join([m.get('message', 'Unknown error') for m in messages if isinstance(m, dict)])
            if not error_msg:
                error_msg = resp_data.get('message') or f"Leegality error (Code: {response.status_code})"
            logger.error(f"Leegality sign request rejected: {error_msg}")
            raise LeegalityError(error_msg, status_code=response.status_code or 400, details=resp_data)

        # 4. Normalize successful response
        doc_data = resp_data.get('data', {})
        document_id = doc_data.get('documentId')
        invitees_res = doc_data.get('invitees', [])

        # Filter out empty slots if returned by profile
        active_invitees = [
            inv for inv in invitees_res
            if isinstance(inv, dict) and inv.get('name')
        ]

        logger.info(f"Leegality eSign request successful. Document ID: {document_id}")
        return {
            "success": True,
            "document_id": document_id,
            "irn": doc_data.get('irn') or payload.get('irn'),
            "invitees": active_invitees,
            "message": "Digital eSign invitations dispatched successfully."
        }

    def get_document_details(
        self,
        document_id: str,
        include_file: bool = False,
        include_audit: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch real-time document status, signer details, and signed PDF from Leegality.
        
        Args:
            document_id: The Leegality document ID.
            include_file: If True, requests Base64 / CDN download for the signed PDF.
            include_audit: If True, requests the audit trail document.
            
        Returns:
            Dict containing document status, invitations progress, and file payloads.
        """
        if not self.is_configured():
            raise LeegalityError("Leegality API credentials are not configured.", status_code=500)

        if not document_id:
            raise LeegalityError("document_id is required.", status_code=400)

        headers = {
            "X-Auth-Token": self.auth_token
        }
        params = {
            "documentId": document_id,
            "file": "true" if include_file else "false",
            "auditTrail": "true" if include_audit else "false"
        }

        endpoint = f"{self.base_url}/document/details"
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=25)
            resp_data = response.json()
        except Exception as e:
            logger.exception(f"Failed to query Leegality document details for {document_id}")
            raise LeegalityError(f"Failed to query document details: {str(e)}", status_code=502)

        if response.status_code != 200 or resp_data.get('status') != 1:
            messages = resp_data.get('messages', [])
            error_msg = "; ".join([m.get('message', '') for m in messages if isinstance(m, dict)]) or "Document not found."
            raise LeegalityError(error_msg, status_code=response.status_code, details=resp_data)

        doc_data = resp_data.get('data', {})
        return {
            "success": True,
            "document_id": doc_data.get('documentId'),
            "document_name": doc_data.get('documentName'),
            "status": doc_data.get('status'),  # SENT, IN_PROGRESS, COMPLETED, EXPIRED, REJECTED
            "creation_date": doc_data.get('creationDate'),
            "completion_date": doc_data.get('completionDate'),
            "invitations": doc_data.get('invitations', []),
            "file_base64": doc_data.get('file'),
            "audit_trail_base64": doc_data.get('auditTrail')
        }

    def verify_webhook_mac(self, raw_payload: bytes, mac_header: str) -> bool:
        """
        Verify incoming Leegality webhook signature with Private Salt.
        """
        if not self.private_salt or not mac_header:
            return True  # If salt not configured in dev, pass through

        try:
            expected_mac = hmac.new(
                self.private_salt.encode('utf-8'),
                raw_payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_mac.lower(), mac_header.lower())
        except Exception as e:
            logger.warning(f"Webhook MAC calculation error: {e}")
            return False


# Global singleton instance
leegality_service = LeegalityService()
