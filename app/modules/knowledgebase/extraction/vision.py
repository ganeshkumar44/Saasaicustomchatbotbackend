"""
Gemini Vision helpers for image understanding during ingestion.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import get_settings

logger = logging.getLogger(__name__)

IMAGE_DESCRIPTION_PROMPT = """You are analyzing an image extracted from a business or technical document.

Describe the image in clear, detailed, searchable text so a chatbot can answer questions about it later.

Include:
- Diagram type (flowchart, architecture diagram, graph, table screenshot, map, photo, etc.)
- All visible labels, titles, and headings
- Relationships between elements (arrows, flows, hierarchies)
- Table headers and key row values when visible
- Trends or comparisons for charts

Write 2-6 sentences. Do not say "the image shows" repeatedly. Be factual and specific."""


@dataclass
class _VisionSession:
    """Per-document vision state to respect API quotas and limits."""

    quota_exhausted: bool = False
    images_attempted: int = 0
    last_request_at: float = 0.0
    quota_warning_logged: bool = False
    limit_warning_logged: bool = False


_session = _VisionSession()


def reset_vision_session() -> None:
    """Reset vision counters and flags for a new document upload."""
    global _session
    _session = _VisionSession()


def _vision_enabled() -> bool:
    settings = get_settings()
    return settings.GEMINI_VISION_ENABLED and bool(settings.GEMINI_API_KEY)


@lru_cache
def _get_vision_client() -> genai.Client | None:
    """Return a Gemini client when configured, otherwise None."""
    if not _vision_enabled():
        return None
    settings = get_settings()
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def should_describe_image(
    image_bytes: bytes,
    *,
    width: int = 0,
    height: int = 0,
) -> bool:
    """Return True when an image is eligible for Gemini Vision description."""
    if not _vision_enabled():
        return False

    if _session.quota_exhausted:
        return False

    settings = get_settings()
    if _session.images_attempted >= settings.GEMINI_VISION_MAX_IMAGES_PER_DOCUMENT:
        if not _session.limit_warning_logged:
            logger.info(
                "Reached Gemini Vision image limit (%s) for this document; "
                "skipping remaining images",
                settings.GEMINI_VISION_MAX_IMAGES_PER_DOCUMENT,
            )
            _session.limit_warning_logged = True
        return False

    if len(image_bytes) < settings.GEMINI_VISION_MIN_IMAGE_BYTES:
        return False

    if width > 0 and height > 0:
        if width < settings.GEMINI_VISION_MIN_IMAGE_DIMENSION or height < settings.GEMINI_VISION_MIN_IMAGE_DIMENSION:
            return False

    return True


def _wait_for_rate_limit() -> None:
    """Space out vision requests to reduce free-tier rate limit errors."""
    settings = get_settings()
    interval = settings.GEMINI_VISION_REQUEST_INTERVAL_SECONDS
    if interval <= 0:
        return

    elapsed = time.monotonic() - _session.last_request_at
    if elapsed < interval:
        time.sleep(interval - elapsed)


def describe_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    *,
    width: int = 0,
    height: int = 0,
) -> str | None:
    """
    Generate a searchable description for an image using Gemini Vision.

    Returns None when vision is unavailable, rate-limited, or the request fails.
    """
    if not should_describe_image(image_bytes, width=width, height=height):
        return None

    client = _get_vision_client()
    if client is None:
        return None

    settings = get_settings()
    model = settings.GEMINI_VISION_MODEL or settings.GEMINI_MODEL

    _wait_for_rate_limit()
    _session.images_attempted += 1
    _session.last_request_at = time.monotonic()

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=IMAGE_DESCRIPTION_PROMPT),
            ],
        )
    except Exception as exc:
        error_text = str(exc)
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            _session.quota_exhausted = True
            if not _session.quota_warning_logged:
                logger.warning(
                    "Gemini Vision quota exceeded; skipping remaining image "
                    "descriptions for this document. Configure billing or increase "
                    "GEMINI_VISION_REQUEST_INTERVAL_SECONDS, or set "
                    "GEMINI_VISION_MAX_IMAGES_PER_DOCUMENT lower."
                )
                _session.quota_warning_logged = True
            return None

        logger.warning("Gemini Vision request failed: %s", exc)
        return None

    description = (response.text or "").strip()
    if not description:
        logger.debug("Gemini Vision returned an empty description")
        return None

    logger.info("Generated image description with length=%s", len(description))
    return description
