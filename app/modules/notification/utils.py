"""
Notification module helper utilities.
"""

import logging
from typing import Literal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.model import User
from app.modules.notification.model import (
    DEFAULT_CHATBOT_CHANGES_EMAIL,
    DEFAULT_CRITICAL_ALERT_SMS,
    DEFAULT_NEW_CHAT_START_PUSH,
    DEFAULT_NEW_CHATBOT_EMAIL,
    NotificationSettings,
)

logger = logging.getLogger(__name__)

EmailNotificationField = Literal["new_chatbot_email", "chatbot_changes_email"]
PushNotificationField = Literal["new_chat_start_push"]
SmsNotificationField = Literal["critical_alert_sms"]


def build_default_notification_settings(user_id: int) -> NotificationSettings:
    """Build a default notification settings record for a user."""
    return NotificationSettings(
        user_id=user_id,
        new_chatbot_email=DEFAULT_NEW_CHATBOT_EMAIL,
        chatbot_changes_email=DEFAULT_CHATBOT_CHANGES_EMAIL,
        new_chat_start_push=DEFAULT_NEW_CHAT_START_PUSH,
        critical_alert_sms=DEFAULT_CRITICAL_ALERT_SMS,
    )


def create_default_notification_settings(
    db: Session,
    user_id: int,
) -> NotificationSettings:
    """
    Create and persist default notification settings for a user.

    Prefer ensure_user_notification_settings_exists() when duplicate safety is needed.
    """
    settings = build_default_notification_settings(user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    logger.info("Created default notification settings for user_id=%s", user_id)
    return settings


def get_notification_settings_by_user_id(
    db: Session,
    user_id: int,
) -> NotificationSettings | None:
    """Return the notification settings record for a user, if one exists."""
    return db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user_id)
    ).scalar_one_or_none()


def ensure_user_notification_settings_exists(
    db: Session,
    user_id: int,
) -> NotificationSettings:
    """
    Return existing notification settings for a user or create defaults.

    Safe to call multiple times; never creates duplicate records.
    """
    existing = get_notification_settings_by_user_id(db, user_id)
    if existing is not None:
        return existing

    settings = build_default_notification_settings(user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)

    logger.info(
        "Created default notification settings for user_id=%s",
        user_id,
    )
    return settings


def should_send_email(
    db: Session,
    user_id: int,
    field: EmailNotificationField,
) -> bool:
    """Return whether the user has enabled the given email notification."""
    settings = get_notification_settings_by_user_id(db, user_id)
    if settings is None:
        return False
    return bool(getattr(settings, field, False))


def should_send_push(
    db: Session,
    user_id: int,
    field: PushNotificationField = "new_chat_start_push",
) -> bool:
    """Return whether the user has enabled the given push notification."""
    settings = get_notification_settings_by_user_id(db, user_id)
    if settings is None:
        return False
    return bool(getattr(settings, field, False))


def should_send_sms(
    db: Session,
    user_id: int,
    field: SmsNotificationField = "critical_alert_sms",
) -> bool:
    """Return whether the user has enabled the given SMS notification."""
    settings = get_notification_settings_by_user_id(db, user_id)
    if settings is None:
        return False
    return bool(getattr(settings, field, False))


def sync_existing_notification_settings(db_engine: Engine) -> int:
    """
    Create missing notification settings records for existing users.

    Safe to run multiple times; skips users who already have a record.
    Returns the number of records created.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created_count = 0

    try:
        missing_user_ids = db.execute(
            select(User.id)
            .outerjoin(
                NotificationSettings,
                User.id == NotificationSettings.user_id,
            )
            .where(NotificationSettings.id.is_(None))
        ).scalars().all()

        for user_id in missing_user_ids:
            db.add(build_default_notification_settings(user_id))
            created_count += 1

        if created_count:
            db.commit()
            logger.info(
                "Synchronized %s missing notification settings records",
                created_count,
            )
        else:
            logger.info(
                "Notification settings synchronization complete; no missing records",
            )
    except Exception:
        db.rollback()
        logger.exception("Failed to synchronize existing notification settings")
        raise
    finally:
        db.close()

    return created_count
