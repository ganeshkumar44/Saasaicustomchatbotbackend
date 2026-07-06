"""
RAG retrieval orchestration service.
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.ai.context_builder import build_context_from_chunks
from app.modules.chatbot.model import Chatbot
from app.rag.hybrid_search import hybrid_search_knowledge_base
from app.rag.reranker import rerank_chunks
from app.rag.schema import ContextResponse, RAGSearchResultItem
from app.rag.search_service import QueryRequiredError
from app.rag.utils import normalize_query

logger = logging.getLogger(__name__)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


def search_knowledge_base(
    db: Session,
    chatbot_id: int,
    query: str,
    top_k: int | None = None,
) -> list[RAGSearchResultItem]:
    """
    Retrieve the most relevant knowledge chunks for a user question.

    Flow:
    1. Hybrid search (vector + BM25) over top initial candidates
    2. Re-rank to the best final chunks
    """
    if not query or not query.strip():
        raise QueryRequiredError()

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        logger.warning("Search requested for invalid chatbot_id=%s", chatbot_id)
        return []

    settings = get_settings()
    initial_top_k = top_k or settings.RAG_INITIAL_TOP_K
    final_top_k = settings.RAG_FINAL_TOP_K

    candidates = hybrid_search_knowledge_base(
        db,
        chatbot_id,
        query,
        initial_top_k=initial_top_k,
    )
    results = rerank_chunks(
        query,
        candidates,
        final_top_k=final_top_k,
        hybrid_weight=settings.RAG_HYBRID_WEIGHT,
        keyword_weight=settings.RAG_KEYWORD_OVERLAP_WEIGHT,
    )

    logger.info(
        "RAG search completed for chatbot_id=%s with %s final results",
        chatbot_id,
        len(results),
    )
    return results


def build_context(
    db: Session,
    chatbot_id: int,
    query: str,
    top_k: int | None = None,
) -> ContextResponse:
    """
    Build merged context from the top relevant knowledge base chunks.

    Used by the AI service before sending context to Gemini or Ollama.
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
    context = build_context_from_chunks(search_results)

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
