"""Utilities for chatbot prompt persistence and migrations."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.chatbot.model import Chatbot
from app.modules.prompt.model import ChatbotPrompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_MAX_LENGTH = 10_000
EXTRA_INSTRUCTION_MAX_LENGTH = 5_000
FIELD_MAX_LENGTH = 100

ALLOWED_TONES = frozenset({"Professional", "Friendly", "Formal", "Casual"})
ALLOWED_RESPONSE_STYLES = frozenset(
    {"Detailed", "Professional", "Technical", "Simple", "Creative"}
)
ALLOWED_RESPONSE_LENGTHS = frozenset({"Short", "Medium", "Long"})
ALLOWED_LANGUAGES = frozenset(
    {
        "English",
        "Hindi",
        "Spanish",
        "French",
        "German",
        "Portuguese",
        "Arabic",
        "Chinese",
        "Japanese",
    }
)


def normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
    """Convert blank strings to NULL and enforce maximum length."""
    if value is None:
        return None

    trimmed = value.strip()
    if not trimmed:
        return None

    if len(trimmed) > max_length:
        raise ValueError(f"Value exceeds maximum length of {max_length} characters.")

    return trimmed


def normalize_language(value: str | None) -> str | None:
    """Treat 'Default' and blank values as NULL."""
    normalized = normalize_optional_text(value, max_length=FIELD_MAX_LENGTH)
    if normalized is None:
        return None
    if normalized.lower() == "default":
        return None
    return normalized


def normalize_dropdown_value(
    value: str | None,
    *,
    allowed: frozenset[str],
    field_label: str,
) -> str | None:
    normalized = normalize_optional_text(value, max_length=FIELD_MAX_LENGTH)
    if normalized is None:
        return None
    if normalized not in allowed:
        raise ValueError(f"Invalid {field_label} value.")
    return normalized


def record_to_response_data(record: ChatbotPrompt) -> dict[str, str]:
    """Map ORM record to API response with empty strings for NULL."""
    return {
        "system_prompt": record.system_prompt or "",
        "tone": record.tone or "",
        "response_style": record.response_style or "",
        "response_length": record.response_length or "",
        "language": record.language or "",
        "extra_instruction": record.extra_instruction or "",
    }


def create_default_chatbot_prompt(
    db: Session,
    chatbot_id: int,
    *,
    commit: bool = False,
) -> ChatbotPrompt:
    """Create a NULL-default prompt row for a chatbot."""
    record = ChatbotPrompt(
        chatbot_id=chatbot_id,
        system_prompt=None,
        tone=None,
        response_style=None,
        response_length=None,
        language=None,
        extra_instruction=None,
    )
    db.add(record)
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record


def get_or_create_chatbot_prompt(db: Session, chatbot_id: int) -> ChatbotPrompt:
    """Return the chatbot prompt row, creating a default NULL row when missing."""
    record = db.execute(
        select(ChatbotPrompt).where(ChatbotPrompt.chatbot_id == chatbot_id)
    ).scalar_one_or_none()

    if record is not None:
        return record

    logger.info("Creating default chatbot_prompt row for chatbot_id=%s", chatbot_id)
    return create_default_chatbot_prompt(db, chatbot_id)


def backfill_chatbot_prompt_records(db: Session) -> int:
    """Create NULL-default prompt rows for chatbots that do not have one."""
    existing_ids = {
        row[0]
        for row in db.execute(select(ChatbotPrompt.chatbot_id)).all()
    }
    chatbot_ids = [row[0] for row in db.execute(select(Chatbot.id)).all()]
    created = 0

    for chatbot_id in chatbot_ids:
        if chatbot_id in existing_ids:
            continue
        create_default_chatbot_prompt(db, chatbot_id)
        created += 1

    if created:
        db.commit()
        logger.info("Backfilled %s chatbot_prompt records", created)

    return created


def apply_prompt_migrations(db_engine: Engine) -> None:
    """
    Ensure chatbot_prompt table exists and backfill rows for existing chatbots.

    Safe to run on every application startup.
    """
    inspector = inspect(db_engine)
    if "chatbot_prompt" not in inspector.get_table_names():
        logger.info("Creating chatbot_prompt table")
        ChatbotPrompt.__table__.create(bind=db_engine, checkfirst=True)
    elif "chatbots" not in inspector.get_table_names():
        return

    from app.core.database import SessionLocal

    with SessionLocal() as db:
        backfill_chatbot_prompt_records(db)
