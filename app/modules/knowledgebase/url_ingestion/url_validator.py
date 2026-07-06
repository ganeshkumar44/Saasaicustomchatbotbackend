"""SSRF-safe URL validation for website ingestion."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.modules.knowledgebase.url_ingestion.exceptions import UnsafeUrlError
from app.modules.knowledgebase.url_ingestion.url_normalizer import normalize_url

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
    }
)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True for private, loopback, link-local, or reserved addresses."""
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a hostname to IP addresses."""
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        for info in socket.getaddrinfo(hostname, None):
            addresses.append(ipaddress.ip_address(info[4][0]))
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Unable to resolve hostname: {hostname}") from exc
    return addresses


def validate_crawl_url(url: str) -> str:
    """
    Validate and normalize a crawlable URL.

    Only http/https schemes are allowed. Localhost, private IPs, and
  non-HTTP schemes are rejected to mitigate SSRF.
    """
    normalized = normalize_url(url)
    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise UnsafeUrlError("URL hostname is required.")

    if hostname in BLOCKED_HOSTNAMES:
        raise UnsafeUrlError("Localhost URLs are not allowed.")

    try:
        literal_ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        literal_ip = None

    if literal_ip is not None and _is_blocked_ip(literal_ip):
        raise UnsafeUrlError("Private or local network URLs are not allowed.")

    for resolved_ip in _resolve_host_ips(hostname):
        if _is_blocked_ip(resolved_ip):
            raise UnsafeUrlError("URL resolves to a private or local network address.")

    return normalized
