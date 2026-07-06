"""Factory for resolving AI providers from chatbot configuration."""

import logging

from app.modules.chatbot.schema import AIModelEnum
from app.modules.ai.providers.base_provider import BaseAIProvider
from app.modules.ai.providers.gemini_provider import GeminiProvider
from app.modules.ai.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

_gemini_provider = GeminiProvider()
_ollama_provider = OllamaProvider()


def get_provider_for_model(ai_model: str | None) -> BaseAIProvider:
    """
    Return the AI provider for a chatbot's configured model.

    Defaults to Gemini when the model is unset for backward compatibility.
    """
    normalized_model = (ai_model or AIModelEnum.GEMINI_2_5_FLASH.value).strip()

    if normalized_model == AIModelEnum.LLAMA_3_1.value:
        logger.info("Selected AI provider: Ollama (model=%s)", normalized_model)
        return _ollama_provider

    logger.info("Selected AI provider: Gemini (model=%s)", normalized_model)
    return _gemini_provider
