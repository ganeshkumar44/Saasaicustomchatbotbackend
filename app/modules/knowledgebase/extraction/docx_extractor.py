"""
Structured DOCX extraction with paragraphs, tables, headings, lists, and images.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.modules.knowledgebase.extraction.models import StructuredDocument
from app.modules.knowledgebase.extraction.table_utils import table_rows_to_markdown
from app.modules.knowledgebase.extraction.vision import describe_image_bytes, reset_vision_session

logger = logging.getLogger(__name__)


def _paragraph_style_is_heading(paragraph: Paragraph) -> bool:
    style_name = (paragraph.style.name or "").lower()
    return "heading" in style_name or style_name.startswith("title")


def _paragraph_is_list_item(paragraph: Paragraph) -> bool:
    style_name = (paragraph.style.name or "").lower()
    return "list" in style_name or "bullet" in style_name


def _extract_docx_table(table: Table) -> str | None:
    rows: list[list[str]] = []
    for row in table.rows:
        rows.append([cell.text.strip() for cell in row.cells])
    return table_rows_to_markdown(rows)


def _iter_block_items(document: Document):
    """Yield paragraphs and tables in document order."""
    parent_elm = document.element.body
    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def _extract_docx_images(document: Document, seen_hashes: set[str]) -> list[str]:
    descriptions: list[str] = []
    for rel in document.part.rels.values():
        if "image" not in rel.reltype:
            continue
        try:
            image_bytes = rel.target_part.blob
            if not image_bytes:
                continue
            image_hash = hashlib.md5(image_bytes).hexdigest()
            if image_hash in seen_hashes:
                continue
            seen_hashes.add(image_hash)

            content_type = rel.target_part.content_type or "image/png"
            description = describe_image_bytes(image_bytes, content_type)
            if description:
                descriptions.append(description)
        except Exception:
            logger.exception("Failed to extract/describe DOCX image")
            continue
    return descriptions


def extract_docx_structured(file_path: Path) -> StructuredDocument:
    """Extract structured content from a DOCX file."""
    document_model = StructuredDocument()
    reset_vision_session()
    document = Document(file_path)
    seen_image_hashes: set[str] = set()

    for block in _iter_block_items(document):
        try:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                if _paragraph_style_is_heading(block):
                    document_model.add("heading", text)
                elif _paragraph_is_list_item(block):
                    document_model.add("paragraph", f"- {text}")
                else:
                    document_model.add("paragraph", text)
            elif isinstance(block, Table):
                table_markdown = _extract_docx_table(block)
                if table_markdown:
                    document_model.add("table", table_markdown)
        except Exception:
            logger.exception("DOCX block extraction failed file=%s", file_path)
            continue

    for description in _extract_docx_images(document, seen_image_hashes):
        document_model.add("image_description", description)

    return document_model
