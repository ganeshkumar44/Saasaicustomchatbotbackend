"""
Playground module business logic.

Reuses the shared AI pipeline (``generate_ai_answer``) used by the website
widget. Only persistence differs: messages are stored in playground_* tables.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.ai import service as ai_service
from app.modules.ai.schema import AITestAnswerResponse
from app.modules.auth.model import User
from app.modules.playground.model import (
    DEFAULT_PLAYGROUND_SESSION_TITLE,
    PlaygroundSession,
)
from app.modules.playground.schema import (
    CreatePlaygroundSessionRequest,
    CreatePlaygroundSessionResponse,
    DeletePlaygroundSessionResponse,
    PlaygroundMessageItem,
    PlaygroundMessagesResponse,
    PlaygroundSessionItem,
    PlaygroundSessionListResponse,
)
from app.modules.playground.utils import (
    PlaygroundSessionMismatchError,
    PlaygroundSessionNotFoundError,
    build_title_from_question,
    create_session_record,
    get_accessible_chatbot,
    get_accessible_playground_session,
    list_messages_for_session,
    list_sessions_for_chatbot,
    normalize_session_title,
    save_message_pair,
)

logger = logging.getLogger(__name__)


class PlaygroundValidationError(Exception):
    """Raised when a Playground request fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _to_session_item(session: PlaygroundSession) -> PlaygroundSessionItem:
    return PlaygroundSessionItem(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def create_playground_session(
    db: Session,
    user: User,
    payload: CreatePlaygroundSessionRequest,
) -> CreatePlaygroundSessionResponse:
    """Create a new Playground conversation for an accessible chatbot."""
    chatbot = get_accessible_chatbot(db, user, payload.chatbot_id)
    title = normalize_session_title(payload.title)

    session = create_session_record(
        db,
        chatbot_id=chatbot.id,
        user_id=user.id,
        title=title,
    )
    db.commit()
    db.refresh(session)

    logger.info(
        "Playground session created id=%s chatbot_id=%s user_id=%s",
        session.id,
        chatbot.id,
        user.id,
    )

    return CreatePlaygroundSessionResponse(
        message=messages.PLAYGROUND_SESSION_CREATED_SUCCESS,
        data=_to_session_item(session),
    )


def get_playground_sessions(
    db: Session,
    user: User,
    chatbot_id: int,
) -> PlaygroundSessionListResponse:
    """Return all Playground sessions for a chatbot (latest first)."""
    chatbot = get_accessible_chatbot(db, user, chatbot_id)
    sessions = list_sessions_for_chatbot(db, chatbot.id)

    logger.info(
        "Listed %s Playground sessions for chatbot_id=%s user_id=%s",
        len(sessions),
        chatbot.id,
        user.id,
    )

    return PlaygroundSessionListResponse(
        data=[_to_session_item(session) for session in sessions],
    )


def get_playground_messages(
    db: Session,
    user: User,
    session_id: int,
) -> PlaygroundMessagesResponse:
    """Load the full Playground conversation for a session."""
    session = get_accessible_playground_session(db, user, session_id)
    rows = list_messages_for_session(db, session.id)

    logger.info(
        "Loaded %s Playground messages for session_id=%s user_id=%s",
        len(rows),
        session.id,
        user.id,
    )

    return PlaygroundMessagesResponse(
        data=[
            PlaygroundMessageItem(
                id=row.id,
                sender=row.sender,
                message=row.message,
                response_time=row.response_time,
                tokens_used=row.tokens_used,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


def delete_playground_session(
    db: Session,
    user: User,
    session_id: int,
) -> DeletePlaygroundSessionResponse:
    """Delete a Playground session and all related playground_messages."""
    session = get_accessible_playground_session(db, user, session_id)
    chatbot_id = session.chatbot_id

    db.delete(session)
    db.commit()

    logger.info(
        "Playground session deleted id=%s chatbot_id=%s user_id=%s",
        session_id,
        chatbot_id,
        user.id,
    )

    return DeletePlaygroundSessionResponse(
        message=messages.PLAYGROUND_SESSION_DELETED_SUCCESS,
    )


def save_playground_message(
    db: Session,
    *,
    session: PlaygroundSession,
    user_message: str,
    assistant_message: str,
    response_time: Decimal | None,
    tokens_used: int | None = None,
) -> None:
    """
    Persist a Playground turn and refresh session metadata.

    Commits the transaction. Raises on failure so callers can surface errors.
    """
    save_message_pair(
        db,
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        response_time=response_time,
        tokens_used=tokens_used,
    )

    if session.title == DEFAULT_PLAYGROUND_SESSION_TITLE:
        session.title = build_title_from_question(user_message)

    session.updated_at = datetime.now(timezone.utc)
    db.commit()


def generate_playground_answer(
    db: Session,
    user: User,
    *,
    chatbot_id: int,
    question: str,
    session_id: int,
) -> AITestAnswerResponse:
    """
    Generate an AI answer using the shared widget pipeline and persist it
    to playground_messages.

    Flow mirrors the website widget:
    Prompt Builder → Vector Search → Similarity / RAG → AI Provider
    Then stores the turn in playground_* tables only.
    """
    session = get_accessible_playground_session(db, user, session_id)
    if session.chatbot_id != chatbot_id:
        raise PlaygroundSessionMismatchError()

    # Ensure chatbot is still accessible (also covers deleted chatbots).
    chatbot = get_accessible_chatbot(db, user, chatbot_id)
    owner_user_id = chatbot.user_id

    normalized_question = ai_service.normalize_question(question)
    if not normalized_question:
        raise ai_service.QuestionRequiredError()

    logger.info(
        "Playground answer requested session_id=%s chatbot_id=%s user_id=%s",
        session.id,
        chatbot_id,
        user.id,
    )

    from app.modules.chatbot_usage.service import (
        USAGE_CHANNEL_PLAYGROUND,
        increment_playground_usage,
        validate_chatbot_usage,
    )

    validate_chatbot_usage(
        db,
        chatbot_id=chatbot_id,
        owner_user_id=owner_user_id,
        channel=USAGE_CHANNEL_PLAYGROUND,
    )

    start_time = time.perf_counter()
    ai_response = ai_service.generate_ai_answer(
        db,
        chatbot_id,
        normalized_question,
        playground_session_id=session.id,
    )
    response_time = Decimal(str(round(time.perf_counter() - start_time, 3)))

    try:
        save_playground_message(
            db,
            session=session,
            user_message=normalized_question,
            assistant_message=ai_response.answer,
            response_time=response_time,
            tokens_used=0,
        )
    except Exception:
        logger.exception(
            "Failed to save Playground messages session_id=%s chatbot_id=%s",
            session.id,
            chatbot_id,
        )
        db.rollback()
        raise

    try:
        # Providers do not currently return token usage; store 0.
        increment_playground_usage(
            db,
            chatbot_id=chatbot_id,
            owner_user_id=owner_user_id,
            tokens_used=0,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to increment playground usage session_id=%s chatbot_id=%s",
            session.id,
            chatbot_id,
        )

    logger.info(
        "Playground answer saved session_id=%s chatbot_id=%s response_time=%s",
        session.id,
        chatbot_id,
        response_time,
    )

    return ai_response
