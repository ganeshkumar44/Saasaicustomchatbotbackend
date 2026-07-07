"""OpenAI GPT AI provider."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from app.core import messages
from app.core.config import get_settings
from app.modules.ai.exceptions import (
    OpenAIAPIKeyMissingError,
    OpenAIAuthenticationError,
    OpenAINetworkError,
    OpenAIProviderError,
    OpenAIRateLimitError,
    OpenAIServiceUnavailableError,
    OpenAITimeoutError,
)
from app.modules.ai.providers.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


@lru_cache
def _get_openai_client() -> OpenAI:
    """Return a cached OpenAI client configured from application settings."""
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise OpenAIAPIKeyMissingError()
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_REQUEST_TIMEOUT_SECONDS,
    )


class OpenAIProvider(BaseAIProvider):
    """Generate answers using OpenAI chat completions."""

    def generate_answer(self, prompt: str) -> str:
        """Send a prompt to OpenAI and return the generated answer text."""
        settings = get_settings()
        client = _get_openai_client()
        model = settings.OPENAI_MODEL

        logger.info("Sending request to OpenAI model=%s", model)
        started_at = time.monotonic()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
        except AuthenticationError as exc:
            logger.warning("OpenAI authentication failed")
            raise OpenAIAuthenticationError(messages.OPENAI_AUTHENTICATION_FAILED) from exc
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit exceeded")
            raise OpenAIRateLimitError(messages.OPENAI_RATE_LIMIT_EXCEEDED) from exc
        except APITimeoutError as exc:
            logger.warning("OpenAI request timed out model=%s", model)
            raise OpenAITimeoutError(messages.OPENAI_REQUEST_TIMEOUT) from exc
        except APIConnectionError as exc:
            logger.warning("OpenAI network connection failed")
            raise OpenAINetworkError(messages.OPENAI_NETWORK_ERROR) from exc
        except APIStatusError as exc:
            logger.warning(
                "OpenAI returned error status=%s body=%s",
                exc.status_code,
                str(exc.message)[:200],
            )
            if exc.status_code == 503:
                raise OpenAIServiceUnavailableError(
                    messages.OPENAI_SERVICE_UNAVAILABLE
                ) from exc
            if exc.status_code in {401, 403}:
                raise OpenAIAuthenticationError(messages.OPENAI_AUTHENTICATION_FAILED) from exc
            if exc.status_code == 429:
                raise OpenAIRateLimitError(messages.OPENAI_RATE_LIMIT_EXCEEDED) from exc
            raise OpenAIProviderError(messages.OPENAI_REQUEST_FAILED) from exc
        except Exception as exc:
            logger.exception("OpenAI API request failed")
            raise OpenAIProviderError(messages.OPENAI_REQUEST_FAILED) from exc

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        usage = response.usage
        if usage is not None:
            logger.info(
                "OpenAI response received in %sms prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                elapsed_ms,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )
        else:
            logger.info("OpenAI response received in %sms", elapsed_ms)

        if not response.choices:
            logger.error("OpenAI returned no choices model=%s", model)
            raise OpenAIProviderError(messages.OPENAI_EMPTY_RESPONSE)

        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            logger.error("OpenAI returned an empty response model=%s", model)
            raise OpenAIProviderError(messages.OPENAI_EMPTY_RESPONSE)

        logger.info("Received OpenAI response with length=%s", len(answer))
        return answer
