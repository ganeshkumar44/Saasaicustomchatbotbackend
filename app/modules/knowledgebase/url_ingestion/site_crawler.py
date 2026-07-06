"""Same-domain website crawler built on Playwright."""

from __future__ import annotations

import logging
from collections import deque

from app.core.config import Settings
from app.modules.knowledgebase.url_ingestion.content_cleaner import merge_page_contents
from app.modules.knowledgebase.url_ingestion.html_extractor import (
    PageContent,
    extract_page_content,
)
from app.modules.knowledgebase.url_ingestion.playwright_service import (
    PlaywrightBrowserService,
)
from app.modules.knowledgebase.url_ingestion.url_normalizer import normalize_url

logger = logging.getLogger(__name__)

PRIORITY_PATH_KEYWORDS = (
    "about",
    "pricing",
    "price",
    "faq",
    "support",
    "help",
    "docs",
    "documentation",
    "product",
    "products",
    "service",
    "services",
    "contact",
    "blog",
    "resource",
    "resources",
    "privacy",
    "terms",
    "features",
    "solutions",
)


def _link_priority(url: str) -> int:
    """Score internal links so important navigation pages are crawled earlier."""
    path = normalize_url(url).lower()
    score = 0
    for index, keyword in enumerate(PRIORITY_PATH_KEYWORDS):
        if keyword in path:
            score += (len(PRIORITY_PATH_KEYWORDS) - index) * 10
    return score


class SiteCrawler:
    """Crawl a website starting from a seed URL using one browser instance."""

    def __init__(
        self,
        browser_service: PlaywrightBrowserService,
        settings: Settings,
        start_url: str,
    ) -> None:
        self._browser_service = browser_service
        self._settings = settings
        self._start_url = normalize_url(start_url)
        self._max_pages = settings.URL_CRAWL_MAX_PAGES

    async def crawl(self) -> list[PageContent]:
        """
        Crawl same-domain internal pages up to the configured limit.

        Individual page failures are logged and skipped so one broken page does
        not fail the entire website import.
        """
        visited: set[str] = set()
        queued: set[str] = {self._start_url}
        queue: deque[str] = deque([self._start_url])
        pages: list[PageContent] = []

        while queue and len(visited) < self._max_pages:
            current_url = queue.popleft()
            queued.discard(current_url)

            if current_url in visited:
                continue

            visited.add(current_url)
            logger.info(
                "Crawling page %s/%s: %s",
                len(visited),
                self._max_pages,
                current_url,
            )

            try:
                html = await self._browser_service.fetch_rendered_html(current_url)
                page_content = extract_page_content(html, current_url)
            except Exception:
                logger.exception("Failed to crawl page %s", current_url)
                continue

            if page_content.text.strip():
                pages.append(page_content)

            discovered_links = sorted(
                page_content.internal_links,
                key=_link_priority,
                reverse=True,
            )
            for link in discovered_links:
                normalized = normalize_url(link)
                if normalized in visited or normalized in queued:
                    continue
                if len(visited) + len(queue) >= self._max_pages:
                    break
                queue.append(normalized)
                queued.add(normalized)

        logger.info(
            "Crawl finished for %s with %s successful pages",
            self._start_url,
            len(pages),
        )
        return pages

    async def crawl_and_merge(self) -> str:
        """Crawl the site and return merged, cleaned text for chunking."""
        pages = await self.crawl()
        return merge_page_contents(pages)
