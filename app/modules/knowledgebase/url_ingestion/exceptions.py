"""URL ingestion exception types."""


class UrlIngestionError(Exception):
    """Base exception for URL ingestion failures."""


class UnsafeUrlError(UrlIngestionError):
    """Raised when a URL fails SSRF or protocol validation."""


class UrlExtractionError(UrlIngestionError):
    """Raised when no usable content could be extracted from a URL."""


class PlaywrightNotAvailableError(UrlExtractionError):
    """Raised when Playwright or Chromium is not installed or cannot launch."""
