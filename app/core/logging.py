"""
app/core/logging.py
Structured logging with Loguru — production-ready setup
"""
import sys
from loguru import logger
from app.core.config import settings


def setup_logging():
    """Configure Loguru for the application."""
    logger.remove()  # Remove default handler

    log_level = "DEBUG" if settings.APP_DEBUG else "INFO"

    # Console handler — human readable in dev, JSON in prod
    if settings.APP_ENV == "development":
        logger.add(
            sys.stdout,
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
    else:
        # JSON structured logs for production / log aggregators
        logger.add(
            sys.stdout,
            level=log_level,
            serialize=True,  # JSON output
        )

    # File handler — rotate at 50MB, keep 10 days
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="50 MB",
        retention="10 days",
        level="INFO",
        compression="gz",
    )

    # Error-only file for alerting
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        level="ERROR",
    )

    logger.info(f"Logging configured | env={settings.APP_ENV} | level={log_level}")
    return logger
