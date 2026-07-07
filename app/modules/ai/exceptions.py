"""AI provider exception types."""


class GeminiAPIKeyMissingError(Exception):
    """Raised when the Gemini API key is not configured."""


class GeminiAPIError(Exception):
    """Raised when the Gemini API request fails."""


class GeminiQuotaExceededError(Exception):
    """Raised when the Gemini API quota or rate limit is exceeded."""


class AIProviderError(Exception):
    """Base exception for AI provider failures."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class OllamaNotRunningError(AIProviderError):
    """Raised when the Ollama server is unreachable."""


class OllamaModelUnavailableError(AIProviderError):
    """Raised when the configured Ollama model is not available."""


class OllamaProviderError(AIProviderError):
    """Raised for other Ollama provider failures."""


class OpenAIAPIKeyMissingError(Exception):
    """Raised when the OpenAI API key is not configured."""


class OpenAIAuthenticationError(AIProviderError):
    """Raised when OpenAI rejects the API key or credentials."""


class OpenAIRateLimitError(AIProviderError):
    """Raised when OpenAI rate limit is exceeded."""


class OpenAITimeoutError(AIProviderError):
    """Raised when an OpenAI request times out."""


class OpenAINetworkError(AIProviderError):
    """Raised when OpenAI cannot be reached over the network."""


class OpenAIServiceUnavailableError(AIProviderError):
    """Raised when OpenAI returns a service-unavailable response."""


class OpenAIProviderError(AIProviderError):
    """Raised for other OpenAI provider failures."""
