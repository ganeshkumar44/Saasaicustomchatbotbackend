"""
Chat messages helper utilities.
"""

import logging

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_messages.schema import ChatMessageResponse

logger = logging.getLogger(__name__)


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


def apply_chat_message_migrations(db_engine: Engine) -> None:
    """
    Align existing chat_messages tables with the current ORM schema.

    create_all() only creates new tables; it does not alter existing ones.
    """
    inspector = inspect(db_engine)
    if "chat_messages" not in inspector.get_table_names():
        return

    columns = {
        column["name"] for column in inspector.get_columns("chat_messages")
    }
    statements: list[str] = []

    if "response_time" not in columns:
        statements.append(
            "ALTER TABLE chat_messages ADD COLUMN response_time NUMERIC(10, 3)"
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    logger.info("Applied chat_messages schema migrations: %s", statements)
