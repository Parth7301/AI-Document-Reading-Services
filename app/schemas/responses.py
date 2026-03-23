"""
app/schemas/responses.py
Pydantic schemas for all API request/response models.
"""
from datetime import date
from typing import Any
from pydantic import BaseModel, Field


# ── Generic ──────────────────────────────────────────────────────────────────

class BaseResponse(BaseModel):
    success: bool
    message: str = ""
    errors: list[str] = []
    warnings: list[str] = []
    processing_time_ms: int = 0


class DocumentReadResponse(BaseResponse):
    document_type: str
    extracted_data: dict[str, Any] = {}
    confidence_score: float = Field(ge=0.0, le=1.0)
    ocr_text: str | None = None


# ── Aadhaar ──────────────────────────────────────────────────────────────────

class AadhaarAddress(BaseModel):
    house: str | None = None
    street: str | None = None
    landmark: str | None = None
    village_town: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None


class AadhaarData(BaseModel):
    aadhaar_number: str | None = None
    name: str | None = None
    name_in_local_language: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    address: AadhaarAddress | None = None
    address_full: str | None = None
    is_masked: bool = False
    is_valid_format: bool = False
    qr_code_present: bool = False


class AadhaarResponse(BaseResponse):
    document_type: str = "AADHAAR_CARD"
    extracted_data: AadhaarData | None = None
    confidence_score: float = 0.0


# ── PAN ───────────────────────────────────────────────────────────────────────

class PANData(BaseModel):
    pan_number: str | None = None
    name: str | None = None
    fathers_name: str | None = None
    date_of_birth: str | None = None
    pan_holder_type: str | None = None
    is_valid_pan: bool = False
    state_code: str | None = None


class PANResponse(BaseResponse):
    document_type: str = "PAN_CARD"
    extracted_data: PANData | None = None
    confidence_score: float = 0.0


# ── Marksheet ─────────────────────────────────────────────────────────────────

class SubjectMarks(BaseModel):
    subject_code: str | None = None
    subject_name: str | None = None
    theory_max: float | None = None
    theory_obtained: float | None = None
    practical_max: float | None = None
    practical_obtained: float | None = None
    total_max: float | None = None
    total_obtained: float | None = None
    grade: str | None = None
    result: str | None = None


class MarksheetData(BaseModel):
    student_name: str | None = None
    roll_number: str | None = None
    board_name: str | None = None
    exam_class: str | None = None
    exam_year: str | None = None
    school_name: str | None = None
    subjects: list[SubjectMarks] = []
    total_marks_obtained: float | None = None
    total_marks_maximum: float | None = None
    percentage: float | None = None
    percentage_computed: float | None = None
    best_of_5_percentage: float | None = None
    division: str | None = None
    cgpa: str | None = None
    result: str | None = None


class MarksheetResponse(BaseResponse):
    document_type: str = "MARKSHEET"
    extracted_data: MarksheetData | None = None
    confidence_score: float = 0.0


# ── Expiry Check ──────────────────────────────────────────────────────────────

class ExpiryCheckResponse(BaseResponse):
    document_type: str
    status: str  # VALID / EXPIRED / EXPIRING_SOON / NO_EXPIRY / UNKNOWN
    is_valid: bool = False
    issue_date: date | None = None
    expiry_date: date | None = None
    days_remaining: int | None = None
    days_since_expiry: int | None = None
    extracted_data: dict[str, Any] = {}


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    services: dict[str, str] = {}
