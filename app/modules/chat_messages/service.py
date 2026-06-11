"""
Chat messages business logic.
"""

from sqlalchemy.orm import Session

from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_messages.schema import (
    ChatMessageResponse,
    CreateChatMessageRequest,
)
from app.modules.chat_messages.utils import (
    build_chat_message_response,
    get_message_by_id as get_message_record_by_id,
    get_messages_by_session_id,
)
from app.modules.chat_sessions.model import ChatSession


class ChatSessionNotFoundError(Exception):
    """Raised when the requested chat session does not exist."""


class ChatMessageNotFoundError(Exception):
    """Raised when the requested chat message does not exist."""


def create_message(
    db: Session,
    payload: CreateChatMessageRequest,
) -> ChatMessageResponse:
    """Create a new chat message for an existing session."""
    session = db.get(ChatSession, payload.session_id)
    if session is None:
        raise ChatSessionNotFoundError()

    message = ChatMessage(
        session_id=payload.session_id,
        user_message=payload.user_message,
        bot_response=payload.bot_response,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return build_chat_message_response(message)


def get_message_by_id(db: Session, message_id: int) -> ChatMessageResponse:
    """Return a single chat message by its primary key."""
    message = get_message_record_by_id(db, message_id)
    if message is None:
        raise ChatMessageNotFoundError()

    return build_chat_message_response(message)


def get_session_messages(db: Session, session_id: int) -> list[ChatMessageResponse]:
    """Return all messages for a chat session."""
    session = db.get(ChatSession, session_id)
    if session is None:
        raise ChatSessionNotFoundError()

    messages = get_messages_by_session_id(db, session_id)
    return [build_chat_message_response(message) for message in messages]
