"""
app/main.py
FastAPI application entry point — serves API + React frontend via static files.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.endpoints import documents
from app.core.config import _ENV_FILE

STATIC_DIR = Path(__file__).parent / "static"


# ── App Lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    logger.info(f"🚀 Document Reading Services started | env={settings.APP_ENV}")
    logger.info(f"   Gemini model: {settings.GEMINI_MODEL}")
    logger.info(f"   Tesseract path: {settings.TESSERACT_PATH}")
    logger.info(f"   Max file size: {settings.MAX_FILE_SIZE_MB}MB")
    logger.info(f"   Frontend: http://{settings.APP_HOST}:{settings.APP_PORT}/")
    if not settings.GEMINI_API_KEY:
        logger.warning("⚠️  GEMINI_API_KEY is not set! Add it to your .env file.")
    yield
    logger.info("🛑 Application shutting down")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="📄 Document Reading Services",
    description=(
        "AI-powered document processing system for Indian government documents.\n\n"
        "**Supported Documents:**\n"
        "- Aadhaar Card\n"
        "- PAN Card\n"
        "- Board Certificates (SSC/HSC/Diploma)\n"
        "- Transfer/Leaving Certificate\n"
        "- Marksheets (10th/12th — Multiple Boards)\n"
        "- Document Expiry Validation\n\n"
        "**Tech Stack:** Google Gemini Free API + Tesseract OCR + FastAPI"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.APP_ENV == "development" else ["yourdomain.com"],
)


# ── Global Exception Handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc} | path={request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.APP_DEBUG else "Contact support",
        },
    )


# ── API Routes ────────────────────────────────────────────────────────────────

app.include_router(documents.router, prefix=f"/api/{settings.API_VERSION}")


@app.get("/health", tags=["Health"])
async def health_check():
    """System health check — verifies OCR and AI connectivity."""
    import pytesseract
    checks = {}
    try:
        ver = pytesseract.get_tesseract_version()
        checks["tesseract"] = f"OK (v{ver})"
    except Exception as e:
        checks["tesseract"] = f"ERROR: {e}"
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        checks["gemini_config"] = "OK" if settings.GEMINI_API_KEY else "MISSING KEY"
    except Exception as e:
        checks["gemini_config"] = f"ERROR: {e}"

    overall = "healthy" if all("ERROR" not in v for v in checks.values()) else "degraded"
    return {
        "status": overall,
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "services": checks,
    }


# ── Serve Frontend (must be after API routes) ─────────────────────────────────

# Serve static assets (CSS/JS/images if any)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serve the main frontend application."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"service": "Document Reading Services", "docs": "/docs"})


# ── Run (development) ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
        log_level="debug" if settings.APP_DEBUG else "info",
    )
