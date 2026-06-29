"""
Chat messages business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.chatbot.model import Chatbot
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

logger = logging.getLogger(__name__)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class ChatSessionNotFoundError(Exception):
    """Raised when the requested chat session does not exist."""


class InvalidChatSessionError(Exception):
    """Raised when a chat session does not belong to the expected chatbot."""


class ChatMessageNotFoundError(Exception):
    """Raised when the requested chat message does not exist."""


def create_message(
    db: Session,
    payload: CreateChatMessageRequest,
) -> ChatMessageResponse:
    """
    Create a new chat message for an existing session.

    Persists chatbot_id and chat_session_id using the chat_sessions primary key
    (not the public sess_* string identifier).
    """
    session = db.get(ChatSession, payload.session_id)
    if session is None:
        logger.warning(
            "Chat session not found while saving message session_id=%s",
            payload.session_id,
        )
        raise ChatSessionNotFoundError()

    chatbot = db.get(Chatbot, session.chatbot_id)
    if chatbot is None:
        logger.warning(
            "Chatbot not found while saving message chatbot_id=%s session_id=%s",
            session.chatbot_id,
            payload.session_id,
        )
        raise ChatbotNotFoundError()

    if session.chatbot_id != chatbot.id:
        logger.warning(
            "Chat session does not belong to chatbot chat_session_id=%s "
            "chatbot_id=%s",
            session.id,
            chatbot.id,
        )
        raise InvalidChatSessionError()

    message = ChatMessage(
        chatbot_id=chatbot.id,
        chat_session_id=session.id,
        user_message=payload.user_message,
        bot_response=payload.bot_response,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    logger.info(
        "Chat message saved message_id=%s chatbot_id=%s chat_session_id=%s",
        message.id,
        message.chatbot_id,
        message.chat_session_id,
    )

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
