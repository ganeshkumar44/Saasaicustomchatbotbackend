"""Knowledge context builder for AI generation."""

from __future__ import annotations

import logging

from app.rag.context_cleaner import clean_context_chunks
from app.rag.schema import RAGSearchResultItem
from app.rag.utils import merge_chunk_texts

logger = logging.getLogger(__name__)


def _format_source_label(chunk: RAGSearchResultItem) -> str:
    """Build an internal source label for future attribution support."""
    if chunk.source_url:
        return f"URL: {chunk.source_url}"
    if chunk.source_name:
        return f"Document: {chunk.source_name}"
    return f"Document ID: {chunk.document_id}"


def build_context_from_chunks(chunks: list[RAGSearchResultItem]) -> str:
    """
    Merge retrieved chunks into a clean, hierarchy-aware context string.

    Preserves headings, lists, tables, and code blocks while attaching
    lightweight source labels for future attribution features.
    """
    cleaned_chunks = clean_context_chunks(chunks)
    if not cleaned_chunks:
        return ""

    formatted_sections: list[str] = []
    for index, chunk in enumerate(cleaned_chunks, start=1):
        source_label = _format_source_label(chunk)
        section = (
            f"[Source {index} | {source_label} | Chunk {chunk.chunk_index}]\n"
            f"{chunk.chunk_text.strip()}"
        )
        formatted_sections.append(section)

    context = merge_chunk_texts(formatted_sections)
    logger.info(
        "Built AI context from %s cleaned chunks with length=%s",
        len(cleaned_chunks),
        len(context),
    )
    return context
