"""
Chat sessions helper utilities.
"""

import logging
import secrets

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.chat_sessions.model import ChatSession
from app.modules.chat_sessions.schema import ChatSessionResponse

logger = logging.getLogger(__name__)


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
        visitor_step=session.visitor_step,
        started_at=session.started_at,
        last_activity=session.last_activity,
    )


def apply_chat_session_migrations(db_engine: Engine) -> None:
    """
    Align an existing chat_sessions table with the current ORM schema.

    create_all() only creates new tables; it does not alter existing ones.
    """
    inspector = inspect(db_engine)
    if "chat_sessions" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("chat_sessions")
    }
    statements: list[str] = []

    if "visitor_email" not in existing_columns:
        statements.append(
            "ALTER TABLE chat_sessions ADD COLUMN visitor_email VARCHAR(255)"
        )
    if "visitor_phone" not in existing_columns:
        statements.append(
            "ALTER TABLE chat_sessions ADD COLUMN visitor_phone VARCHAR(20)"
        )
    if "visitor_step" not in existing_columns:
        statements.append(
            "ALTER TABLE chat_sessions ADD COLUMN visitor_step VARCHAR(20) "
            "NOT NULL DEFAULT 'completed'"
        )

    if statements:
        with db_engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        logger.info("Applied chat_sessions schema migrations: %s", statements)

    visitor_id_col = next(
        (c for c in inspector.get_columns("chat_sessions") if c["name"] == "visitor_id"),
        None,
    )
    if visitor_id_col is not None:
        col_type = str(visitor_id_col["type"])
        if "64" in col_type and "100" not in col_type:
            with db_engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE chat_sessions "
                        "ALTER COLUMN visitor_id TYPE VARCHAR(100)"
                    )
                )
            logger.info("Widened chat_sessions.visitor_id to VARCHAR(100)")
