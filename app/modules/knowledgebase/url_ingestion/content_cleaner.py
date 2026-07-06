"""Cross-page content cleaning and merge helpers."""

from __future__ import annotations

import hashlib
import re

from app.modules.knowledgebase.url_ingestion.html_extractor import PageContent

FOOTER_PATTERNS = (
    r"all rights reserved",
    r"copyright\s*©",
    r"privacy policy",
    r"terms of (service|use)",
    r"cookie policy",
)


def _normalize_paragraph(text: str) -> str:
    """Normalize a paragraph for duplicate detection."""
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed


def _paragraph_hash(text: str) -> str:
    """Return a stable hash for a normalized paragraph."""
    return hashlib.sha1(_normalize_paragraph(text).encode("utf-8")).hexdigest()


def _is_boilerplate_paragraph(text: str) -> bool:
    """Return True for short footer/legal boilerplate lines."""
    normalized = _normalize_paragraph(text)
    if len(normalized) < 25:
        return False
    return any(re.search(pattern, normalized) for pattern in FOOTER_PATTERNS)


def format_page_block(page: PageContent) -> str:
    """Format a single page with metadata for semantic chunking."""
    lines = [f"# {page.title or page.url}", f"URL: {page.url}"]
    if page.description:
        lines.append(f"Description: {page.description}")
    lines.append("")
    if page.text.strip():
        lines.append(page.text.strip())
    return "\n".join(lines).strip()


def merge_page_contents(pages: list[PageContent]) -> str:
    """
    Merge crawled pages into one document while removing duplicate paragraphs.

    Repeated navigation/footer paragraphs that appear on multiple pages are
    deduplicated globally so chunking focuses on unique content.
    """
    if not pages:
        return ""

    global_seen_hashes: set[str] = set()
    merged_blocks: list[str] = []

    for page in pages:
        if not page.text.strip():
            continue

        filtered_lines: list[str] = []
        paragraph_buffer: list[str] = []

        def flush_paragraph() -> None:
            if not paragraph_buffer:
                return
            paragraph = "\n".join(paragraph_buffer).strip()
            paragraph_buffer.clear()
            if not paragraph:
                return
            if paragraph.startswith("#"):
                filtered_lines.append(paragraph)
                return
            if _is_boilerplate_paragraph(paragraph):
                return
            digest = _paragraph_hash(paragraph)
            if digest in global_seen_hashes:
                return
            global_seen_hashes.add(digest)
            filtered_lines.append(paragraph)

        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                continue
            if stripped.startswith("#"):
                flush_paragraph()
                filtered_lines.append(stripped)
                continue
            paragraph_buffer.append(stripped)

        flush_paragraph()

        if not filtered_lines:
            continue

        page_copy = PageContent(
            url=page.url,
            title=page.title,
            description=page.description,
            text="\n\n".join(filtered_lines),
            internal_links=page.internal_links,
        )
        merged_blocks.append(format_page_block(page_copy))

    return "\n\n---\n\n".join(block for block in merged_blocks if block.strip())
