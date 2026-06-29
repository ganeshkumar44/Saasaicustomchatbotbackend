"""
Chat messages helper utilities.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_messages.schema import ChatMessageResponse


def get_message_by_id(db: Session, message_id: int) -> ChatMessage | None:
    """Return a chat message by its primary key."""
    return db.get(ChatMessage, message_id)


def get_messages_by_session_id(db: Session, session_id: int) -> list[ChatMessage]:
    """Return all chat messages for a session ordered by creation time."""
    return list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        ).scalars().all()
    )


def build_chat_message_response(message: ChatMessage) -> ChatMessageResponse:
    """Map a chat message ORM record to a Pydantic response."""
    return ChatMessageResponse(
        id=message.id,
        session_id=message.chat_session_id,
        user_message=message.user_message,
        bot_response=message.bot_response,
        created_at=message.created_at,
    )
