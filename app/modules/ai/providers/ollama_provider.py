"""Ollama local AI provider."""

import logging

import requests

from app.core import messages
from app.core.config import get_settings
from app.modules.ai.exceptions import (
    OllamaModelUnavailableError,
    OllamaNotRunningError,
    OllamaProviderError,
)
from app.modules.ai.providers.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseAIProvider):
    """Generate answers using a local Ollama server."""

    def generate_answer(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the generated answer text."""
        settings = get_settings()
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        model = settings.OLLAMA_MODEL
        endpoint = f"{base_url}/api/generate"

        logger.info("Sending request to Ollama model=%s url=%s", model, endpoint)

        try:
            response = requests.post(
                endpoint,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=settings.OLLAMA_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.ConnectionError as exc:
            logger.warning("Ollama server is not reachable at %s", base_url)
            raise OllamaNotRunningError(messages.OLLAMA_NOT_RUNNING) from exc
        except requests.Timeout as exc:
            logger.warning("Ollama request timed out model=%s", model)
            raise OllamaProviderError(messages.OLLAMA_REQUEST_TIMEOUT) from exc
        except requests.RequestException as exc:
            logger.warning("Ollama request failed: %s", exc)
            raise OllamaProviderError(messages.OLLAMA_REQUEST_FAILED) from exc

        if response.status_code == 404:
            logger.warning("Ollama model not found model=%s", model)
            raise OllamaModelUnavailableError(messages.OLLAMA_MODEL_NOT_DOWNLOADED)

        if response.status_code >= 400:
            logger.warning(
                "Ollama returned error status=%s body=%s",
                response.status_code,
                response.text[:200],
            )
            if response.status_code == 503:
                raise OllamaModelUnavailableError(messages.OLLAMA_MODEL_UNAVAILABLE)
            raise OllamaProviderError(messages.OLLAMA_REQUEST_FAILED)

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("Ollama returned invalid JSON")
            raise OllamaProviderError(messages.OLLAMA_REQUEST_FAILED) from exc

        ollama_error = str(payload.get("error", "")).strip()
        if ollama_error:
            logger.warning("Ollama returned error: %s", ollama_error[:200])
            if "memory" in ollama_error.lower():
                raise OllamaModelUnavailableError(messages.OLLAMA_INSUFFICIENT_MEMORY)
            if "not found" in ollama_error.lower():
                raise OllamaModelUnavailableError(messages.OLLAMA_MODEL_NOT_DOWNLOADED)
            raise OllamaProviderError(messages.OLLAMA_REQUEST_FAILED)

        answer = str(payload.get("response", "")).strip()
        if not answer:
            logger.warning("Ollama returned an empty response model=%s", model)
            raise OllamaProviderError(messages.OLLAMA_EMPTY_RESPONSE)

        logger.info("Received Ollama response with length=%s", len(answer))
        return answer
