"""
OCR helpers for scanned PDF pages and image-heavy documents.
"""

from __future__ import annotations

import logging
import shutil
from functools import lru_cache

import fitz

logger = logging.getLogger(__name__)

MIN_PAGE_TEXT_LENGTH = 40
_tesseract_unavailable_logged = False


@lru_cache
def is_tesseract_available() -> bool:
    """Return True when Tesseract OCR is available on the system."""
    if shutil.which("tesseract"):
        return True

    try:
        fitz.get_tessdata()
        return True
    except Exception:
        return False


def _log_tesseract_unavailable_once() -> None:
    global _tesseract_unavailable_logged
    if _tesseract_unavailable_logged:
        return
    _tesseract_unavailable_logged = True
    logger.info(
        "Tesseract OCR is not installed; scanned PDF pages will use extracted "
        "text only. Install with: sudo apt install tesseract-ocr"
    )


def page_needs_ocr(page: fitz.Page) -> bool:
    """Return True when a PDF page likely contains scanned or image-only content."""
    if not is_tesseract_available():
        return False

    plain_text = page.get_text("text").strip()
    if len(plain_text) >= MIN_PAGE_TEXT_LENGTH:
        return False
    if page.get_images(full=True):
        return True
    return len(plain_text) < MIN_PAGE_TEXT_LENGTH


def extract_page_ocr_text(page: fitz.Page) -> str | None:
    """
    Run OCR on a PDF page using PyMuPDF's Tesseract integration when available.

    Returns None when OCR is unavailable or produces no text.
    """
    if not is_tesseract_available():
        _log_tesseract_unavailable_once()
        return None

    try:
        textpage = page.get_textpage_ocr(dpi=200, full=True)
        text = page.get_text("text", textpage=textpage).strip()
        if text:
            return text
    except RuntimeError as exc:
        logger.debug(
            "PyMuPDF OCR unavailable for page_number=%s: %s",
            page.number + 1,
            exc,
        )
    except Exception:
        logger.debug("PyMuPDF OCR failed for page_number=%s", page.number + 1)

    try:
        import io

        import pytesseract
        from PIL import Image

        pixmap = page.get_pixmap(dpi=200)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        text = pytesseract.image_to_string(image).strip()
        return text or None
    except Exception:
        logger.debug(
            "Fallback Tesseract OCR unavailable for page_number=%s",
            page.number + 1,
        )
        return None
