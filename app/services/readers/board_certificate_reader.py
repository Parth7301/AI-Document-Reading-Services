"""
app/services/readers/board_certificate_reader.py
Board Certificate Reader — SSC, HSC, Diploma, Degree certificates.
Supports CBSE, ICSE, State Boards (Maharashtra, UP, TN, Karnataka, etc.)
"""
import re
from typing import Any

from app.services.readers.base_reader import BaseDocumentReader


class BoardCertificateReader(BaseDocumentReader):
    """
    Extracts from Board Certificates:
    - Student name, Roll number, Seat number
    - Board name and examination type
    - Result (Pass/Fail/Distinction)
    - Year, Month of examination
    - School/College details
    - Division/Grade/Percentage
    """

    @property
    def document_type(self) -> str:
        return "BOARD_CERTIFICATE"

    def get_extraction_prompt(self) -> str:
        return """
You are a specialized OCR system for reading Indian educational board certificates and marksheets.
This may be an SSC (10th), HSC (12th), Diploma, or degree passing certificate.

Analyze the certificate carefully and return ONLY a valid JSON object:
{
    "student_name": "Full name of student",
    "mother_name": "Mother's name if printed",
    "father_name": "Father's name if printed",
    "roll_number": "Examination roll number",
    "seat_number": "Seat/Hall ticket number",
    "registration_number": "Board registration number",
    "date_of_birth": "DD/MM/YYYY",
    "examination_type": "SSC/HSC/Diploma/Degree/Other",
    "board_name": "CBSE/ICSE/Maharashtra State Board/UP Board/etc",
    "school_name": "Name of school or college",
    "school_code": "Institution code if present",
    "exam_year": "YYYY",
    "exam_month": "Month of exam",
    "result": "PASS/FAIL/DISTINCTION/FIRST CLASS/SECOND CLASS/WITHHELD",
    "division": "First/Second/Third/Distinction",
    "percentage": "Percentage as number (e.g., 85.40)",
    "grade": "Overall grade if mentioned",
    "certificate_number": "Unique certificate/document number",
    "issue_date": "Date certificate was issued DD/MM/YYYY",
    "medium": "Medium of instruction (English/Hindi/Marathi/etc)",
    "attempt": "Regular/Ex-student/ATKT"
}

Rules:
- Extract exactly as printed on the certificate
- Percentage should be a number without % symbol
- Use null for any field not visible or not applicable
- Return ONLY the JSON object
"""

    def post_process(self, data: dict[str, Any]) -> dict[str, Any]:
        # Normalize percentage
        pct = data.get("percentage")
        if pct:
            try:
                data["percentage"] = round(float(str(pct).replace("%", "").strip()), 2)
            except (ValueError, TypeError):
                data["percentage"] = None

        # Normalize result to standard values
        result = str(data.get("result", "")).upper()
        if "DISTINCTION" in result:
            data["result"] = "DISTINCTION"
            data["division"] = data.get("division") or "Distinction"
        elif "FIRST" in result:
            data["result"] = "PASS"
            data["division"] = "First Class"
        elif "SECOND" in result:
            data["result"] = "PASS"
            data["division"] = "Second Class"
        elif "FAIL" in result:
            data["result"] = "FAIL"
        elif "PASS" in result:
            data["result"] = "PASS"

        # Auto-detect board from name
        board_name = str(data.get("board_name", "")).upper()
        board_map = {
            "CBSE": "Central Board of Secondary Education",
            "ICSE": "Indian Certificate of Secondary Education",
            "MAHARASHTRA": "Maharashtra State Board (MSBSHSE)",
            "UTTAR PRADESH": "UP Madhyamik Shiksha Parishad",
            "SSC": "Secondary School Certificate Board",
        }
        for key, full_name in board_map.items():
            if key in board_name:
                data["board_full_name"] = full_name
                break

        # Compute grade from percentage
        pct_val = data.get("percentage")
        if pct_val:
            try:
                p = float(pct_val)
                if p >= 90:
                    data["computed_grade"] = "O (Outstanding)"
                elif p >= 75:
                    data["computed_grade"] = "A+ (Excellent)"
                elif p >= 60:
                    data["computed_grade"] = "A (Very Good)"
                elif p >= 50:
                    data["computed_grade"] = "B (Good)"
                elif p >= 35:
                    data["computed_grade"] = "C (Pass)"
                else:
                    data["computed_grade"] = "F (Fail)"
            except Exception:
                pass

        # Normalize student name
        if data.get("student_name"):
            data["student_name"] = str(data["student_name"]).strip().title()

        return data
