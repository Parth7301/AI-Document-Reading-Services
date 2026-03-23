"""
app/utils/ocr_engine.py
OCR Engine — Tesseract wrapper with image preprocessing.
Preprocessing significantly improves accuracy on government documents.
"""
import io
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
from loguru import logger

from app.core.config import settings

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH


class OCREngine:
    """
    Multi-stage OCR with preprocessing pipeline:
    1. Deskew
    2. Denoise
    3. Binarize (adaptive threshold)
    4. Tesseract extraction
    """

    def __init__(self, lang: str = settings.TESSERACT_LANG):
        self.lang = lang
        self.config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Apply OpenCV preprocessing pipeline for better OCR accuracy."""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Noise removal via morphological operations
        kernel = np.ones((1, 1), np.uint8)
        denoised = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

        # Adaptive threshold — handles uneven lighting
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11, C=2,
        )

        # Deskew
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 0.5:  # Only rotate if skew > 0.5 degrees
                (h, w) = binary.shape[:2]
                M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return binary

    def extract_text(self, image_bytes: bytes) -> str:
        """
        Extract text from image bytes.

        Returns:
            Extracted text string
        """
        try:
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                # Fallback: try PIL
                pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            processed = self.preprocess_image(img)
            text = pytesseract.image_to_string(processed, lang=self.lang, config=self.config)
            logger.debug(f"OCR extracted {len(text)} characters")
            return text.strip()

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return ""

    def extract_text_from_pdf(self, pdf_bytes: bytes, dpi: int = 200) -> str:
        """Convert PDF pages to images, then OCR each page."""
        try:
            pages = convert_from_bytes(pdf_bytes, dpi=dpi)
            all_text = []
            for i, page in enumerate(pages):
                img_bytes = io.BytesIO()
                page.save(img_bytes, format="JPEG", quality=95)
                text = self.extract_text(img_bytes.getvalue())
                all_text.append(f"--- Page {i + 1} ---\n{text}")
            return "\n\n".join(all_text)
        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            return ""

    def extract_with_confidence(self, image_bytes: bytes) -> dict:
        """Return text with per-word confidence scores (for quality checking)."""
        try:
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            processed = self.preprocess_image(img)
            data = pytesseract.image_to_data(
                processed, lang=self.lang,
                output_type=pytesseract.Output.DICT
            )
            words = []
            confidences = []
            for i, word in enumerate(data["text"]):
                conf = data["conf"][i]
                if word.strip() and int(conf) > 0:
                    words.append(word)
                    confidences.append(int(conf))

            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            return {
                "text": " ".join(words),
                "avg_confidence": round(avg_conf, 2),
                "word_count": len(words),
            }
        except Exception as e:
            logger.error(f"OCR with confidence failed: {e}")
            return {"text": "", "avg_confidence": 0, "word_count": 0}


def image_to_bytes(image: Image.Image, fmt: str = "JPEG") -> bytes:
    """Convert PIL Image to bytes."""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


# Singleton
_ocr_engine: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine()
    return _ocr_engine
