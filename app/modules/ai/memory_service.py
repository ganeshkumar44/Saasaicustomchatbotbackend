"""Conversation memory helpers for follow-up aware AI responses."""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.chat_messages.utils import get_messages_by_session_id

logger = logging.getLogger(__name__)

_FOLLOW_UP_PATTERNS = (
    r"\b(it|this|that|they|them|those|these|he|she|who|when|where|why|how)\b",
    r"^(what about|how about|tell me more|explain more|and what|difference between)",
    r"\b(also|another|more about|compared to|versus|vs\.?)\b",
)


def is_follow_up_question(question: str) -> bool:
    """Detect whether a question likely depends on prior conversation."""
    normalized = question.strip().lower()
    if not normalized:
        return False

    if len(normalized.split()) <= 6:
        return True

    return any(re.search(pattern, normalized) for pattern in _FOLLOW_UP_PATTERNS)


def format_conversation_history(
    messages: list[tuple[str, str]],
) -> str:
    """Format recent user/bot exchanges for inclusion in the AI prompt."""
    if not messages:
        return ""

    lines: list[str] = []
    for user_message, bot_response in messages:
        lines.append(f"User: {user_message.strip()}")
        lines.append(f"Assistant: {bot_response.strip()}")
    return "\n".join(lines)


def get_recent_conversation(
    db: Session,
    chat_session_id: int | None,
    *,
    limit: int | None = None,
) -> list[tuple[str, str]]:
    """
    Return the most recent conversation turns for a chat session.

    Each item is ``(user_message, bot_response)``.
    """
    if chat_session_id is None:
        return []

    settings = get_settings()
    message_limit = limit or settings.RAG_CONVERSATION_MEMORY_MESSAGES
    messages = get_messages_by_session_id(db, chat_session_id)
    if not messages:
        return []

    recent = messages[-message_limit:]
    return [
        (message.user_message, message.bot_response)
        for message in recent
    ]


def build_conversation_context(
    db: Session,
    chat_session_id: int | None,
    question: str,
) -> str:
    """
    Build recent conversation history for the AI prompt.

    Includes up to the configured number of prior turns so follow-up
    questions like "Who invented it?" can be understood in context.
    """
    recent_messages = get_recent_conversation(db, chat_session_id)
    if not recent_messages:
        return ""

    history = format_conversation_history(recent_messages)
    logger.info(
        "Including %s prior conversation turns for session_id=%s follow_up=%s",
        len(recent_messages),
        chat_session_id,
        is_follow_up_question(question),
    )
    return history
