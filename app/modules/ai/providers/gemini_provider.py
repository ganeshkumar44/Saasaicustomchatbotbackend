"""Google Gemini AI provider."""

import logging
from functools import lru_cache

from google import genai
from google.genai.errors import ClientError

from app.core.config import get_settings
from app.modules.ai.exceptions import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiQuotaExceededError,
)
from app.modules.ai.providers.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


@lru_cache
def _get_gemini_client() -> genai.Client:
    """Return a cached Gemini client configured from application settings."""
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise GeminiAPIKeyMissingError()
    return genai.Client(api_key=settings.GEMINI_API_KEY)


class GeminiProvider(BaseAIProvider):
    """Generate answers using Google Gemini."""

    def generate_answer(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the generated answer text."""
        settings = get_settings()
        client = _get_gemini_client()

        logger.info("Sending request to Gemini model=%s", settings.GEMINI_MODEL)
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
            )
        except ClientError as exc:
            if exc.status_code == 429:
                logger.warning("Gemini API quota exceeded")
                raise GeminiQuotaExceededError() from exc
            logger.warning("Gemini API client error status=%s", exc.status_code)
            raise GeminiAPIError(str(exc)) from exc
        except Exception as exc:
            error_text = str(exc)
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                logger.warning("Gemini API quota exceeded")
                raise GeminiQuotaExceededError() from exc
            logger.exception("Gemini API request failed")
            raise GeminiAPIError(str(exc)) from exc

        answer = (response.text or "").strip()
        if not answer:
            logger.error("Gemini returned an empty response")
            raise GeminiAPIError("Gemini returned an empty response")

        logger.info("Received Gemini response with length=%s", len(answer))
        return answer
