"""Context cleaning utilities before AI generation."""

from __future__ import annotations

import hashlib
import re

from app.rag.schema import RAGSearchResultItem


def _normalize_paragraph(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _paragraph_hash(text: str) -> str:
    return hashlib.sha1(_normalize_paragraph(text).encode("utf-8")).hexdigest()


def dedupe_chunk_texts(chunks: list[RAGSearchResultItem]) -> list[RAGSearchResultItem]:
    """Remove duplicate or near-duplicate chunk bodies while preserving order."""
    seen_hashes: set[str] = set()
    deduped: list[RAGSearchResultItem] = []

    for chunk in chunks:
        digest = _paragraph_hash(chunk.chunk_text)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        deduped.append(chunk)

    return deduped


def merge_similar_chunks(
    chunks: list[RAGSearchResultItem],
    *,
    similarity_threshold: float = 0.92,
) -> list[RAGSearchResultItem]:
    """
    Merge chunks that are highly similar to reduce repetition in the prompt.

    Uses normalized text prefix comparison as a lightweight similarity check.
    """
    if len(chunks) <= 1:
        return chunks

    merged: list[RAGSearchResultItem] = []
    for chunk in chunks:
        normalized = _normalize_paragraph(chunk.chunk_text)
        prefix = normalized[:180]
        duplicate_found = False
        for existing in merged:
            existing_normalized = _normalize_paragraph(existing.chunk_text)
            if (
                prefix
                and existing_normalized.startswith(prefix[:120])
                and len(normalized) / max(len(existing_normalized), 1)
                >= similarity_threshold
            ):
                duplicate_found = True
                break
        if not duplicate_found:
            merged.append(chunk)

    return merged


def clean_context_chunks(chunks: list[RAGSearchResultItem]) -> list[RAGSearchResultItem]:
    """Apply duplicate removal and similarity merging to retrieved chunks."""
    if not chunks:
        return []
    return merge_similar_chunks(dedupe_chunk_texts(chunks))
