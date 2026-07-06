"""
AI answer generation service.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.ai.schema import AITestAnswerResponse
from app.modules.ai.providers.provider_factory import get_provider_for_model
from app.modules.ai.utils import (
    NO_CONTEXT_ANSWER,
    build_ai_prompt,
    normalize_question,
)
from app.modules.chatbot.model import Chatbot
from app.rag import rag_service
from app.rag.search_service import QueryRequiredError

logger = logging.getLogger(__name__)


class QuestionRequiredError(Exception):
    """Raised when the user question is empty."""


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


def generate_ai_answer(
    db: Session,
    chatbot_id: int,
    question: str,
    top_k: int = 5,
) -> AITestAnswerResponse:
    """
    Generate an AI answer using RAG context and the chatbot's configured provider.

    Flow:
    1. Retrieve top knowledge base chunks
    2. Build merged context
    3. Route to Gemini or Ollama based on chatbot.ai_model
    """
    normalized_question = normalize_question(question)
    if not normalized_question:
        raise QuestionRequiredError()

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    logger.info(
        "Starting AI answer generation for chatbot_id=%s ai_model=%s",
        chatbot_id,
        chatbot.ai_model,
    )

    context_result = rag_service.build_context(
        db,
        chatbot_id,
        normalized_question,
        top_k=top_k,
    )

    logger.info(
        "RAG retrieval completed for chatbot_id=%s with total_chunks=%s and context_length=%s",
        chatbot_id,
        context_result.total_chunks,
        context_result.context_length,
    )

    if not context_result.context.strip():
        logger.info(
            "No knowledge base context found for chatbot_id=%s; skipping AI provider call",
            chatbot_id,
        )
        return AITestAnswerResponse(
            question=normalized_question,
            answer=NO_CONTEXT_ANSWER,
        )

    prompt = build_ai_prompt(context_result.context, normalized_question)
    provider = get_provider_for_model(chatbot.ai_model)
    answer = provider.generate_answer(prompt)

    return AITestAnswerResponse(
        question=normalized_question,
        answer=answer,
    )
