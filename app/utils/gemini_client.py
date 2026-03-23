"""
app/utils/gemini_client.py
Google Gemini API client — handles image + text prompts,
retries, rate-limit backoff, and structured JSON extraction.
"""
import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import google.generativeai as genai
from loguru import logger

from app.core.config import settings


class GeminiClient:
    """
    Wrapper around google-generativeai for document reading tasks.

    Usage:
        client = GeminiClient()
        result = await client.extract_from_image(image_bytes, prompt)
    """

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.1,       # Low temp = deterministic extraction
                top_p=0.95,
                response_mime_type="application/json",  # Force JSON output
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        )

    async def extract_from_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        ocr_text: str | None = None,
    ) -> dict[str, Any]:
        """
        Send image (+ optional OCR text) to Gemini and return parsed JSON.

        Args:
            image_bytes: Raw image bytes
            prompt: Extraction instruction prompt
            mime_type: Image MIME type
            ocr_text: Pre-extracted OCR text to assist Gemini

        Returns:
            Parsed dictionary of extracted fields
        """
        full_prompt = prompt
        if ocr_text:
            full_prompt += f"\n\n--- OCR Pre-extracted Text (use as hint) ---\n{ocr_text}"

        parts = [
            {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()},
            full_prompt,
        ]

        for attempt in range(1, settings.GEMINI_MAX_RETRIES + 1):
            try:
                logger.debug(f"Gemini API call attempt {attempt}")
                response = await asyncio.to_thread(
                    self.model.generate_content, parts
                )
                raw_text = response.text.strip()

                # Strip markdown code fences if present
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]

                parsed = json.loads(raw_text)
                logger.info(f"Gemini extraction successful on attempt {attempt}")
                return parsed

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error attempt {attempt}: {e}")
                if attempt == settings.GEMINI_MAX_RETRIES:
                    return {"error": "Failed to parse Gemini response", "raw": raw_text}

            except Exception as e:
                logger.error(f"Gemini API error attempt {attempt}: {e}")
                if attempt < settings.GEMINI_MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

        return {"error": "Max retries exceeded"}

    async def extract_from_text(self, text: str, prompt: str) -> dict[str, Any]:
        """For text-based document extraction (when OCR already done)."""
        full_prompt = f"{prompt}\n\n--- Document Text ---\n{text}"
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, full_prompt
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Gemini text extraction error: {e}")
            return {"error": str(e)}


# Singleton instance
_gemini_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
