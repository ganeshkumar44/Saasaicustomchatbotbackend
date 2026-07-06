"""
Structured PDF extraction using PyMuPDF, pdfplumber, OCR, and Gemini Vision.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import fitz

from app.modules.knowledgebase.extraction.models import StructuredDocument
from app.modules.knowledgebase.extraction.ocr import extract_page_ocr_text, page_needs_ocr
from app.modules.knowledgebase.extraction.table_utils import table_rows_to_markdown
from app.modules.knowledgebase.extraction.vision import describe_image_bytes, reset_vision_session

logger = logging.getLogger(__name__)

_IMAGE_HASHES: set[str] = set()


def _reset_image_cache() -> None:
    """Reset per-document duplicate image tracking."""
    _IMAGE_HASHES.clear()


def _image_mime_type(image_bytes: bytes, fallback: str = "image/png") -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        return "image/webp"
    return fallback


def _extract_pdf_tables(page_number: int, file_path: Path) -> list[str]:
    """Extract tables from a single PDF page using pdfplumber."""
    tables: list[str] = []
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                return tables
            page = pdf.pages[page_number - 1]
            for table in page.extract_tables() or []:
                markdown = table_rows_to_markdown(table)
                if markdown:
                    tables.append(markdown)
    except Exception:
        logger.exception(
            "pdfplumber table extraction failed file=%s page=%s",
            file_path,
            page_number,
        )
    return tables


def _extract_pdf_page_images(page: fitz.Page) -> list[str]:
    """Extract embedded images from a PDF page and describe them with Gemini Vision."""
    descriptions: list[str] = []
    image_list = page.get_images(full=True)

    for image_index, image_info in enumerate(image_list, start=1):
        xref = image_info[0]
        width = int(image_info[2]) if len(image_info) > 2 else 0
        height = int(image_info[3]) if len(image_info) > 3 else 0
        try:
            image = page.parent.extract_image(xref)
            image_bytes = image.get("image")
            if not image_bytes:
                continue

            image_hash = hashlib.md5(image_bytes).hexdigest()
            if image_hash in _IMAGE_HASHES:
                continue
            _IMAGE_HASHES.add(image_hash)

            mime_type = image.get("ext", "png")
            if mime_type == "jpg":
                mime_type = "jpeg"
            mime_type = f"image/{mime_type}"

            description = describe_image_bytes(
                image_bytes,
                mime_type,
                width=width,
                height=height,
            )
            if description:
                descriptions.append(description)
        except Exception:
            logger.warning(
                "Failed to extract/describe PDF image page=%s index=%s",
                page.number + 1,
                image_index,
            )
            continue

    return descriptions


def _extract_pdf_page_text_blocks(page: fitz.Page) -> list[tuple[str, str]]:
    """
    Extract text blocks from a PDF page preserving reading order.

    Returns tuples of (block_type, text).
    """
    blocks: list[tuple[str, str]] = []
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines: list[str] = []
        max_font_size = 0.0
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = "".join(span.get("text", "") for span in spans).strip()
            if line_text:
                lines.append(line_text)
                for span in spans:
                    max_font_size = max(max_font_size, float(span.get("size", 0)))
        text = "\n".join(lines).strip()
        if not text:
            continue
        block_type = "heading" if max_font_size >= 14 and len(text) < 180 else "paragraph"
        blocks.append((block_type, text))
    return blocks


def extract_pdf_structured(file_path: Path) -> StructuredDocument:
    """Extract structured content from a PDF file page by page."""
    document = StructuredDocument()
    _reset_image_cache()
    reset_vision_session()

    with fitz.open(file_path) as pdf_document:
        for page in pdf_document:
            page_number = page.number + 1
            document.add("page_marker", f"--- Page {page_number} ---")

            try:
                for block_type, text in _extract_pdf_page_text_blocks(page):
                    document.add(block_type, text, metadata={"page": page_number})

                for table_markdown in _extract_pdf_tables(page_number, file_path):
                    document.add(
                        "table",
                        table_markdown,
                        metadata={"page": page_number},
                    )

                if page_needs_ocr(page):
                    ocr_text = extract_page_ocr_text(page)
                    if ocr_text:
                        document.add(
                            "ocr_text",
                            ocr_text,
                            metadata={"page": page_number},
                        )

                for description in _extract_pdf_page_images(page):
                    document.add(
                        "image_description",
                        description,
                        metadata={"page": page_number},
                    )
            except Exception:
                logger.exception(
                    "PDF page extraction failed file=%s page=%s",
                    file_path,
                    page_number,
                )
                continue

    return document
