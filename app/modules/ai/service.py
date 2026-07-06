"""
AI answer generation service.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.ai.context_builder import build_context_from_chunks
from app.modules.ai.memory_service import build_conversation_context
from app.modules.ai.prompt_builder import NO_CONTEXT_ANSWER, build_ai_prompt
from app.modules.ai.schema import AITestAnswerResponse
from app.modules.ai.providers.provider_factory import get_provider_for_model
from app.modules.chatbot.model import Chatbot
from app.rag import rag_service
from app.rag.search_service import QueryRequiredError

logger = logging.getLogger(__name__)


class QuestionRequiredError(Exception):
    """Raised when the user question is empty."""


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


def normalize_question(question: str) -> str:
    """Normalize and validate a user question string."""
    return question.strip()


def generate_ai_answer(
    db: Session,
    chatbot_id: int,
    question: str,
    top_k: int | None = None,
    chat_session_id: int | None = None,
) -> AITestAnswerResponse:
    """
    Generate an AI answer using enhanced RAG context and conversation memory.

    Flow:
    1. Hybrid retrieval with re-ranking
    2. Clean and merge context
    3. Include recent conversation when useful
    4. Route to Gemini or Ollama based on chatbot.ai_model
    """
    normalized_question = normalize_question(question)
    if not normalized_question:
        raise QuestionRequiredError()

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    logger.info(
        "Starting AI answer generation for chatbot_id=%s ai_model=%s session_id=%s",
        chatbot_id,
        chatbot.ai_model,
        chat_session_id,
    )

    search_results = rag_service.search_knowledge_base(
        db,
        chatbot_id,
        normalized_question,
        top_k=top_k,
    )
    context = build_context_from_chunks(search_results)

    logger.info(
        "RAG retrieval completed for chatbot_id=%s with total_chunks=%s and context_length=%s",
        chatbot_id,
        len(search_results),
        len(context),
    )

    if not context.strip():
        logger.info(
            "No knowledge base context found for chatbot_id=%s; skipping AI provider call",
            chatbot_id,
        )
        return AITestAnswerResponse(
            question=normalized_question,
            answer=NO_CONTEXT_ANSWER,
        )

    conversation_history = build_conversation_context(
        db,
        chat_session_id,
        normalized_question,
    )
    prompt = build_ai_prompt(
        context=context,
        question=normalized_question,
        conversation_history=conversation_history or None,
    )
    provider = get_provider_for_model(chatbot.ai_model)
    answer = provider.generate_answer(prompt)

    return AITestAnswerResponse(
        question=normalized_question,
        answer=answer,
    )
