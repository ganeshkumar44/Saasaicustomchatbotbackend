"""
Theme module helper utilities.
"""

import logging

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import messages
from app.modules.auth.model import User
from app.modules.theme.model import ALLOWED_THEMES, DEFAULT_THEME, Theme

logger = logging.getLogger(__name__)


def validate_theme(value: str | None) -> str | None:
    """Validate a theme value. Returns an error message when invalid."""
    if value is None or not str(value).strip():
        return messages.INVALID_THEME

    normalized = str(value).strip().lower()
    if normalized not in ALLOWED_THEMES:
        return messages.INVALID_THEME

    return None


def normalize_theme(value: str) -> str:
    """Return a normalized theme value."""
    return str(value).strip().lower()


def build_default_theme(user_id: int) -> Theme:
    """Build a default theme record for a user."""
    return Theme(
        user_id=user_id,
        theme=DEFAULT_THEME,
    )


def get_theme_by_user_id(db: Session, user_id: int) -> Theme | None:
    """Return the theme record for a user, if one exists."""
    return db.execute(
        select(Theme).where(Theme.user_id == user_id)
    ).scalar_one_or_none()


def ensure_user_theme_exists(db: Session, user_id: int) -> Theme:
    """
    Return existing theme for a user or create one with default values.

    Safe to call multiple times; never creates duplicate records.
    """
    existing = get_theme_by_user_id(db, user_id)
    if existing is not None:
        return existing

    theme = build_default_theme(user_id)
    db.add(theme)
    db.commit()
    db.refresh(theme)

    logger.info("Created default theme for user_id=%s theme=%s", user_id, theme.theme)
    return theme


def sync_existing_user_themes(db_engine: Engine) -> int:
    """
    Create missing theme records for existing users.

    Safe to run multiple times; skips users who already have a theme record.
    Returns the number of records created.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created_count = 0

    try:
        missing_user_ids = db.execute(
            select(User.id)
            .outerjoin(Theme, User.id == Theme.user_id)
            .where(Theme.id.is_(None))
        ).scalars().all()

        for user_id in missing_user_ids:
            db.add(build_default_theme(user_id))
            created_count += 1

        if created_count:
            db.commit()
            logger.info("Synchronized %s missing theme records", created_count)
        else:
            logger.info("Theme synchronization complete; no missing records")
    except Exception:
        db.rollback()
        logger.exception("Failed to synchronize existing theme records")
        raise
    finally:
        db.close()

    return created_count
