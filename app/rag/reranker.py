"""Re-ranking utilities for retrieved knowledge chunks."""

from __future__ import annotations

import logging

from app.rag.bm25_search import tokenize
from app.rag.schema import RAGSearchResultItem

logger = logging.getLogger(__name__)


def keyword_overlap_score(query: str, chunk_text: str) -> float:
    """Measure how many query terms appear in a chunk."""
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    chunk_tokens = set(tokenize(chunk_text))
    overlap = len(query_tokens & chunk_tokens)
    return round(overlap / len(query_tokens), 4)


def rerank_chunks(
    query: str,
    chunks: list[RAGSearchResultItem],
    final_top_k: int,
    *,
    hybrid_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[RAGSearchResultItem]:
    """
    Re-rank candidate chunks using hybrid score and keyword overlap.

    Prefers chunks with higher similarity, stronger keyword overlap, and
    slightly boosts longer informative chunks when scores are close.
    """
    if not chunks:
        return []

    scored_chunks: list[tuple[float, RAGSearchResultItem]] = []
    for chunk in chunks:
        overlap = keyword_overlap_score(query, chunk.chunk_text)
        length_bonus = min(len(chunk.chunk_text) / 2000.0, 0.05)
        final_score = (
            hybrid_weight * chunk.similarity_score
            + keyword_weight * overlap
            + length_bonus
        )
        scored_chunks.append((round(final_score, 4), chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    reranked = [chunk for _, chunk in scored_chunks[:final_top_k]]

    logger.info(
        "Re-ranked %s chunks down to top %s for query_length=%s",
        len(chunks),
        len(reranked),
        len(query),
    )
    return reranked
