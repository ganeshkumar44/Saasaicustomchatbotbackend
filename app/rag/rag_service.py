"""
RAG retrieval orchestration service.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.chatbot.model import Chatbot
from app.rag.schema import ContextResponse, RAGSearchResultItem
from app.rag.search_service import (
    ChromaSearchError,
    QueryRequiredError,
    generate_query_embedding,
    query_chromadb,
)
from app.rag.utils import merge_chunk_texts, normalize_query

logger = logging.getLogger(__name__)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


def search_knowledge_base(
    db: Session,
    chatbot_id: int,
    query: str,
    top_k: int = 5,
) -> list[RAGSearchResultItem]:
    """
    Retrieve the most relevant knowledge chunks for a user question.

    Flow:
    1. Generate query embedding
    2. Search ChromaDB with chatbot filter
    3. Return top-k ranked chunks
    """
    if not query or not query.strip():
        raise QueryRequiredError()

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        logger.warning("Search requested for invalid chatbot_id=%s", chatbot_id)
        return []

    try:
        query_embedding = generate_query_embedding(query)
        raw_results = query_chromadb(
            chatbot_id=chatbot_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )
    except ChromaSearchError:
        logger.error("Returning empty RAG results due to ChromaDB search failure")
        return []

    results = [
        RAGSearchResultItem(
            chunk_text=str(item["chunk_text"]),
            document_id=int(item["document_id"]),
            chunk_index=int(item["chunk_index"]),
            similarity_score=float(item["similarity_score"]),
        )
        for item in raw_results
    ]

    logger.info(
        "RAG search completed for chatbot_id=%s with %s results",
        chatbot_id,
        len(results),
    )
    return results


def build_context(
    db: Session,
    chatbot_id: int,
    query: str,
    top_k: int = 5,
) -> ContextResponse:
    """
    Build merged context from the top relevant knowledge base chunks.

    Used to validate the context that will later be sent to the AI model.
    """
    normalized_query = normalize_query(query)
    if not normalized_query:
        raise QueryRequiredError()

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    search_results = search_knowledge_base(
        db,
        chatbot_id,
        normalized_query,
        top_k=top_k,
    )
    chunk_texts = [result.chunk_text for result in search_results]
    context = merge_chunk_texts(chunk_texts)

    logger.info(
        "Built RAG context for chatbot_id=%s with %s chunks and length=%s",
        chatbot_id,
        len(search_results),
        len(context),
    )

    return ContextResponse(
        question=normalized_query,
        total_chunks=len(search_results),
        context_length=len(context),
        context=context,
    )
