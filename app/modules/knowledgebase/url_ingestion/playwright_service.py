"""Playwright browser lifecycle management for URL ingestion."""

from __future__ import annotations

import logging
from types import TracebackType

from playwright.async_api import Browser, Page, Playwright, async_playwright

from app.core.config import Settings

logger = logging.getLogger(__name__)

MIN_VISIBLE_TEXT_LENGTH = 150


class PlaywrightBrowserService:
    """Manage a reusable headless Chromium browser for website crawling."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> PlaywrightBrowserService:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        """Launch Playwright and a shared Chromium browser instance."""
        if self._browser is not None:
            return

        logger.info("Starting Playwright Chromium browser for URL ingestion")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._settings.URL_PLAYWRIGHT_HEADLESS,
        )

    async def close(self) -> None:
        """Close the browser and Playwright process."""
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                logger.exception("Failed to close Playwright browser")
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                logger.exception("Failed to stop Playwright")
            self._playwright = None

        logger.info("Playwright browser closed")

    async def _wait_for_visible_content(self, page: Page, url: str) -> None:
        """Wait until JavaScript-rendered pages expose meaningful body text."""
        timeout_ms = min(
            15000,
            self._settings.URL_CRAWL_TIMEOUT_SECONDS * 1000,
        )
        try:
            await page.wait_for_function(
                f"""() => {{
                    const text = document.body ? document.body.innerText : '';
                    return text.trim().length >= {MIN_VISIBLE_TEXT_LENGTH};
                }}""",
                timeout=timeout_ms,
            )
        except Exception:
            logger.warning(
                "Timed out waiting for rendered text on %s; using current DOM",
                url,
            )

    async def fetch_rendered_html(self, url: str) -> str:
        """Render a page with JavaScript and return the final HTML."""
        if self._browser is None:
            raise RuntimeError("Playwright browser is not started")

        page: Page | None = None
        timeout_ms = self._settings.URL_CRAWL_TIMEOUT_SECONDS * 1000

        try:
            page = await self._browser.new_page()
            logger.info("Rendering URL with Playwright: %s", url)
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                logger.warning(
                    "networkidle not reached for %s; continuing with rendered DOM",
                    url,
                )
            await page.wait_for_timeout(
                self._settings.URL_CRAWL_POST_RENDER_WAIT_MS
            )
            await self._wait_for_visible_content(page, url)
            return await page.content()
        finally:
            if page is not None:
                await page.close()
