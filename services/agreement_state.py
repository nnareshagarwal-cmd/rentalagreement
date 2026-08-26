"""
services/agreement_state.py — Single Source of Truth Agreement State Manager
=============================================================================
Tracks structured agreement fields with 5-level provenance and 4-state lifecycle.

Provenance Sources:
  - user_explicit: Typed or chosen directly by the user.
  - extracted_chat: Parsed from conversational text.
  - extracted_ocr: Extracted from Aadhaar/Identity documents.
  - ai_suggested: Standard legal or market preset proposed by system.
  - system_calculated: Deterministically calculated (e.g. End date = Start date + tenure).
  - user_confirmed: Explicitly accepted/verified by user.

Field Lifecycle States:
  - missing: No value provided yet.
  - extracted: Parsed from text/document; pending review/confirmation.
  - suggested: Preset suggested; pending acceptance.
  - confirmed: Explicitly verified or accepted by user.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set


class ProvenanceSource:
    USER_EXPLICIT = "user_explicit"
    EXTRACTED_CHAT = "extracted_chat"
    EXTRACTED_OCR = "extracted_ocr"
    AI_SUGGESTED = "ai_suggested"
    SYSTEM_CALCULATED = "system_calculated"
    USER_CONFIRMED = "user_confirmed"


class FieldStatus:
    MISSING = "missing"
    EXTRACTED = "extracted"
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"


class FieldEntry:
    def __init__(
        self,
        key: str,
        value: Any = None,
        status: str = FieldStatus.MISSING,
        source: str = ProvenanceSource.USER_EXPLICIT,
        confidence: float = 1.0,
        confirmed_at: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.status = status
        self.source = source
        self.confidence = float(confidence)
        self.confirmed_at = confirmed_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "status": self.status,
            "source": self.source,
            "confidence": self.confidence,
            "confirmed_at": self.confirmed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldEntry":
        return cls(
            key=data.get("key", ""),
            value=data.get("value"),
            status=data.get("status", FieldStatus.MISSING),
            source=data.get("source", ProvenanceSource.USER_EXPLICIT),
            confidence=data.get("confidence", 1.0),
            confirmed_at=data.get("confirmed_at"),
        )


class AgreementState:
    """
    Manages the single synchronized agreement state.
    Provides bridge between AI extraction, structured form controls, and clause rendering.
    """

    def __init__(
        self,
        agreement_type: str = "simple_rental",
        jurisdiction: str = "KA",
        scenario: str = "family",
        user_role: str = "owner",
    ):
        self.agreement_type = agreement_type
        self.jurisdiction = jurisdiction
        self.scenario = scenario
        self.user_role = user_role
        self.fields: Dict[str, FieldEntry] = {}
        self.updated_at: str = datetime.utcnow().isoformat()

    def set_field(
        self,
        key: str,
        value: Any,
        source: str = ProvenanceSource.USER_EXPLICIT,
        confidence: float = 1.0,
        status: Optional[str] = None,
    ) -> FieldEntry:
        """Set or update a field with provenance metadata."""
        if status is None:
            if source in (ProvenanceSource.USER_EXPLICIT, ProvenanceSource.USER_CONFIRMED):
                status = FieldStatus.CONFIRMED
            elif source in (ProvenanceSource.EXTRACTED_CHAT, ProvenanceSource.EXTRACTED_OCR):
                status = FieldStatus.EXTRACTED
            elif source == ProvenanceSource.AI_SUGGESTED:
                status = FieldStatus.SUGGESTED
            elif source == ProvenanceSource.SYSTEM_CALCULATED:
                status = FieldStatus.EXTRACTED
            else:
                status = FieldStatus.CONFIRMED

        confirmed_at = datetime.utcnow().isoformat() if status == FieldStatus.CONFIRMED else None

        entry = FieldEntry(
            key=key,
            value=value,
            status=status,
            source=source,
            confidence=confidence,
            confirmed_at=confirmed_at,
        )
        self.fields[key] = entry
        self.updated_at = datetime.utcnow().isoformat()
        return entry

    def get_field(self, key: str) -> Optional[FieldEntry]:
        return self.fields.get(key)

    def get_value(self, key: str, default: Any = None) -> Any:
        entry = self.fields.get(key)
        if entry is None or entry.value is None or entry.value == "":
            return default
        return entry.value

    def confirm_field(self, key: str) -> bool:
        """Mark an existing field as confirmed."""
        entry = self.fields.get(key)
        if entry and entry.value is not None:
            entry.status = FieldStatus.CONFIRMED
            entry.source = ProvenanceSource.USER_CONFIRMED
            entry.confirmed_at = datetime.utcnow().isoformat()
            self.updated_at = datetime.utcnow().isoformat()
            return True
        return False

    def bulk_confirm(self, keys: Optional[List[str]] = None) -> int:
        """Confirm multiple fields at once (e.g. during final review)."""
        target_keys = keys if keys is not None else list(self.fields.keys())
        count = 0
        for k in target_keys:
            if self.confirm_field(k):
                count += 1
        return count

    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dictionary representation required by clauses/ rendered templates.
        """
        result: Dict[str, Any] = {
            "agreement_type": self.agreement_type,
            "state_code": self.jurisdiction,
            "scenario": self.scenario,
        }
        for k, entry in self.fields.items():
            if entry.value is not None:
                result[k] = entry.value
        return result

    def to_client_payload(self) -> Dict[str, Any]:
        """
        Full structured state including provenance metadata for frontend synchronization.
        Safe for client sessions (excludes sensitive raw file binaries).
        """
        return {
            "agreement_type": self.agreement_type,
            "jurisdiction": self.jurisdiction,
            "scenario": self.scenario,
            "user_role": self.user_role,
            "updated_at": self.updated_at,
            "fields": {k: entry.to_dict() for k, entry in self.fields.items()},
        }

    @classmethod
    def from_client_payload(cls, data: Dict[str, Any]) -> "AgreementState":
        state = cls(
            agreement_type=data.get("agreement_type", "simple_rental"),
            jurisdiction=data.get("jurisdiction", "KA"),
            scenario=data.get("scenario", "family"),
            user_role=data.get("user_role", "owner"),
        )
        fields_data = data.get("fields", {})
        for k, f_data in fields_data.items():
            if isinstance(f_data, dict):
                state.fields[k] = FieldEntry.from_dict(f_data)
            else:
                state.set_field(k, f_data, source=ProvenanceSource.USER_EXPLICIT)
        return state

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> "AgreementState":
        """Initialize state from legacy flat form POST / JSON payload."""
        state = cls(
            agreement_type=data.get("agreement_type", "simple_rental"),
            jurisdiction=data.get("state_code", data.get("jurisdiction", "KA")),
            scenario=data.get("scenario", "family"),
            user_role=data.get("user_role", "owner"),
        )
        for k, v in data.items():
            if k not in ("agreement_type", "state_code", "jurisdiction", "scenario", "user_role") and v is not None:
                state.set_field(k, v, source=ProvenanceSource.USER_EXPLICIT)
        return state
