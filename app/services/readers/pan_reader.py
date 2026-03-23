"""
app/services/readers/pan_reader.py
PAN Card Reader — Income Tax Department of India
Extracts PAN number, name, father's name, DOB, and validates PAN format.
"""
import re
from typing import Any

from app.services.readers.base_reader import BaseDocumentReader


class PANReader(BaseDocumentReader):
    """
    Extracts from PAN Card:
    - PAN Number (AAAAA0000A format)
    - Name of Card Holder
    - Father's Name
    - Date of Birth
    - Signature presence
    - Photo presence
    """

    @property
    def document_type(self) -> str:
        return "PAN_CARD"

    def get_extraction_prompt(self) -> str:
        return """
You are an expert document reader specialized in Indian PAN (Permanent Account Number) cards issued by Income Tax Department of India.

Carefully read the PAN card image and extract all visible details.

Return ONLY a valid JSON object with this exact schema:
{
    "pan_number": "ABCDE1234F",
    "name": "Card holder's name as printed",
    "fathers_name": "Father's name as printed",
    "date_of_birth": "DD/MM/YYYY",
    "aadhaar_linked": "Yes/No/Unknown",
    "pan_type": "Individual/Company/HUF/Firm/etc",
    "issuing_authority": "Income Tax Department, Govt of India",
    "photo_present": true,
    "signature_present": true,
    "card_condition": "Good/Damaged/Partially Visible"
}

PAN Number Format Rules:
- Exactly 10 characters: 5 letters + 4 digits + 1 letter
- Format: AAAAA0000A
- All uppercase
- 4th character indicates taxpayer type: P=Person, C=Company, H=HUF, F=Firm, A=AOP, T=Trust, B=BOI

Return ONLY the JSON, no explanation or other text.
"""

    def post_process(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate PAN number format and normalize data."""

        pan = str(data.get("pan_number", "")).upper().strip()
        pan_clean = re.sub(r"[^A-Z0-9]", "", pan)

        # Validate PAN format: AAAAA0000A
        pan_pattern = re.compile(r"^[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]$")
        data["pan_number"] = pan_clean
        data["is_valid_pan"] = bool(pan_pattern.match(pan_clean))

        if pan_clean and len(pan_clean) == 10:
            # Decode PAN type from 4th character
            type_map = {
                "P": "Individual (Person)",
                "C": "Company",
                "H": "Hindu Undivided Family (HUF)",
                "F": "Firm / LLP",
                "A": "Association of Persons (AOP)",
                "T": "Trust",
                "B": "Body of Individuals",
                "L": "Local Authority",
                "J": "Artificial Juridical Person",
                "G": "Government",
            }
            pan_type_char = pan_clean[3] if len(pan_clean) > 3 else ""
            data["pan_holder_type"] = type_map.get(pan_type_char, "Unknown")
            data["state_code"] = pan_clean[:2]  # First 2 chars = jurisdiction

        # Clean DOB
        dob = data.get("date_of_birth", "")
        if dob:
            data["date_of_birth"] = re.sub(r"[^0-9/\-]", "", str(dob))

        # Normalize names to title case
        for field in ["name", "fathers_name"]:
            if data.get(field):
                data[field] = str(data[field]).strip().title()

        return data
