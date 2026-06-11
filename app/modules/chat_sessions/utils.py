"""
Chat sessions helper utilities.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.chat_sessions.model import ChatSession
from app.modules.chat_sessions.schema import ChatSessionResponse


def generate_session_id() -> str:
    """Generate a unique URL-safe chat session identifier."""
    return f"sess_{secrets.token_hex(6)}"


def generate_unique_session_id(db: Session) -> str:
    """Generate a session ID that does not already exist in the database."""
    while True:
        session_id = generate_session_id()
        existing = db.execute(
            select(ChatSession.id).where(ChatSession.session_id == session_id)
        ).scalar_one_or_none()
        if existing is None:
            return session_id


def get_chat_session_by_session_id(
    db: Session,
    session_id: str,
) -> ChatSession | None:
    """Return a chat session by its public session identifier."""
    return db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    ).scalar_one_or_none()


def build_chat_session_response(session: ChatSession) -> ChatSessionResponse:
    """Map a chat session ORM record to a Pydantic response."""
    return ChatSessionResponse(
        id=session.id,
        chatbot_id=session.chatbot_id,
        session_id=session.session_id,
        visitor_id=session.visitor_id,
        started_at=session.started_at,
        last_activity=session.last_activity,
    )
