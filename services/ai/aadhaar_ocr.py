"""
services/ai/aadhaar_ocr.py — Aadhaar Document OCR Extraction Service
====================================================================
Offline digital PDF parser and multimodal Gemini Vision OCR for Indian Aadhaar cards.
Safely extracts party details, relations, and addresses without persisting PII.
"""

import json
import logging
import re
from datetime import datetime
from config import Config

logger = logging.getLogger("AgreementAI_AadhaarOCR")


class AadhaarOcrError(RuntimeError):
    """Raised when a real Aadhaar OCR response cannot be produced."""


class AadhaarOcrService:
    """Extracts structured legal party attributes from Aadhaar cards (images or digital PDFs)."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.gemini_key = Config.GEMINI_API_KEY

    def extract_aadhaar_ocr(self, document_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Extract structured party details from an Aadhaar image or a multi-page PDF."""
        # 1. Fast Offline Digital PDF Extraction (Zero API cost, instant execution)
        if mime_type == "application/pdf":
            try:
                import fitz
                pdf_doc = fitz.open(stream=document_bytes, filetype="pdf")
                raw_text = "\n".join([page.get_text() for page in pdf_doc])
                pdf_doc.close()

                if raw_text and len(raw_text.strip()) >= 50:
                    digital_extracted = self._parse_digital_aadhaar_text(raw_text)
                    if digital_extracted.get("full_name"):
                        logger.info("Aadhaar details successfully extracted via offline digital PDF parser.")
                        return digital_extracted
            except Exception as pdf_err:
                logger.warning(f"Offline PDF extraction failed, falling back to vision: {pdf_err}")

        # 2. Vision OCR via Gemini Multimodal Models
        if self.provider != "gemini" or not self.gemini_key:
            raise AadhaarOcrError("Aadhaar OCR is not configured. Set AI_PROVIDER=gemini and GEMINI_API_KEY.")

        try:
            from google import genai
            from google.genai import types

            document_parts = []
            if mime_type == "application/pdf":
                import fitz  # PyMuPDF
                pdf = fitz.open(stream=document_bytes, filetype="pdf")
                try:
                    for page in list(pdf)[:2]:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        document_parts.append(types.Part.from_bytes(data=pix.tobytes("png"), mime_type="image/png"))
                finally:
                    pdf.close()
            else:
                document_parts.append(types.Part.from_bytes(data=document_bytes, mime_type=mime_type))

            if not document_parts:
                raise AadhaarOcrError("The uploaded document does not contain readable pages.")

            prompt = """
Extract the visible details from this Indian Aadhaar document. Return only a JSON object with these keys:
full_name, relation_type, relation_name, date_of_birth, gender, aadhaar_masked, address_line1, locality, city, state, pincode.
Use relation_type only as S/O, W/O, D/O, C/O, or an empty string. Convert date_of_birth to YYYY-MM-DD when visible.
Never invent values. Use an empty string for a value that is absent or unclear. Always mask the Aadhaar number as XXXX-XXXX-last4.
"""
            model_candidates = [
                "gemini-2.5-flash",
                "gemini-3.6-flash",
                "gemini-2.5-flash-preview",
            ]

            client = genai.Client(api_key=self.gemini_key)
            response = None
            last_err = None

            for model_name in model_candidates:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[*document_parts, prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json"),
                    )
                    if response and response.text:
                        break
                except Exception as m_err:
                    last_err = m_err
                    err_str = str(m_err)
                    logger.warning(f"Aadhaar OCR notice with {model_name}: {m_err}")
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        import time as _time
                        retry_match = re.search(r'retry in (\d+)', err_str, re.I)
                        wait_secs = min(int(retry_match.group(1)), 15) if retry_match else 5
                        logger.info(f"Rate limited on {model_name}, waiting {wait_secs}s before next model...")
                        _time.sleep(wait_secs)
                    continue

            if not response or not response.text:
                if last_err and ("429" in str(last_err) or "RESOURCE_EXHAUSTED" in str(last_err)):
                    raise AadhaarOcrError("Gemini OCR quota limit reached. Please upload an official e-Aadhaar PDF or type details directly.")
                if last_err and ("503" in str(last_err) or "UNAVAILABLE" in str(last_err)):
                    raise AadhaarOcrError("Google Gemini Vision service is currently experiencing a temporary server spike. Please re-upload or upload a digital PDF.")
                raise AadhaarOcrError(f"Could not extract Aadhaar fields: {last_err}")

            extracted = json.loads((response.text or "").strip())
            if not isinstance(extracted, dict) or not extracted.get("full_name"):
                raise AadhaarOcrError("Gemini could not read a name from this Aadhaar document. Please upload a clearer image.")

            # 1. Compute Age from date_of_birth if present
            dob = extracted.get("date_of_birth", "")
            if dob:
                dob_match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})|(\d{1,2})[-/](\d{1,2})[-/](\d{4})', dob)
                if dob_match:
                    birth_year = int(dob_match.group(1) or dob_match.group(6))
                    current_year = datetime.now().year
                    if 1900 < birth_year < current_year:
                        extracted["age"] = str(current_year - birth_year)

            # 2. Normalize Care of Relation
            rel_type = (extracted.get("relation_type") or "").upper()
            if "W/O" in rel_type or "WIFE" in rel_type or "HUSBAND" in rel_type:
                extracted["careof"] = "Husband Name"
            else:
                extracted["careof"] = "Father Name"

            # 2b. Derive name prefix (Mr./Ms.) from gender and relation_type
            gender_raw = (extracted.get("gender") or "").upper().strip()
            if gender_raw in ("MALE", "M") or "S/O" in rel_type:
                extracted["prefix"] = "Mr."
            elif gender_raw in ("FEMALE", "F") or "D/O" in rel_type or "W/O" in rel_type:
                extracted["prefix"] = "Ms."
            extracted["careofname_prefix"] = "Mr."

            # 3. Assemble complete postal address
            addr_parts = []
            for k in ("address_line1", "locality", "city", "state", "pincode"):
                val = extracted.get(k)
                if val and str(val).strip():
                    addr_parts.append(str(val).strip())
            if addr_parts:
                extracted["full_address"] = ", ".join(addr_parts)

            return extracted
        except AadhaarOcrError:
            raise
        except Exception as error:
            logger.exception("Gemini Aadhaar OCR failed")
            raise AadhaarOcrError(f"Gemini could not process this Aadhaar document: {error}") from error

    def _parse_digital_aadhaar_text(self, raw_text: str) -> dict:
        """Parse structured Aadhaar attributes directly from digital PDF text stream."""
        extracted = {}

        # 1. Full Legal Name
        name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\n\s*(?:S/O|W/O|D/O|C/O|DOB|Date of Birth|\n\s*DOB)', raw_text)
        if not name_match:
            name_match = re.search(r'To\s*\n+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', raw_text, re.I)
        if name_match:
            extracted["full_name"] = name_match.group(1).strip()

        # 2. DOB / Age
        dob_match = re.search(r'\b(?:DOB|Date of Birth)\s*:?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})', raw_text, re.I)
        if dob_match:
            dob_str = dob_match.group(1).strip()
            extracted["date_of_birth"] = dob_str
            try:
                birth_year = int(dob_str.split('/')[-1].split('-')[-1])
                curr_year = datetime.now().year
                if 1900 < birth_year < curr_year:
                    extracted["age"] = str(curr_year - birth_year)
            except Exception:
                pass

        # 3. Care of (Father / Husband)
        careof_match = re.search(r'\b(S/O|W/O|D/O|C/O)\s*:?\s*([A-Za-z]+(?:\s+[A-Za-z]+)+)', raw_text, re.I)
        if careof_match:
            rel_type = careof_match.group(1).upper()
            rel_name = careof_match.group(2).split('\n')[0].split(',')[0].strip()
            extracted["relation_type"] = rel_type
            extracted["relation_name"] = rel_name
            extracted["careof"] = "Husband Name" if "W/O" in rel_type else "Father Name"

        # 4. Full Address & Pincode
        addr_match = re.search(r'Address\s*:\s*([\s\S]+?)(?=\b\d{4}\s+\d{4}\s+\d{4}\b|VID\s*:|\n\s*\n\s*\d|\Z)', raw_text, re.I)
        if addr_match:
            raw_addr = addr_match.group(1).strip()
            clean_addr = " ".join(raw_addr.split())
            clean_addr = re.sub(r'^(?:S/O|W/O|D/O|C/O)\s*:?\s*[^,]+,\s*', '', clean_addr, flags=re.I)
            extracted["full_address"] = clean_addr

            pin_match = re.search(r'\b(\d{6})\b', clean_addr)
            if pin_match:
                extracted["pincode"] = pin_match.group(1)

        # 5. Masked Aadhaar
        aadhaar_match = re.search(r'\b(\d{4}\s+\d{4}\s+\d{4})\b', raw_text)
        if aadhaar_match:
            last4 = aadhaar_match.group(1).replace(" ", "")[-4:]
            extracted["aadhaar_masked"] = f"XXXX-XXXX-{last4}"

        # 6. Derive name prefix (Mr./Ms.) from gender text or relation_type
        gender_match = re.search(r'\b(MALE|FEMALE)\b', raw_text, re.I)
        gender_raw = (gender_match.group(1).upper() if gender_match else "")
        rel_type_raw = (extracted.get("relation_type") or "").upper()
        if gender_raw == "MALE" or "S/O" in rel_type_raw:
            extracted["prefix"] = "Mr."
        elif gender_raw == "FEMALE" or "D/O" in rel_type_raw or "W/O" in rel_type_raw:
            extracted["prefix"] = "Ms."
        extracted["careofname_prefix"] = "Mr."

        return extracted

    @staticmethod
    def _mock_aadhaar_ocr() -> dict:
        return {
            "full_name": "Rahul Ramesh Sharma",
            "relation_type": "S/O",
            "relation_name": "Suresh Sharma",
            "date_of_birth": "1992-08-15",
            "gender": "Male",
            "aadhaar_masked": "XXXX-XXXX-8912",
            "address_line1": "Flat 302, Green Acres Apartment",
            "locality": "10th Main, HSR Layout Sector 1",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560102",
            "is_ocr_verified": False
        }
