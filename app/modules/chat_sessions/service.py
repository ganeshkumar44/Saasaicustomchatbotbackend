"""
Chat sessions business logic.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.chatbot.model import Chatbot
from app.modules.chat_sessions.model import ChatSession
from app.modules.chat_sessions.schema import ChatSessionResponse
from app.modules.chat_sessions.utils import (
    build_chat_session_response,
    generate_unique_session_id,
    get_chat_session_by_session_id,
)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class ChatSessionNotFoundError(Exception):
    """Raised when the requested chat session does not exist."""


def create_chat_session(
    db: Session,
    chatbot_id: int,
    visitor_id: str | None = None,
) -> ChatSessionResponse:
    """Create a new chat session for a published chatbot visitor."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    now = datetime.now(timezone.utc)
    session = ChatSession(
        chatbot_id=chatbot_id,
        session_id=generate_unique_session_id(db),
        visitor_id=visitor_id,
        started_at=now,
        last_activity=now,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return build_chat_session_response(session)


def get_chat_session(db: Session, session_id: str) -> ChatSessionResponse:
    """Return an existing chat session by session_id."""
    session = get_chat_session_by_session_id(db, session_id)
    if session is None:
        raise ChatSessionNotFoundError()

    return build_chat_session_response(session)


def update_last_activity(db: Session, session_id: str) -> ChatSessionResponse:
    """Update last_activity when a visitor interacts with the chatbot."""
    session = get_chat_session_by_session_id(db, session_id)
    if session is None:
        raise ChatSessionNotFoundError()

    now = datetime.now(timezone.utc)
    session.last_activity = now
    session.updated_at = now

    db.commit()
    db.refresh(session)

    return build_chat_session_response(session)
