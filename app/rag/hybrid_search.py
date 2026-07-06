"""Hybrid BM25 + vector search for knowledge base retrieval."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.knowledgebase.model import KnowledgeChunk, KnowledgebaseDocument
from app.rag.bm25_search import normalize_scores, search_bm25
from app.rag.schema import RAGSearchResultItem
from app.rag.search_service import (
    ChromaSearchError,
    generate_query_embedding,
    query_chromadb,
)

logger = logging.getLogger(__name__)


def _chunk_key(document_id: int, chunk_index: int) -> tuple[int, int]:
    return document_id, chunk_index


def _load_chatbot_chunks(
    db: Session,
    chatbot_id: int,
    max_chunks: int,
) -> list[KnowledgeChunk]:
    """Load knowledge chunks for BM25 indexing."""
    return list(
        db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.chatbot_id == chatbot_id)
            .order_by(KnowledgeChunk.document_id.asc(), KnowledgeChunk.chunk_index.asc())
            .limit(max_chunks)
        ).scalars().all()
    )


def _load_document_metadata(
    db: Session,
    document_ids: set[int],
) -> dict[int, KnowledgebaseDocument]:
    """Load source document metadata for attribution-ready context."""
    if not document_ids:
        return {}

    documents = list(
        db.execute(
            select(KnowledgebaseDocument).where(
                KnowledgebaseDocument.id.in_(document_ids)
            )
        ).scalars().all()
    )
    return {document.id: document for document in documents}


def _build_result_item(
    document_id: int,
    chunk_index: int,
    chunk_text: str,
    score: float,
    document: KnowledgebaseDocument | None,
) -> RAGSearchResultItem:
    """Build a search result with optional source metadata."""
    source_name = None
    source_url = None
    source_type = None
    if document is not None:
        source_type = document.source_type
        source_url = document.source_url
        source_name = document.original_name

    return RAGSearchResultItem(
        chunk_text=chunk_text,
        document_id=document_id,
        chunk_index=chunk_index,
        similarity_score=round(score, 4),
        source_name=source_name,
        source_url=source_url,
        source_type=source_type,
    )


def hybrid_search_knowledge_base(
    db: Session,
    chatbot_id: int,
    query: str,
    initial_top_k: int,
) -> list[RAGSearchResultItem]:
    """
    Retrieve knowledge chunks using vector search and BM25, then merge results.

    Flow:
    1. Vector search (ChromaDB) for semantic matches
    2. BM25 keyword search over stored chunks
    3. Merge, deduplicate, and score with configurable weights
    """
    settings = get_settings()
    vector_weight = settings.RAG_VECTOR_SEARCH_WEIGHT
    bm25_weight = settings.RAG_BM25_SEARCH_WEIGHT

    merged_scores: dict[tuple[int, int], float] = {}
    chunk_lookup: dict[tuple[int, int], str] = {}

    try:
        query_embedding = generate_query_embedding(query)
        vector_results = query_chromadb(
            chatbot_id=chatbot_id,
            query_embedding=query_embedding,
            top_k=initial_top_k,
        )
    except ChromaSearchError:
        logger.error("Vector search failed during hybrid retrieval")
        vector_results = []

    db_chunks = _load_chatbot_chunks(db, chatbot_id, settings.RAG_BM25_MAX_CHUNKS)
    for chunk in db_chunks:
        key = _chunk_key(chunk.document_id, chunk.chunk_index)
        chunk_lookup[key] = chunk.chunk_text

    for result in vector_results:
        key = _chunk_key(int(result["document_id"]), int(result["chunk_index"]))
        merged_scores[key] = max(
            merged_scores.get(key, 0.0),
            vector_weight * float(result["similarity_score"]),
        )
        chunk_lookup[key] = str(result["chunk_text"])

    corpus_keys = list(chunk_lookup.keys())
    corpus_texts = [chunk_lookup[key] for key in corpus_keys]
    bm25_hits = search_bm25(query, corpus_texts, top_k=initial_top_k)
    bm25_scores = normalize_scores([score for _, score in bm25_hits])

    for (corpus_index, _), normalized_score in zip(bm25_hits, bm25_scores, strict=False):
        key = corpus_keys[corpus_index]
        merged_scores[key] = max(
            merged_scores.get(key, 0.0),
            bm25_weight * normalized_score,
        )

    if not merged_scores:
        return []

    document_metadata = _load_document_metadata(
        db,
        {key[0] for key in merged_scores},
    )

    ranked_items: list[RAGSearchResultItem] = []
    for key, score in sorted(
        merged_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:initial_top_k]:
        chunk_text = chunk_lookup.get(key)
        if not chunk_text:
            continue
        ranked_items.append(
            _build_result_item(
                key[0],
                key[1],
                chunk_text,
                score,
                document_metadata.get(key[0]),
            )
        )

    logger.info(
        "Hybrid search completed for chatbot_id=%s vector_hits=%s bm25_hits=%s merged=%s",
        chatbot_id,
        len(vector_results),
        len(bm25_hits),
        len(ranked_items),
    )
    return ranked_items
