"""
AI answer generation helper utilities.
"""

import logging
from functools import lru_cache

from google import genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = "I don't have enough information in the knowledge base."

AI_PROMPT_TEMPLATE = """You are a helpful AI assistant.

Answer ONLY using the provided knowledge base context.

If the answer is not available in the provided context, respond exactly:

"I don't have enough information in the knowledge base."

Do not make up information.

Context:
{context}

Question:
{question}"""


class GeminiAPIKeyMissingError(Exception):
    """Raised when the Gemini API key is not configured."""


class GeminiAPIError(Exception):
    """Raised when the Gemini API request fails."""


def normalize_question(question: str) -> str:
    """Normalize and validate a user question string."""
    return question.strip()


def build_ai_prompt(context: str, question: str) -> str:
    """Build the full prompt sent to Gemini from context and question."""
    return AI_PROMPT_TEMPLATE.format(context=context, question=question)


@lru_cache
def get_gemini_client() -> genai.Client:
    """Return a cached Gemini client configured from application settings."""
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise GeminiAPIKeyMissingError()
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def get_answer_from_gemini(prompt: str) -> str:
    """Send a prompt to Gemini and return the generated answer text."""
    settings = get_settings()
    client = get_gemini_client()

    logger.info("Sending request to Gemini model=%s", settings.GEMINI_MODEL)
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        logger.exception("Gemini API request failed")
        raise GeminiAPIError(str(exc)) from exc

    answer = (response.text or "").strip()
    if not answer:
        logger.error("Gemini returned an empty response")
        raise GeminiAPIError("Gemini returned an empty response")

    logger.info("Received Gemini response with length=%s", len(answer))
    return answer
