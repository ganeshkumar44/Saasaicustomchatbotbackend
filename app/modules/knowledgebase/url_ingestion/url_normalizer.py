"""URL normalization helpers for crawling."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_QUERY_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "ref",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
)

SKIP_FILE_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".mp4",
        ".mp3",
        ".avi",
        ".mov",
        ".wmv",
        ".css",
        ".js",
        ".json",
        ".xml",
        ".rss",
        ".atom",
    }
)


def normalize_hostname(hostname: str) -> str:
    """Normalize a hostname for comparison."""
    return hostname.lower().rstrip(".")


def normalize_url(url: str, *, drop_fragment: bool = True) -> str:
    """
    Normalize a URL for deduplication and crawling.

    - Lowercases hostname
    - Removes default ports
    - Strips trailing slashes (except root)
    - Removes tracking query parameters
    - Optionally drops URL fragments
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    hostname = normalize_hostname(parsed.hostname or "")
    port = parsed.port

    if not hostname:
        return url.strip()

    netloc = hostname
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(filtered_query, doseq=True)
    fragment = "" if drop_fragment else parsed.fragment

    return urlunparse((scheme, netloc, path, parsed.params, query, fragment))


def is_same_domain(url: str, base_url: str) -> bool:
    """Return True when two URLs belong to the same hostname."""
    base_host = normalize_hostname(urlparse(base_url).hostname or "")
    candidate_host = normalize_hostname(urlparse(url).hostname or "")
    return bool(base_host) and base_host == candidate_host


def is_crawlable_link(url: str, base_url: str) -> bool:
    """Return True when a discovered link should be crawled."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not is_same_domain(url, base_url):
        return False

    path = (parsed.path or "").lower()
    for extension in SKIP_FILE_EXTENSIONS:
        if path.endswith(extension):
            return False

    return True


def resolve_internal_link(base_url: str, href: str) -> str | None:
    """Resolve and normalize an internal hyperlink."""
    if not href:
        return None

    stripped = href.strip()
    if not stripped or stripped.startswith("#"):
        return None

    lowered = stripped.lower()
    if lowered.startswith(
        ("mailto:", "tel:", "javascript:", "data:", "ftp:", "file:")
    ):
        return None

    absolute = urljoin(base_url, stripped)
    if not is_crawlable_link(absolute, base_url):
        return None

    return normalize_url(absolute)
