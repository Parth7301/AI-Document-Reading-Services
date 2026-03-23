"""
app/api/v1/endpoints/documents.py
FastAPI route handlers for all document reading services.
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from loguru import logger

from app.services.readers.aadhaar_reader import AadhaarReader
from app.services.readers.pan_reader import PANReader
from app.services.readers.board_certificate_reader import BoardCertificateReader
from app.services.readers.tc_reader import TCReader
from app.services.readers.marksheet_reader import MarksheetReader
from app.services.validators.expiry_validator import ExpiryValidatorService, VALIDITY_RULES
from app.utils.file_validator import validate_upload_file


router = APIRouter(prefix="/documents", tags=["Document Reading Services"])


# ── Aadhaar ──────────────────────────────────────────────────────────────────

@router.post(
    "/aadhaar/read",
    summary="Extract details from Aadhaar Card",
    description="Upload an Aadhaar card image (JPG/PNG/PDF) and extract all fields using Gemini AI + OCR.",
)
async def read_aadhaar(
    file: UploadFile = File(..., description="Aadhaar card image or PDF"),
    use_ocr: bool = Form(True, description="Enable OCR pre-processing"),
):
    content = await validate_upload_file(file)
    reader = AadhaarReader()
    result = await reader.read(content, file.filename or "aadhaar.jpg", use_ocr=use_ocr)
    return JSONResponse(content=result.to_dict(), status_code=200 if result.success else 422)


# ── PAN Card ─────────────────────────────────────────────────────────────────

@router.post(
    "/pan/read",
    summary="Extract details from PAN Card",
    description="Upload a PAN card image and extract PAN number, name, DOB, father's name.",
)
async def read_pan(
    file: UploadFile = File(..., description="PAN card image or PDF"),
    use_ocr: bool = Form(True),
):
    content = await validate_upload_file(file)
    reader = PANReader()
    result = await reader.read(content, file.filename or "pan.jpg", use_ocr=use_ocr)
    return JSONResponse(content=result.to_dict(), status_code=200 if result.success else 422)


# ── Board Certificate ─────────────────────────────────────────────────────────

@router.post(
    "/board-certificate/read",
    summary="Extract details from Board Certificate (SSC/HSC/Diploma)",
    description="Upload a board passing certificate to extract student details, result, and certification info.",
)
async def read_board_certificate(
    file: UploadFile = File(..., description="Board certificate image or PDF"),
    use_ocr: bool = Form(True),
):
    content = await validate_upload_file(file)
    reader = BoardCertificateReader()
    result = await reader.read(content, file.filename or "certificate.jpg", use_ocr=use_ocr)
    return JSONResponse(content=result.to_dict(), status_code=200 if result.success else 422)


# ── Transfer Certificate ──────────────────────────────────────────────────────

@router.post(
    "/tc/read",
    summary="Extract details from Transfer/Leaving Certificate",
    description="Upload a TC/LC to extract student name, admission/leaving dates, conduct, and school details.",
)
async def read_tc(
    file: UploadFile = File(..., description="Transfer/Leaving Certificate image or PDF"),
    use_ocr: bool = Form(True),
):
    content = await validate_upload_file(file)
    reader = TCReader()
    result = await reader.read(content, file.filename or "tc.jpg", use_ocr=use_ocr)
    return JSONResponse(content=result.to_dict(), status_code=200 if result.success else 422)


# ── Marksheet ─────────────────────────────────────────────────────────────────

@router.post(
    "/marksheet/read",
    summary="Extract marks from 10th/12th Marksheet",
    description=(
        "Upload a marksheet to extract subject-wise marks, percentage, and grade. "
        "Supports CBSE, ICSE, Maharashtra, UP, TN, Karnataka, and other state boards."
    ),
)
async def read_marksheet(
    file: UploadFile = File(..., description="Marksheet image or PDF"),
    exam_class: str = Form("auto", description="Exam class: '10', '12', or 'auto'"),
    use_ocr: bool = Form(True),
):
    if exam_class not in ("10", "12", "auto"):
        raise HTTPException(status_code=400, detail="exam_class must be '10', '12', or 'auto'")

    content = await validate_upload_file(file)
    reader = MarksheetReader(exam_class=exam_class)
    result = await reader.read(content, file.filename or "marksheet.jpg", use_ocr=use_ocr)
    return JSONResponse(content=result.to_dict(), status_code=200 if result.success else 422)


# ── Expiry Check ──────────────────────────────────────────────────────────────

@router.post(
    "/expiry/check",
    summary="Check document expiry status",
    description=(
        "Upload any time-bound government certificate to check if it is valid, expired, "
        "or expiring soon. Supports Income Certificate, Domicile, Caste, EWS, etc."
    ),
)
async def check_document_expiry(
    file: UploadFile = File(..., description="Government certificate image or PDF"),
    doc_type_hint: str = Form(
        "",
        description="Optional hint: income_certificate / domicile_certificate / caste_certificate / ews_certificate / etc.",
    ),
):
    content = await validate_upload_file(file)
    service = ExpiryValidatorService()
    result = await service.check_expiry(content, file.filename or "certificate.jpg", doc_type_hint)
    return JSONResponse(content=result.to_dict(), status_code=200)


@router.get(
    "/expiry/validity-rules",
    summary="Get validity rules for all supported document types",
    description="Returns the standard validity periods for all government documents.",
)
async def get_validity_rules():
    service = ExpiryValidatorService()
    return {"rules": service.get_all_validity_rules()}


# ── Batch Read ────────────────────────────────────────────────────────────────

@router.post(
    "/batch/read",
    summary="Read multiple documents in one request",
    description="Upload multiple document files. Returns results for each file.",
)
async def batch_read(
    files: list[UploadFile] = File(..., description="Multiple document files"),
    doc_types: str = Form("auto", description="Comma-separated doc types (auto/aadhaar/pan/marksheet/tc/certificate/expiry)"),
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch request")

    doc_type_list = [t.strip() for t in doc_types.split(",")]
    if len(doc_type_list) == 1:
        doc_type_list = doc_type_list * len(files)

    reader_map = {
        "aadhaar": AadhaarReader,
        "pan": PANReader,
        "marksheet": MarksheetReader,
        "tc": TCReader,
        "certificate": BoardCertificateReader,
    }

    results = []
    for i, file in enumerate(files):
        doc_type = doc_type_list[i] if i < len(doc_type_list) else "auto"
        content = await validate_upload_file(file)

        try:
            if doc_type == "expiry":
                svc = ExpiryValidatorService()
                res = await svc.check_expiry(content, file.filename or "doc.jpg")
                results.append({"filename": file.filename, **res.to_dict()})
            elif doc_type in reader_map:
                reader = reader_map[doc_type]()
                res = await reader.read(content, file.filename or "doc.jpg")
                results.append({"filename": file.filename, **res.to_dict()})
            else:
                results.append({"filename": file.filename, "error": f"Unknown doc_type: {doc_type}"})
        except Exception as e:
            logger.error(f"Batch read error for {file.filename}: {e}")
            results.append({"filename": file.filename, "error": str(e)})

    return {"total": len(results), "results": results}
