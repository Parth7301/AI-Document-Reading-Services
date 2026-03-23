"""
app/services/readers/tc_reader.py
Transfer Certificate (TC) / Leaving Certificate Reader.
Handles formats from CBSE, ICSE, State Boards, Universities.
"""
import re
from typing import Any

from app.services.readers.base_reader import BaseDocumentReader


class TCReader(BaseDocumentReader):
    """
    Extracts from Transfer/Leaving Certificates:
    - Student details (name, DOB, category)
    - School details
    - Admission & leaving details
    - Academic progress
    - Conduct & character assessment
    - TC serial number
    """

    @property
    def document_type(self) -> str:
        return "TRANSFER_CERTIFICATE"

    def get_extraction_prompt(self) -> str:
        return """
You are an expert document processor for Indian school Transfer Certificates (TC) and Leaving Certificates (LC).

These documents are issued by schools when a student leaves. They contain student details, academic history, and conduct information.

Analyze the document and return ONLY a valid JSON object:
{
    "tc_number": "Serial number of TC",
    "student_name": "Full name of student",
    "fathers_name": "Father's name",
    "mothers_name": "Mother's name",
    "date_of_birth": "DD/MM/YYYY",
    "date_of_birth_in_words": "Date of birth in words if mentioned",
    "gender": "Male/Female",
    "nationality": "Nationality (Indian/etc)",
    "religion": "Religion if mentioned",
    "caste": "Caste/Category (General/OBC/SC/ST)",
    "admission_number": "Student's admission/roll number",
    "date_of_admission": "DD/MM/YYYY",
    "class_of_admission": "Class at time of admission",
    "date_of_leaving": "DD/MM/YYYY",
    "class_of_leaving": "Class at time of leaving (e.g., X, XII)",
    "last_class_studied": "Last class studied",
    "reason_for_leaving": "Reason for leaving school",
    "whether_passed": "Yes/No - whether passed last examination",
    "qualified_for_promotion": "Yes/No",
    "medium": "Medium of instruction",
    "conduct": "Conduct remarks (Good/Very Good/Excellent)",
    "attendance_percentage": "Overall attendance %",
    "fee_dues": "Whether fee dues are clear (Yes/No)",
    "school_name": "Full name of school",
    "school_address": "School address",
    "board_affiliation": "Board affiliation (CBSE/ICSE/State)",
    "affiliation_number": "Board affiliation number",
    "issue_date": "Date of issue of TC",
    "issued_by": "Name/designation of issuing authority"
}

Return ONLY the JSON. Use null for missing fields.
"""

    def post_process(self, data: dict[str, Any]) -> dict[str, Any]:
        # Normalize student name
        if data.get("student_name"):
            data["student_name"] = str(data["student_name"]).strip().title()

        # Clean attendance percentage
        att = data.get("attendance_percentage")
        if att:
            try:
                data["attendance_percentage"] = round(
                    float(str(att).replace("%", "").strip()), 2
                )
            except Exception:
                data["attendance_percentage"] = None

        # Parse leaving class to numeric
        leaving_class = str(data.get("class_of_leaving", "")).upper()
        class_map = {
            "X": 10, "10": 10, "TEN": 10,
            "XII": 12, "12": 12, "TWELVE": 12,
            "IX": 9, "9": 9, "VIII": 8, "8": 8,
        }
        for key, val in class_map.items():
            if key in leaving_class:
                data["class_of_leaving_numeric"] = val
                break

        # Compute duration of study (if both dates are available)
        try:
            from dateutil import parser as date_parser
            adm = date_parser.parse(str(data.get("date_of_admission", "")), dayfirst=True)
            lev = date_parser.parse(str(data.get("date_of_leaving", "")), dayfirst=True)
            delta = lev - adm
            data["total_years_at_school"] = round(delta.days / 365.25, 1)
        except Exception:
            pass

        return data
