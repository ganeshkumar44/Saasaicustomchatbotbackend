"""
Chat sessions business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.chatbot.model import Chatbot
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_PENDING,
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_CLOSED,
    VISITOR_STEP_NAME,
    ChatSession,
)
from app.modules.chat_sessions.schema import (
    ChatSessionResponse,
    UpdateChatSessionStatusRequest,
    UpdateChatSessionStatusResponse,
)
from app.modules.chat_sessions.utils import (
    build_chat_session_response,
    generate_unique_session_id,
    get_chat_session_by_session_id,
    validate_resolution_status,
    validate_session_status,
)

logger = logging.getLogger(__name__)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class ChatSessionNotFoundError(Exception):
    """Raised when the requested chat session does not exist."""


class ChatSessionValidationError(Exception):
    """Raised when chat session lifecycle input is invalid."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ChatAlreadyClosedError(Exception):
    """Raised when attempting to close an already closed chat session."""


class ChatSessionNotClosedError(Exception):
    """Raised when feedback is submitted before the chat session is closed."""


_UNSET = object()


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
        visitor_step=VISITOR_STEP_NAME,
        is_active=SESSION_STATUS_ACTIVE,
        is_resolved=SESSION_RESOLVED_PENDING,
        started_at=now,
        last_activity=now,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(
        "Created chat session session_id=%s chatbot_id=%s is_active=%s is_resolved=%s",
        session.session_id,
        chatbot_id,
        session.is_active,
        session.is_resolved,
    )

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


def update_visitor_onboarding(
    db: Session,
    session: ChatSession,
    *,
    visitor_step: str,
    visitor_id: str | None | object = _UNSET,
    visitor_email: str | None | object = _UNSET,
    visitor_phone: str | None | object = _UNSET,
) -> ChatSession:
    """Persist visitor onboarding fields and advance the session step."""
    now = datetime.now(timezone.utc)

    if visitor_id is not _UNSET:
        session.visitor_id = visitor_id  # type: ignore[assignment]
    if visitor_email is not _UNSET:
        session.visitor_email = visitor_email  # type: ignore[assignment]
    if visitor_phone is not _UNSET:
        session.visitor_phone = visitor_phone  # type: ignore[assignment]

    session.visitor_step = visitor_step
    session.last_activity = now
    session.updated_at = now

    db.commit()
    db.refresh(session)
    return session


def _get_session_or_raise(db: Session, session_id: str) -> ChatSession:
    """Return a chat session by public session_id or raise."""
    if not session_id or not session_id.strip():
        raise ChatSessionNotFoundError()

    session = get_chat_session_by_session_id(db, session_id.strip())
    if session is None:
        logger.warning("Chat session not found session_id=%s", session_id)
        raise ChatSessionNotFoundError()

    chatbot = db.get(Chatbot, session.chatbot_id)
    if chatbot is None:
        logger.warning(
            "Chatbot not found for session_id=%s chatbot_id=%s",
            session.session_id,
            session.chatbot_id,
        )
        raise ChatSessionNotFoundError()

    return session


def update_chat_session_status(
    db: Session,
    payload: UpdateChatSessionStatusRequest,
) -> UpdateChatSessionStatusResponse:
    """Update chat session lifecycle fields for close and feedback flows."""
    if payload.is_active is None and payload.is_resolved is None:
        raise ChatSessionValidationError(messages.SESSION_STATUS_REQUIRED)

    status_error = validate_session_status(payload.is_active)
    if status_error:
        raise ChatSessionValidationError(status_error)

    resolution_error = validate_resolution_status(payload.is_resolved)
    if resolution_error:
        raise ChatSessionValidationError(resolution_error)

    session = _get_session_or_raise(db, payload.session_id)
    response_message = messages.CHAT_SESSION_UPDATED

    if payload.is_active == SESSION_STATUS_CLOSED:
        if session.is_active == SESSION_STATUS_CLOSED and payload.is_resolved is None:
            raise ChatAlreadyClosedError()
        session.is_active = SESSION_STATUS_CLOSED
        response_message = messages.CHAT_SESSION_CLOSED

    if payload.is_resolved is not None:
        if payload.is_resolved in (
            SESSION_RESOLVED_RESOLVED,
            SESSION_RESOLVED_UNRESOLVED,
        ):
            if session.is_active != SESSION_STATUS_CLOSED:
                raise ChatSessionNotClosedError()
            session.is_resolved = payload.is_resolved
            response_message = (
                messages.CHAT_MARKED_RESOLVED
                if payload.is_resolved == SESSION_RESOLVED_RESOLVED
                else messages.CHAT_MARKED_UNRESOLVED
            )
        elif payload.is_resolved == SESSION_RESOLVED_PENDING:
            session.is_resolved = SESSION_RESOLVED_PENDING

    now = datetime.now(timezone.utc)
    session.last_activity = now
    session.updated_at = now

    db.commit()
    db.refresh(session)

    logger.info(
        "Updated chat session lifecycle session_id=%s is_active=%s is_resolved=%s",
        session.session_id,
        session.is_active,
        session.is_resolved,
    )

    return UpdateChatSessionStatusResponse(
        message=response_message,
        session_id=session.session_id,
        is_active=session.is_active,
        is_resolved=session.is_resolved,
    )
