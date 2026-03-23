"""
app/services/validators/expiry_validator.py
Document Expiry Check Service — validates time-bound government certificates.

Supports:
  - Income Certificate
  - Domicile Certificate
  - Caste Certificate
  - EWS Certificate
  - Non-Creamy Layer Certificate
  - Disability Certificate
  - Any custom document type
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from dateutil import parser as date_parser
from loguru import logger

from app.core.config import settings
from app.utils.gemini_client import get_gemini_client
from app.utils.ocr_engine import get_ocr_engine


class DocumentStatus(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    EXPIRING_SOON = "EXPIRING_SOON"   # within 30 days
    NO_EXPIRY = "NO_EXPIRY"           # document has no expiry
    UNKNOWN = "UNKNOWN"               # could not determine


@dataclass
class ExpiryCheckResult:
    """Result of document expiry validation."""
    document_type: str
    status: DocumentStatus
    issue_date: date | None = None
    expiry_date: date | None = None
    days_remaining: int | None = None
    days_since_expiry: int | None = None
    is_valid: bool = False
    extracted_data: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "document_type": self.document_type,
            "status": self.status.value,
            "is_valid": self.is_valid,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "days_remaining": self.days_remaining,
            "days_since_expiry": self.days_since_expiry,
            "extracted_data": self.extracted_data,
            "warnings": self.warnings,
            "errors": self.errors,
            "processing_time_ms": self.processing_time_ms,
        }


# ── Validity periods per document type ──────────────────────────────────────
VALIDITY_RULES: dict[str, dict] = {
    "income_certificate": {
        "display_name": "Income Certificate",
        "validity_days": settings.INCOME_CERTIFICATE_VALIDITY_DAYS,
        "notes": "Valid for 1 year from issue date",
        "issuing_authority": "Tehsildar / SDM / Revenue Department",
    },
    "domicile_certificate": {
        "display_name": "Domicile Certificate",
        "validity_days": settings.DOMICILE_CERTIFICATE_VALIDITY_DAYS,
        "notes": "Valid for 5 years (permanent in some states)",
        "issuing_authority": "Tehsildar / SDM",
    },
    "caste_certificate": {
        "display_name": "Caste Certificate (OBC/SC/ST)",
        "validity_days": settings.CASTE_CERTIFICATE_VALIDITY_DAYS,
        "notes": "Permanent for SC/ST; OBC valid for 3-5 years (varies by state)",
        "issuing_authority": "District Magistrate / SDM / Tehsildar",
    },
    "ews_certificate": {
        "display_name": "EWS Certificate",
        "validity_days": settings.EWS_CERTIFICATE_VALIDITY_DAYS,
        "notes": "Valid for 1 financial year only",
        "issuing_authority": "Tehsildar / SDM / Revenue Officer",
    },
    "non_creamy_layer": {
        "display_name": "Non-Creamy Layer Certificate",
        "validity_days": 365,
        "notes": "Valid for 1 year; must be renewed annually",
        "issuing_authority": "SDM / Tehsildar",
    },
    "disability_certificate": {
        "display_name": "Disability Certificate (PwD)",
        "validity_days": None,  # Permanent
        "notes": "Usually permanent; some states issue with 5-year renewal",
        "issuing_authority": "Chief Medical Officer / Civil Surgeon",
    },
    "birth_certificate": {
        "display_name": "Birth Certificate",
        "validity_days": None,  # Permanent
        "notes": "Permanent document — no expiry",
        "issuing_authority": "Municipal Corporation / Gram Panchayat",
    },
    "marriage_certificate": {
        "display_name": "Marriage Certificate",
        "validity_days": None,
        "notes": "Permanent document — no expiry",
        "issuing_authority": "Registrar of Marriages",
    },
    "medical_fitness": {
        "display_name": "Medical Fitness Certificate",
        "validity_days": 180,
        "notes": "Valid for 6 months typically",
        "issuing_authority": "Registered Medical Practitioner",
    },
    "character_certificate": {
        "display_name": "Character / Police Clearance Certificate",
        "validity_days": 180,
        "notes": "Valid for 6 months",
        "issuing_authority": "Police Department",
    },
}


class ExpiryValidatorService:
    """
    Service to validate whether a government document is expired.

    Flow:
        1. OCR the document
        2. Gemini extracts issue_date, expiry_date, and document type
        3. Apply validity rules to compute status
    """

    def __init__(self):
        self.gemini = get_gemini_client()
        self.ocr = get_ocr_engine()

    def _get_extraction_prompt(self, doc_type_hint: str = "") -> str:
        type_hint = f"The document appears to be a: {doc_type_hint}." if doc_type_hint else ""
        return f"""
