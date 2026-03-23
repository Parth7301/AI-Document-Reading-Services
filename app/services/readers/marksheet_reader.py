"""
app/services/readers/marksheet_reader.py
Marksheet Reader — 10th / 12th grade, multiple Indian board formats.
Extracts subject-wise marks, totals, percentages, and grades.

Supported boards:
  - CBSE (Central Board of Secondary Education)
  - ICSE (Indian Certificate of Secondary Education)
  - Maharashtra State Board (MSBSHSE)
  - UP Board (UPMSP)
  - Tamil Nadu Board (TNBSE)
  - Karnataka SSLC/PUC
  - Rajasthan Board (RBSE)
  - Bihar Board (BSEB)
  - MP Board (MPBSE)
  - Telangana Board (BSET)
"""
import re
from typing import Any

from app.services.readers.base_reader import BaseDocumentReader


class MarksheetReader(BaseDocumentReader):
    """
    Comprehensive marksheet reader supporting multiple Indian boards.
    Extracts subject-wise marks and computes statistics.
    """

    def __init__(self, exam_class: str = "auto"):
        """
        Args:
            exam_class: "10", "12", or "auto" to auto-detect from document
        """
        super().__init__()
        self.exam_class = exam_class

    @property
    def document_type(self) -> str:
        return f"MARKSHEET_{self.exam_class.upper()}"

    def get_extraction_prompt(self) -> str:
        class_hint = ""
        if self.exam_class in ("10", "12"):
            class_hint = f"This is a Class {self.exam_class} marksheet."

        return f"""
You are an expert document reader for Indian school and board examination marksheets.
{class_hint}

Extract ALL subject marks and student details carefully. Pay close attention to tables.

Return ONLY a valid JSON object with this exact schema:
{{
    "student_name": "Full name of student",
    "fathers_name": "Father's name",
    "mothers_name": "Mother's name",
    "roll_number": "Exam roll/seat number",
    "registration_number": "Board registration number",
    "date_of_birth": "DD/MM/YYYY",
    "school_name": "School or college name",
    "school_code": "Institution code",
    "board_name": "CBSE/ICSE/Maharashtra/UP Board/etc",
    "exam_class": "10/12/Other",
    "exam_year": "YYYY",
    "exam_session": "March/April/October/November",
    "medium": "English/Hindi/Marathi/Other",
    "subjects": [
        {{
            "subject_code": "Code if available",
            "subject_name": "Full subject name",
            "theory_max": "Max theory marks (number)",
            "theory_obtained": "Obtained theory marks (number)",
            "practical_max": "Max practical marks or null",
            "practical_obtained": "Obtained practical marks or null",
            "internal_max": "Max internal/IA marks or null",
            "internal_obtained": "Obtained internal marks or null",
            "total_max": "Total max marks",
            "total_obtained": "Total obtained marks",
            "grade": "Grade for this subject",
            "grade_points": "Grade points (for CBSE CGPA)",
            "result": "PASS/FAIL/ABSENT/EXEMPTED"
        }}
    ],
    "total_marks_obtained": "Sum of all obtained marks",
    "total_marks_maximum": "Sum of all maximum marks",
    "percentage": "Percentage as decimal number",
    "cgpa": "CGPA if CBSE grading system",
    "overall_grade": "Overall grade/division",
    "result": "PASS/FAIL/COMPARTMENT/WITHHELD",
    "distinction": "Yes/No",
    "merit_rank": "Rank if mentioned",
    "special_remarks": "Any special remarks or achievements",
    "certificate_number": "Marksheet certificate number",
    "issue_date": "Date of issue"
}}

IMPORTANT:
- Extract EVERY subject from the marks table, even if there are 8-10 subjects
- Marks should be numbers only (no units)
- If a subject has no practical, set practical fields to null
- Return ONLY the JSON object, no explanation
"""

    def post_process(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate marks, compute statistics, detect board type."""

        subjects = data.get("subjects", [])

        # Clean and validate each subject
        for subj in subjects:
            for field in ["theory_max", "theory_obtained", "practical_max",
                          "practical_obtained", "total_max", "total_obtained",
                          "internal_max", "internal_obtained"]:
                val = subj.get(field)
                if val is not None and val != "null":
                    try:
                        subj[field] = float(str(val))
                    except (ValueError, TypeError):
                        subj[field] = None
                else:
                    subj[field] = None

        # Recompute totals from subjects if missing
        if subjects and not data.get("total_marks_obtained"):
            computed_obtained = sum(
                s.get("total_obtained") or 0
                for s in subjects
                if s.get("total_obtained") is not None
            )
            computed_max = sum(
                s.get("total_max") or 0
                for s in subjects
                if s.get("total_max") is not None
            )
            if computed_obtained > 0:
                data["total_marks_obtained"] = computed_obtained
                data["total_marks_maximum"] = computed_max

        # Recompute percentage
        obtained = data.get("total_marks_obtained")
        maximum = data.get("total_marks_maximum")
        if obtained and maximum and float(maximum) > 0:
            computed_pct = round((float(obtained) / float(maximum)) * 100, 2)
            data["percentage"] = data.get("percentage") or computed_pct
            data["percentage_computed"] = computed_pct

        # Subject count
        data["total_subjects"] = len(subjects)
        data["subjects_passed"] = sum(
            1 for s in subjects
            if str(s.get("result", "")).upper() == "PASS"
        )
        data["subjects_failed"] = sum(
            1 for s in subjects
            if str(s.get("result", "")).upper() == "FAIL"
        )

        # Best-of-5 percentage (used in many boards for admission)
        if subjects:
            subject_pcts = []
            for s in subjects:
                tot = s.get("total_obtained")
                mx = s.get("total_max")
                if tot is not None and mx and float(mx) > 0:
                    subject_pcts.append((float(tot) / float(mx)) * 100)
            if len(subject_pcts) >= 5:
                subject_pcts.sort(reverse=True)
                data["best_of_5_percentage"] = round(sum(subject_pcts[:5]) / 5, 2)

        # Assign division from percentage
        pct = data.get("percentage")
        if pct:
            try:
                p = float(pct)
                if p >= 75:
                    data["division"] = "Distinction"
                elif p >= 60:
                    data["division"] = "First Division"
                elif p >= 45:
                    data["division"] = "Second Division"
                elif p >= 33:
                    data["division"] = "Third Division"
                else:
                    data["division"] = "Fail"
            except Exception:
                pass

        # Normalize student name
        if data.get("student_name"):
            data["student_name"] = str(data["student_name"]).strip().title()

        return data

    def _compute_confidence(self, data: dict) -> float:
        """Higher confidence if subjects list is populated."""
        base = super()._compute_confidence(data)
        subjects = data.get("subjects", [])
        subject_bonus = min(len(subjects) * 0.05, 0.3)
        return min(base + subject_bonus, 1.0)
