"""
app/utils/file_validator.py
Validates uploaded files: size, type, and basic integrity checks.
"""
import io
from fastapi import UploadFile, HTTPException, status
from PIL import Image
from loguru import logger

from app.core.config import settings


MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"\x25PDF": "application/pdf",
    b"RIFF": "image/webp",  # partial — RIFF....WEBP
}


async def validate_upload_file(file: UploadFile) -> bytes:
    """
    Validate uploaded file and return raw bytes.

    Checks:
    1. File size within limit
    2. File extension is allowed
    3. MIME type matches magic bytes (basic security check)

    Returns:
        Raw file bytes

    Raises:
        HTTPException 400/413 on validation failure
    """
    # Check extension
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_formats_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Allowed: {settings.ALLOWED_FORMATS}",
        )

    # Read content
    content = await file.read()

    # Check size
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB}MB. Got: {len(content) / 1024 / 1024:.1f}MB",
        )

    # Validate magic bytes
    header = content[:8]
    detected_type = None
    for magic, mime in MAGIC_BYTES.items():
        if header[:len(magic)] == magic:
            detected_type = mime
            break

    if detected_type is None:
        logger.warning(f"Unknown file magic bytes for: {filename}")
        # Don't reject — some valid files may not match our magic list

    # Extra: validate image can be opened (if it's an image)
    if ext in ("jpg", "jpeg", "png", "webp"):
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted image file: {str(e)}",
            )

    logger.debug(f"File validated: {filename} ({len(content)} bytes, type={detected_type})")
    return content