You are an expert at reading Indian government-issued certificates and identifying validity dates.
{type_hint}

Analyze this document and extract date and validity information.
Return ONLY a valid JSON object:
{{
    "document_type": "income_certificate/domicile_certificate/caste_certificate/ews_certificate/non_creamy_layer/disability_certificate/birth_certificate/marriage_certificate/medical_fitness/character_certificate/other",
    "document_type_raw": "Exact document name as printed on document",
    "certificate_number": "Certificate/Document number",
    "holder_name": "Name of certificate holder",
    "issued_to": "Person/entity name if different",
    "issue_date": "Date of issue as DD/MM/YYYY",
    "valid_upto": "Expiry/Valid upto date as DD/MM/YYYY (null if not mentioned)",
    "validity_period_stated": "Validity period as stated in document (e.g., '1 year', '5 years', 'Permanent')",
    "issuing_authority": "Name and designation of issuing officer",
    "issuing_office": "Name of office that issued document",
    "financial_year": "Financial year if mentioned (for EWS/income cert)",
    "purpose": "Purpose mentioned on certificate",
    "seal_present": true,
    "signature_present": true,
    "document_condition": "Good/Damaged/Partially Visible"
}}

Return ONLY the JSON. Use null for missing fields.
"""

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date string to date object, handling Indian formats."""
        if not date_str or date_str == "null":
            return None
        try:
            # Try standard parser
            return date_parser.parse(str(date_str), dayfirst=True).date()
        except Exception:
            # Try regex for DD/MM/YYYY
            match = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", str(date_str))
            if match:
                try:
                    return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                except ValueError:
                    return None
            return None

    def _determine_expiry(
        self,
        doc_type: str,
        issue_date: date | None,
        stated_expiry: date | None,
        validity_stated: str | None,
    ) -> date | None:
        """Determine the actual expiry date using multiple strategies."""

        # Priority 1: Use explicitly stated expiry date from document
        if stated_expiry:
            return stated_expiry

        # Priority 2: Compute from validity stated in document
        if issue_date and validity_stated:
            val_lower = str(validity_stated).lower()
            if "permanent" in val_lower or "lifetime" in val_lower:
                return None  # No expiry
            match = re.search(r"(\d+)\s*(year|month|day)", val_lower)
            if match:
                qty = int(match.group(1))
                unit = match.group(2)
                if unit == "year":
                    return date(issue_date.year + qty, issue_date.month, issue_date.day)
                elif unit == "month":
                    months = issue_date.month + qty
                    year = issue_date.year + (months - 1) // 12
                    month = (months - 1) % 12 + 1
                    return date(year, month, issue_date.day)
                elif unit == "day":
                    return issue_date + timedelta(days=qty)

        # Priority 3: Apply default validity rules
        rule = VALIDITY_RULES.get(doc_type)
        if rule and issue_date:
            validity_days = rule.get("validity_days")
            if validity_days is None:
                return None  # Permanent document
            return issue_date + timedelta(days=validity_days)

        return None

    def _compute_status(
        self,
        expiry_date: date | None,
        issue_date: date | None,
    ) -> tuple[DocumentStatus, int | None, int | None]:
        """Compute document status and remaining days."""
        today = date.today()

        if expiry_date is None:
            # Check if document even has an issue date — if not, unknown
            if issue_date:
                return DocumentStatus.NO_EXPIRY, None, None
            return DocumentStatus.UNKNOWN, None, None

        delta = (expiry_date - today).days

        if delta < 0:
            return DocumentStatus.EXPIRED, None, abs(delta)
        elif delta <= 30:
            return DocumentStatus.EXPIRING_SOON, delta, None
        else:
            return DocumentStatus.VALID, delta, None

    async def check_expiry(
        self,
        image_bytes: bytes,
        filename: str = "certificate.jpg",
        doc_type_hint: str = "",
    ) -> ExpiryCheckResult:
        """
        Main method: check if document is expired.

        Args:
            image_bytes: Raw image/PDF bytes
            filename: Original filename
            doc_type_hint: Optional hint (e.g., "income_certificate")

        Returns:
            ExpiryCheckResult with status and dates
        """
        import time
        start = time.monotonic()
        warnings: list[str] = []
        errors: list[str] = []

        try:
            # OCR
            if filename.lower().endswith(".pdf"):
                ocr_text = self.ocr.extract_text_from_pdf(image_bytes)
            else:
                ocr_result = self.ocr.extract_with_confidence(image_bytes)
                ocr_text = ocr_result.get("text", "")
                if ocr_result.get("avg_confidence", 0) < 50:
                    warnings.append("Low OCR quality — results may be inaccurate")

            # Gemini extraction
            prompt = self._get_extraction_prompt(doc_type_hint)
            raw = await self.gemini.extract_from_image(
                image_bytes=image_bytes,
                prompt=prompt,
                ocr_text=ocr_text or None,
            )

            if "error" in raw:
                errors.append(raw["error"])
                return ExpiryCheckResult(
                    document_type=doc_type_hint or "UNKNOWN",
                    status=DocumentStatus.UNKNOWN,
                    errors=errors,
                    processing_time_ms=int((time.monotonic() - start) * 1000),
                )

            # Parse dates
            doc_type = raw.get("document_type", doc_type_hint or "other")
            issue_date = self._parse_date(raw.get("issue_date"))
            stated_expiry = self._parse_date(raw.get("valid_upto"))
            validity_stated = raw.get("validity_period_stated")

            if not issue_date:
                warnings.append("Could not extract issue date — expiry check may be inaccurate")

            # Determine expiry
            expiry_date = self._determine_expiry(
                doc_type, issue_date, stated_expiry, validity_stated
            )

            # Compute status
            status, days_remaining, days_expired = self._compute_status(expiry_date, issue_date)
            is_valid = status in (DocumentStatus.VALID, DocumentStatus.EXPIRING_SOON, DocumentStatus.NO_EXPIRY)

            # Add rule info to extracted data
            rule = VALIDITY_RULES.get(doc_type, {})
            raw["validity_rule_applied"] = rule.get("notes", "Custom/Unknown")
            raw["standard_validity_days"] = rule.get("validity_days")

            if status == DocumentStatus.EXPIRING_SOON:
                warnings.append(f"Document expires in {days_remaining} days! Please renew soon.")

            processing_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                f"Expiry check complete | type={doc_type} | status={status.value} | "
                f"issue={issue_date} | expiry={expiry_date} | {processing_ms}ms"
            )

            return ExpiryCheckResult(
                document_type=doc_type,
                status=status,
                issue_date=issue_date,
                expiry_date=expiry_date,
                days_remaining=days_remaining,
                days_since_expiry=days_expired,
                is_valid=is_valid,
                extracted_data=raw,
                warnings=warnings,
                errors=errors,
                processing_time_ms=processing_ms,
            )

        except Exception as e:
            logger.exception(f"Expiry check failed: {e}")
            return ExpiryCheckResult(
                document_type=doc_type_hint or "UNKNOWN",
                status=DocumentStatus.UNKNOWN,
                errors=[str(e)],
                processing_time_ms=int((time.monotonic() - start) * 1000),
            )

    def get_all_validity_rules(self) -> dict:
        """Return all validity rules for API reference."""
        return {
            k: {
                "display_name": v["display_name"],
                "validity_days": v.get("validity_days"),
                "notes": v.get("notes"),
                "issuing_authority": v.get("issuing_authority"),
            }
            for k, v in VALIDITY_RULES.items()
        }
