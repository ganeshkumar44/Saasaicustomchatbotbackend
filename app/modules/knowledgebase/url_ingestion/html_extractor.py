"""Rendered HTML content extraction for crawled pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

from app.modules.knowledgebase.url_ingestion.url_normalizer import resolve_internal_link

REMOVE_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "canvas",
        "template",
    }
)

NOISE_CLASS_KEYWORDS = (
    "cookie",
    "consent",
    "gdpr",
    "banner",
    "advert",
    "advertisement",
    "ad-slot",
    "adsbygoogle",
    "popup",
    "modal",
    "newsletter",
    "subscribe",
    "social-share",
    "share-buttons",
)

MAIN_CONTENT_SELECTORS = (
    "main",
    "[role='main']",
    "article",
    "#content",
    "#main-content",
    ".main-content",
    ".content",
    ".page-content",
    ".post-content",
    ".entry-content",
    ".documentation",
    ".docs-content",
)


@dataclass
class PageContent:
    """Structured content extracted from a rendered page."""

    url: str
    title: str
    description: str
    text: str
    internal_links: list[str] = field(default_factory=list)


def _clean_inline_text(text: str) -> str:
    """Collapse whitespace inside a text fragment."""
    return re.sub(r"\s+", " ", text).strip()


def _element_is_hidden(element: Tag) -> bool:
    """Return True when an element is hidden from users."""
    if element.has_attr("hidden"):
        return True
    if element.get("aria-hidden", "").lower() == "true":
        return True

    style = element.get("style", "").lower().replace(" ", "")
    if "display:none" in style or "visibility:hidden" in style:
        return True

    return False


def _element_is_noise(element: Tag) -> bool:
    """Return True for cookie banners, ads, and similar boilerplate."""
    combined = " ".join(
        filter(
            None,
            [
                element.get("id", ""),
                " ".join(element.get("class", [])),
                element.get("role", ""),
            ],
        )
    ).lower()

    return any(keyword in combined for keyword in NOISE_CLASS_KEYWORDS)


def _remove_unwanted_elements(soup: BeautifulSoup) -> None:
    """Remove scripts, hidden elements, and common boilerplate."""
    for tag_name in REMOVE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    for element in soup.find_all(True):
        if not isinstance(element, Tag):
            continue
        if _element_is_hidden(element) or _element_is_noise(element):
            element.decompose()


def _find_main_container(soup: BeautifulSoup) -> Tag:
    """Locate the primary content container when possible."""
    for selector in MAIN_CONTENT_SELECTORS:
        match = soup.select_one(selector)
        if match and _clean_inline_text(match.get_text(separator=" ", strip=True)):
            return match
    return soup.body or soup


def _render_table(table: Tag) -> str:
    """Convert an HTML table into a Markdown table."""
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = [
            _clean_inline_text(cell.get_text(separator=" ", strip=True))
            for cell in row.find_all(["th", "td"])
        ]
        if any(cells):
            rows.append(cells)

    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
    header = normalized_rows[0]
    separator = ["---"] * column_count
    body = normalized_rows[1:] if len(normalized_rows) > 1 else []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render_list(element: Tag, ordered: bool) -> list[str]:
    """Render ordered or unordered lists."""
    lines: list[str] = []
    for index, item in enumerate(element.find_all("li", recursive=False), start=1):
        prefix = f"{index}." if ordered else "-"
        item_text = _clean_inline_text(item.get_text(separator=" ", strip=True))
        if item_text:
            lines.append(f"{prefix} {item_text}")
    return lines


def _render_node(node: Tag | NavigableString, lines: list[str], depth: int = 0) -> None:
    """Walk a DOM subtree and append structured text lines."""
    if isinstance(node, NavigableString):
        text = _clean_inline_text(str(node))
        if text and (not lines or lines[-1] != text):
            lines.append(text)
        return

    if not isinstance(node, Tag):
        return

    name = node.name.lower()
    if name in REMOVE_TAGS:
        return

    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        heading = _clean_inline_text(node.get_text(separator=" ", strip=True))
        if heading:
            lines.append(f"{'#' * level} {heading}")
        return

    if name == "p":
        paragraph = _clean_inline_text(node.get_text(separator=" ", strip=True))
        if paragraph:
            lines.append(paragraph)
        return

    if name in {"ul", "ol"}:
        lines.extend(_render_list(node, ordered=name == "ol"))
        return

    if name == "table":
        table_text = _render_table(node)
        if table_text:
            lines.append(table_text)
        return

    if name == "details":
        summary = node.find("summary")
        summary_text = _clean_inline_text(
            summary.get_text(separator=" ", strip=True) if summary else ""
        )
        if summary_text:
            lines.append(f"### {summary_text}")
        for child in node.children:
            if isinstance(child, Tag) and child.name.lower() == "summary":
                continue
            _render_node(child, lines, depth + 1)
        return

    if name in {"dl"}:
        for child in node.children:
            if not isinstance(child, Tag):
                continue
            if child.name.lower() == "dt":
                term = _clean_inline_text(child.get_text(separator=" ", strip=True))
                if term:
                    lines.append(f"### {term}")
            elif child.name.lower() == "dd":
                definition = _clean_inline_text(
                    child.get_text(separator=" ", strip=True)
                )
                if definition:
                    lines.append(definition)
        return

    if name in {"section", "article", "main", "div", "span", "body"}:
        for child in node.children:
            _render_node(child, lines, depth + 1)
        return

    text = _clean_inline_text(node.get_text(separator=" ", strip=True))
    if text:
        lines.append(text)


def _dedupe_adjacent_lines(lines: list[str]) -> list[str]:
    """Remove consecutive duplicate lines."""
    deduped: list[str] = []
    previous = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == previous:
            continue
        deduped.append(stripped)
        previous = stripped
    return deduped


def extract_page_content(html: str, page_url: str) -> PageContent:
    """Extract meaningful visible content and internal links from rendered HTML."""
    soup = BeautifulSoup(html, "html.parser")
    _remove_unwanted_elements(soup)

    title = _clean_inline_text(soup.title.get_text(strip=True)) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    description = ""
    if description_tag and description_tag.get("content"):
        description = _clean_inline_text(description_tag["content"])

    container = _find_main_container(soup)
    lines: list[str] = []
    _render_node(container, lines)
    text = "\n\n".join(_dedupe_adjacent_lines(lines))

    if len(text.strip()) < 150 and soup.body is not None:
        body_soup = BeautifulSoup(str(soup.body), "html.parser")
        for tag_name in REMOVE_TAGS:
            for element in body_soup.find_all(tag_name):
                element.decompose()
        fallback_text = _clean_inline_text(
            body_soup.get_text(separator="\n", strip=True)
        )
        if len(fallback_text) > len(text.strip()):
            text = fallback_text

    internal_links: list[str] = []
    seen_links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        resolved = resolve_internal_link(page_url, anchor["href"])
        if resolved and resolved not in seen_links:
            seen_links.add(resolved)
            internal_links.append(resolved)

    return PageContent(
        url=page_url,
        title=title,
        description=description,
        text=text,
        internal_links=internal_links,
    )
