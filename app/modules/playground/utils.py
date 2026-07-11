"""
Playground module helpers.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import Chatbot
from app.modules.chatbot_settings.utils import get_owned_chatbot
from app.modules.playground.model import (
    DEFAULT_PLAYGROUND_SESSION_TITLE,
    PLAYGROUND_TITLE_MAX_LENGTH,
    SENDER_ASSISTANT,
    SENDER_USER,
    PlaygroundMessage,
    PlaygroundSession,
)

logger = logging.getLogger(__name__)


class PlaygroundSessionNotFoundError(Exception):
    """Raised when a Playground session does not exist or is inaccessible."""


class PlaygroundSessionMismatchError(Exception):
    """Raised when a Playground session does not belong to the given chatbot."""


def normalize_session_title(title: str | None) -> str:
    """Return a trimmed title or the default Playground title."""
    if title is None or not title.strip():
        return DEFAULT_PLAYGROUND_SESSION_TITLE
    return title.strip()[:PLAYGROUND_TITLE_MAX_LENGTH]


def build_title_from_question(question: str) -> str:
    """Build a session title from the first user question (max 60 chars)."""
    cleaned = " ".join(question.strip().split())
    if not cleaned:
        return DEFAULT_PLAYGROUND_SESSION_TITLE
    if len(cleaned) <= PLAYGROUND_TITLE_MAX_LENGTH:
        return cleaned
    return cleaned[:PLAYGROUND_TITLE_MAX_LENGTH].rstrip()


def get_accessible_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """
    Return a chatbot the user may use in Playground.

    Reuses the same manage permissions as chatbot settings:
    SuperAdmin → any, Admin → own + non-SuperAdmin, User → own only.
    """
    return get_owned_chatbot(db, user, chatbot_id)


def get_playground_session_or_raise(
    db: Session,
    session_id: int,
) -> PlaygroundSession:
    """Return a Playground session by id or raise PlaygroundSessionNotFoundError."""
    session = db.get(PlaygroundSession, session_id)
    if session is None:
        raise PlaygroundSessionNotFoundError()
    return session


def get_accessible_playground_session(
    db: Session,
    user: User,
    session_id: int,
) -> PlaygroundSession:
    """
    Return a Playground session the user may access.

    Validates chatbot manage permissions for the session's chatbot.
    """
    session = get_playground_session_or_raise(db, session_id)
    get_accessible_chatbot(db, user, session.chatbot_id)
    return session


def list_sessions_for_chatbot(
    db: Session,
    chatbot_id: int,
) -> list[PlaygroundSession]:
    """Return Playground sessions for a chatbot ordered by updated_at DESC."""
    return list(
        db.scalars(
            select(PlaygroundSession)
            .where(PlaygroundSession.chatbot_id == chatbot_id)
            .order_by(PlaygroundSession.updated_at.desc())
        ).all()
    )


def list_messages_for_session(
    db: Session,
    session_id: int,
) -> list[PlaygroundMessage]:
    """Return Playground messages for a session ordered by created_at ASC."""
    return list(
        db.scalars(
            select(PlaygroundMessage)
            .where(PlaygroundMessage.session_id == session_id)
            .order_by(PlaygroundMessage.created_at.asc())
        ).all()
    )


def get_playground_message_pairs(
    db: Session,
    session_id: int,
) -> list[tuple[str, str]]:
    """
    Return recent Playground turns as ``(user_message, assistant_message)`` pairs.

    Used by conversation memory so Playground reuses the same prompt formatting
    as the website widget without reading chat_messages.
    """
    messages = list_messages_for_session(db, session_id)
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None

    for message in messages:
        if message.sender == SENDER_USER:
            pending_user = message.message
        elif message.sender == SENDER_ASSISTANT and pending_user is not None:
            pairs.append((pending_user, message.message))
            pending_user = None

    return pairs


def create_session_record(
    db: Session,
    *,
    chatbot_id: int,
    user_id: int,
    title: str,
) -> PlaygroundSession:
    """Persist a new Playground session row (caller commits)."""
    session = PlaygroundSession(
        chatbot_id=chatbot_id,
        user_id=user_id,
        title=title,
    )
    db.add(session)
    db.flush()
    return session


def save_message_pair(
    db: Session,
    *,
    session: PlaygroundSession,
    user_message: str,
    assistant_message: str,
    response_time: Decimal | None,
    tokens_used: int | None = None,
) -> tuple[PlaygroundMessage, PlaygroundMessage]:
    """
    Save a user message and assistant response in one transaction unit.

    Caller is responsible for commit/rollback.
    """
    user_row = PlaygroundMessage(
        session_id=session.id,
        sender=SENDER_USER,
        message=user_message,
        response_time=None,
        tokens_used=None,
    )
    assistant_row = PlaygroundMessage(
        session_id=session.id,
        sender=SENDER_ASSISTANT,
        message=assistant_message,
        response_time=response_time,
        tokens_used=tokens_used,
    )
    db.add(user_row)
    db.add(assistant_row)
    db.flush()
    return user_row, assistant_row
