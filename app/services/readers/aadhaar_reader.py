"""
app/services/readers/aadhaar_reader.py
Aadhaar Card Reader — extracts all fields using Gemini Vision + OCR.
Handles masked Aadhaar (last 4 digits visible) and full Aadhaar.
"""
import re
from typing import Any

from app.services.readers.base_reader import BaseDocumentReader


class AadhaarReader(BaseDocumentReader):
    """
    Extracts from Aadhaar Card:
    - Aadhaar Number (12-digit, formatted as XXXX XXXX XXXX)
    - Full Name
    - Date of Birth (DD/MM/YYYY)
    - Gender
    - Address (full multiline)
    - VID (Virtual ID) if present
    - Issue Date if visible
    """

    @property
    def document_type(self) -> str:
        return "AADHAAR_CARD"

    def get_extraction_prompt(self) -> str:
        return """
You are an expert OCR system specialized in reading Indian Aadhaar cards.
Analyze the provided Aadhaar card image carefully.

Extract ALL visible information and return ONLY a valid JSON object with this exact schema:
{
    "aadhaar_number": "XXXX XXXX XXXX",
    "name": "Full name as printed",
    "name_in_local_language": "Name in regional language if visible",
    "date_of_birth": "DD/MM/YYYY",
    "year_of_birth": "YYYY",
    "gender": "Male/Female/Transgender",
    "address": {
        "house": "House/Flat number",
        "street": "Street/Area",
        "landmark": "Landmark if any",
        "village_town": "Village/Town/City",
        "district": "District",
        "state": "State",
        "pincode": "6-digit pincode"
    },
    "mobile_linked": "Yes/No/Unknown",
    "vid": "Virtual ID if visible, else null",
    "card_type": "Regular/PVC/mAadhaar",
    "is_masked": "true if Aadhaar number is partially hidden",
    "qr_code_present": "true/false"
}

Rules:
- If a field is not visible or not present, use null
- Aadhaar number format: XXXX XXXX XXXX (4-4-4 digits with spaces)
- For masked Aadhaar, show as XXXX XXXX 1234 (X for hidden digits)
- Address should be broken into components if identifiable
- Gender: derive from the document text or context
- Return ONLY the JSON object, no other text
"""

    def post_process(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and clean extracted Aadhaar data."""

        # Clean Aadhaar number — remove extra spaces, validate format
        aadhaar_no = data.get("aadhaar_number", "")
        if aadhaar_no:
            cleaned = re.sub(r"[^0-9X]", "", str(aadhaar_no).upper())
            if len(cleaned) == 12:
                data["aadhaar_number"] = f"{cleaned[:4]} {cleaned[4:8]} {cleaned[8:]}"
            data["is_valid_format"] = bool(re.match(r"^\d{4} \d{4} \d{4}$", data.get("aadhaar_number", "")))
        else:
            data["is_valid_format"] = False

        # Normalize gender
        gender = str(data.get("gender", "")).lower()
        if "male" in gender and "female" not in gender:
            data["gender"] = "Male"
        elif "female" in gender:
            data["gender"] = "Female"
        elif "trans" in gender:
            data["gender"] = "Transgender"

        # Normalize DOB format
        dob = data.get("date_of_birth", "")
        if dob:
            dob_clean = re.sub(r"[^0-9/\-]", "", str(dob))
            data["date_of_birth"] = dob_clean

        # Flatten address for quick access
        addr = data.get("address", {})
        if isinstance(addr, dict):
            parts = [
                addr.get("house"), addr.get("street"), addr.get("landmark"),
                addr.get("village_town"), addr.get("district"),
                addr.get("state"), addr.get("pincode"),
            ]
            data["address_full"] = ", ".join(p for p in parts if p and p != "null")

        return data
