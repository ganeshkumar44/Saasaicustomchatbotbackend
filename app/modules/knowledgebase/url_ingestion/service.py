"""Entry point for Playwright-based website URL ingestion."""

from __future__ import annotations

import asyncio
import logging

import requests
from bs4 import BeautifulSoup

from app.core.config import Settings, get_settings
from app.modules.knowledgebase.url_ingestion.exceptions import (
    PlaywrightNotAvailableError,
    UnsafeUrlError,
    UrlExtractionError,
)
from app.modules.knowledgebase.url_ingestion.playwright_service import (
    PlaywrightBrowserService,
)
from app.modules.knowledgebase.url_ingestion.site_crawler import SiteCrawler
from app.modules.knowledgebase.url_ingestion.url_validator import validate_crawl_url

logger = logging.getLogger(__name__)

MIN_USEFUL_URL_TEXT_LENGTH = 200
PLAYWRIGHT_INSTALL_HINT = (
    "Playwright Chromium is required for JavaScript websites. "
    "Install it with: ./venv/bin/playwright install chromium"
)


def _is_playwright_setup_error(exc: BaseException) -> bool:
    """Return True when Playwright failed because browsers are missing."""
    message = str(exc).lower()
    return (
        "executable doesn't exist" in message
        or "playwright install" in message
        or "browserType.launch" in message
    )


def _normalize_extracted_text(text: str) -> str:
    """Normalize extracted website text for storage and chunking."""
    from app.modules.knowledgebase.utils import normalize_extracted_text

    return normalize_extracted_text(text)


async def _extract_static_fallback(url: str, timeout_seconds: int) -> str:
    """Best-effort static HTML fallback when Playwright is unavailable."""

    def _fetch() -> str:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SaaSChatbotBot/1.0)"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        return _normalize_extracted_text(soup.get_text(separator="\n"))

    return await asyncio.to_thread(_fetch)


async def extract_url_text(url: str, settings: Settings | None = None) -> str:
    """
    Extract readable text from a website URL using Playwright.

    Flow:
    1. Validate URL and block SSRF targets
    2. Launch one shared Chromium browser
    3. Render JavaScript-heavy pages
    4. Crawl same-domain internal links
    5. Clean and merge page content with metadata
    """
    app_settings = settings or get_settings()
    validated_url = validate_crawl_url(url)

    logger.info("Starting Playwright URL ingestion for %s", validated_url)

    try:
        async with PlaywrightBrowserService(app_settings) as browser_service:
            crawler = SiteCrawler(browser_service, app_settings, validated_url)
            merged_text = await crawler.crawl_and_merge()
    except UnsafeUrlError:
        raise
    except Exception as exc:
        if _is_playwright_setup_error(exc):
            logger.error(
                "Playwright Chromium is not available for %s",
                validated_url,
            )
            raise PlaywrightNotAvailableError(PLAYWRIGHT_INSTALL_HINT) from exc

        logger.exception(
            "Playwright URL ingestion failed for %s; attempting static fallback",
            validated_url,
        )
        try:
            fallback_text = await _extract_static_fallback(
                validated_url,
                app_settings.URL_FETCH_TIMEOUT_SECONDS,
            )
        except Exception as fallback_error:
            raise UrlExtractionError(
                f"Failed to extract content from {validated_url}"
            ) from fallback_error

        if len(fallback_text.strip()) < MIN_USEFUL_URL_TEXT_LENGTH:
            raise UrlExtractionError(
                f"{PLAYWRIGHT_INSTALL_HINT} Static HTML extraction only retrieved "
                f"{len(fallback_text.strip())} characters from {validated_url}."
            )

        logger.warning(
            "Using limited static HTML fallback for %s (%s characters)",
            validated_url,
            len(fallback_text.strip()),
        )
        return fallback_text

    normalized_text = _normalize_extracted_text(merged_text)
    if not normalized_text:
        raise UrlExtractionError(
            f"No readable content could be extracted from {validated_url}"
        )

    logger.info(
        "URL ingestion completed for %s with %s characters",
        validated_url,
        len(normalized_text),
    )
    return normalized_text
