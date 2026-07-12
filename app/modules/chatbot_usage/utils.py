"""
Chatbot usage helpers and synchronization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.chatbot.model import Chatbot
from app.modules.chatbot_usage.model import ChatbotUsage

logger = logging.getLogger(__name__)


def get_usage_by_chatbot_id(db: Session, chatbot_id: int) -> ChatbotUsage | None:
    """Return the usage row for a chatbot, if present."""
    return db.execute(
        select(ChatbotUsage).where(ChatbotUsage.chatbot_id == chatbot_id)
    ).scalar_one_or_none()


def build_chatbot_usage(chatbot_id: int, user_id: int) -> ChatbotUsage:
    """Build a zeroed chatbot_usage row."""
    now = datetime.now(timezone.utc)
    return ChatbotUsage(
        chatbot_id=chatbot_id,
        user_id=user_id,
        website_messages_used=0,
        playground_messages_used=0,
        website_tokens_used=0,
        playground_tokens_used=0,
        website_last_reset_at=now,
        playground_last_reset_at=now,
    )


def ensure_chatbot_usage_exists(
    db: Session,
    chatbot_id: int,
    user_id: int,
) -> ChatbotUsage:
    """Return existing usage or create a zeroed row (caller commits when needed)."""
    existing = get_usage_by_chatbot_id(db, chatbot_id)
    if existing is not None:
        return existing

    usage = build_chatbot_usage(chatbot_id, user_id)
    db.add(usage)
    db.flush()
    logger.info(
        "Created chatbot_usage chatbot_id=%s user_id=%s",
        chatbot_id,
        user_id,
    )
    return usage


def sync_existing_chatbot_usage(db_engine: Engine) -> int:
    """
    Create missing chatbot_usage rows for existing chatbots.

    Safe to run multiple times.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created = 0

    try:
        missing = db.execute(
            select(Chatbot.id, Chatbot.user_id)
            .outerjoin(ChatbotUsage, Chatbot.id == ChatbotUsage.chatbot_id)
            .where(ChatbotUsage.id.is_(None))
        ).all()

        for chatbot_id, user_id in missing:
            db.add(build_chatbot_usage(chatbot_id, user_id))
            created += 1

        if created:
            db.commit()
            logger.info("Synchronized %s missing chatbot_usage row(s)", created)
        else:
            logger.info("chatbot_usage sync complete; no missing rows")
    except Exception:
        db.rollback()
        logger.exception("Failed to synchronize chatbot_usage")
        raise
    finally:
        db.close()

    return created
