"""
app/core/config.py
Central configuration using Pydantic Settings — reads from .env
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False
    SECRET_KEY: str = "Your_Secret_Key"
    API_VERSION: str = "v1"

    # Gemini
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_TIMEOUT_SECONDS: int = 30

    # OCR
    TESSERACT_PATH: str = "C:/Program Files/Tesseract-OCR/tesseract.exe"
    TESSERACT_LANG: str = "eng+hin+mar"

    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_FORMATS: str = "jpg,jpeg,png,pdf,webp"
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:7301@localhost/docreader"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600

    # Expiry (days)
    INCOME_CERTIFICATE_VALIDITY_DAYS: int = 365
    DOMICILE_CERTIFICATE_VALIDITY_DAYS: int = 1825
    CASTE_CERTIFICATE_VALIDITY_DAYS: int = 1825
    EWS_CERTIFICATE_VALIDITY_DAYS: int = 365

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    @property
    def allowed_formats_list(self) -> list[str]:
        return [fmt.strip().lower() for fmt in self.ALLOWED_FORMATS.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
