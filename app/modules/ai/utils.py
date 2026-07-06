"""
AI answer generation helper utilities.
"""

from app.modules.ai.exceptions import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiQuotaExceededError,
)
from app.modules.ai.prompt_builder import NO_CONTEXT_ANSWER, build_ai_prompt
from app.modules.ai.providers.gemini_provider import GeminiProvider
from app.modules.ai.service import normalize_question

_gemini_provider = GeminiProvider()


def get_answer_from_gemini(prompt: str) -> str:
    """Backward-compatible wrapper around the Gemini provider."""
    return _gemini_provider.generate_answer(prompt)


__all__ = [
    "NO_CONTEXT_ANSWER",
    "GeminiAPIError",
    "GeminiAPIKeyMissingError",
    "GeminiQuotaExceededError",
    "build_ai_prompt",
    "get_answer_from_gemini",
    "normalize_question",
]
