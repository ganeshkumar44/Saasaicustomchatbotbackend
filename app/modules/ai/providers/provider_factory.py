"""Factory for resolving AI providers from chatbot configuration."""

import logging

from app.modules.chatbot.schema import AIModelEnum
from app.modules.ai.providers.base_provider import BaseAIProvider
from app.modules.ai.providers.gemini_provider import GeminiProvider
from app.modules.ai.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

_gemini_provider = GeminiProvider()
_openai_provider = OpenAIProvider()

_LEGACY_LLAMA_MODEL = "Llama 3.1"


def get_provider_for_model(ai_model: str | None) -> BaseAIProvider:
    """
    Return the AI provider for a chatbot's configured model.

    Defaults to Gemini when the model is unset for backward compatibility.
    """
    normalized_model = (ai_model or AIModelEnum.GEMINI_2_5_FLASH.value).strip()

    if normalized_model == _LEGACY_LLAMA_MODEL:
        logger.warning(
            "Llama is no longer supported; falling back to Gemini for model=%s",
            normalized_model,
        )
        return _gemini_provider

    if normalized_model == AIModelEnum.GPT_4_1_MINI.value:
        logger.info("Selected AI provider: OpenAI (model=%s)", normalized_model)
        return _openai_provider

    logger.info("Selected AI provider: Gemini (model=%s)", normalized_model)
    return _gemini_provider
