"""
app/services/readers/base_reader.py
Abstract base class for all document readers.
Every reader (Aadhaar, PAN, Marksheet, etc.) inherits from this.
"""
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from app.utils.gemini_client import get_gemini_client
from app.utils.ocr_engine import get_ocr_engine


class DocumentReadResult:
    """Standardized result container for all document reads."""

    def __init__(
        self,
        document_type: str,
        extracted_data: dict[str, Any],
        confidence_score: float,
        ocr_text: str = "",
        processing_time_ms: int = 0,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.document_type = document_type
        self.extracted_data = extracted_data
        self.confidence_score = confidence_score
        self.ocr_text = ocr_text
        self.processing_time_ms = processing_time_ms
        self.warnings = warnings or []
        self.errors = errors or []
        self.success = len(errors or []) == 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "document_type": self.document_type,
            "extracted_data": self.extracted_data,
            "confidence_score": self.confidence_score,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class BaseDocumentReader(ABC):
    """
    Abstract base for all document readers.

    Subclasses must implement:
        - document_type: str property
        - get_extraction_prompt(): returns the Gemini prompt
        - post_process(data): optional cleanup/validation of extracted data
    """

    def __init__(self):
        self.gemini = get_gemini_client()
        self.ocr = get_ocr_engine()

    @property
    @abstractmethod
    def document_type(self) -> str:
        """Human-readable document type name."""
        ...

    @abstractmethod
    def get_extraction_prompt(self) -> str:
        """
        Return the Gemini prompt for extracting fields from this document.
        Should instruct Gemini to return ONLY valid JSON.
        """
        ...

    def post_process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Optional: Override to clean/validate extracted data.
        Default: return as-is.
        """
        return data

    def _compute_image_hash(self, image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()[:16]

    def _get_mime_type(self, filename: str) -> str:
        ext = filename.lower().rsplit(".", 1)[-1]
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "pdf": "application/pdf",
        }.get(ext, "image/jpeg")

    async def read(
        self,
        image_bytes: bytes,
        filename: str = "document.jpg",
        use_ocr: bool = True,
    ) -> DocumentReadResult:
        """
        Main entry point: run OCR + Gemini extraction pipeline.

        Args:
            image_bytes: Raw file bytes (image or PDF)
            filename: Original filename (used for MIME detection)
            use_ocr: Whether to run Tesseract OCR as Gemini hint

        Returns:
            DocumentReadResult with extracted fields
        """
        start_time = time.monotonic()
        warnings: list[str] = []
        errors: list[str] = []

        logger.info(f"[{self.document_type}] Reading document: {filename}")

        try:
            # Step 1: OCR pre-extraction
            ocr_text = ""
            if use_ocr:
                if filename.lower().endswith(".pdf"):
                    ocr_text = self.ocr.extract_text_from_pdf(image_bytes)
                else:
                    ocr_result = self.ocr.extract_with_confidence(image_bytes)
                    ocr_text = ocr_result.get("text", "")
                    avg_conf = ocr_result.get("avg_confidence", 0)
                    if avg_conf < 50:
                        warnings.append(f"Low OCR confidence: {avg_conf:.1f}%. Results may be inaccurate.")

            # Step 2: Gemini extraction
            mime_type = self._get_mime_type(filename)
            prompt = self.get_extraction_prompt()

            raw_data = await self.gemini.extract_from_image(
                image_bytes=image_bytes,
                prompt=prompt,
                mime_type=mime_type,
                ocr_text=ocr_text if ocr_text else None,
            )

            if "error" in raw_data:
                errors.append(raw_data["error"])
                extracted = {}
                confidence = 0.0
            else:
                # Step 3: Post-process
                extracted = self.post_process(raw_data)
                confidence = self._compute_confidence(extracted)

            processing_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                f"[{self.document_type}] Done in {processing_ms}ms | "
                f"confidence={confidence:.2f} | fields={len(extracted)}"
            )

            return DocumentReadResult(
                document_type=self.document_type,
                extracted_data=extracted,
                confidence_score=confidence,
                ocr_text=ocr_text,
                processing_time_ms=processing_ms,
                warnings=warnings,
                errors=errors,
            )

        except Exception as e:
            logger.exception(f"[{self.document_type}] Unexpected error: {e}")
            errors.append(f"Processing failed: {str(e)}")
            return DocumentReadResult(
                document_type=self.document_type,
                extracted_data={},
                confidence_score=0.0,
                processing_time_ms=int((time.monotonic() - start_time) * 1000),
                errors=errors,
            )

    def _compute_confidence(self, data: dict) -> float:
        """
        Simple confidence: ratio of non-null, non-empty fields.
        Override for custom logic.
        """
        if not data:
            return 0.0
        total = len(data)
        filled = sum(
            1 for v in data.values()
            if v is not None and str(v).strip() not in ("", "null", "N/A", "unknown")
        )
        return round(filled / total, 2)
