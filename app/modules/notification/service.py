"""
Notification module business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import messages
from app.core.email_templates import (
    build_chatbot_updated_email,
    build_new_chatbot_created_email,
)
from app.modules.auth.model import User
from app.modules.auth.utils import _send_email
from app.modules.chatbot.model import Chatbot
from app.modules.notification.schema import (
    NotificationSettingsData,
    NotificationSettingsSuccessResponse,
    UpdateNotificationSettingsRequest,
    UpdateNotificationSettingsSuccessResponse,
)
from app.modules.notification.utils import (
    ensure_user_notification_settings_exists,
    should_send_email,
    should_send_push,
    should_send_sms,
)

logger = logging.getLogger(__name__)

DEFAULT_CHATBOT_NAME = "Your Chatbot"


def _to_settings_data(settings) -> NotificationSettingsData:
    return NotificationSettingsData(
        new_chatbot_email=settings.new_chatbot_email,
        chatbot_changes_email=settings.chatbot_changes_email,
        new_chat_start_push=settings.new_chat_start_push,
        critical_alert_sms=settings.critical_alert_sms,
    )


def _get_owner_user(db: Session, owner_user_id: int) -> User | None:
    owner = db.get(User, owner_user_id)
    if owner is None or not owner.email:
        logger.warning(
            "Notification recipient not found or missing email user_id=%s",
            owner_user_id,
        )
        return None
    return owner


def _resolve_chatbot_name(db: Session, chatbot_id: int | None) -> str:
    if chatbot_id is None:
        return DEFAULT_CHATBOT_NAME

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None or not chatbot.chatbot_name or not chatbot.chatbot_name.strip():
        return DEFAULT_CHATBOT_NAME

    return chatbot.chatbot_name.strip()


def _format_user_label(user: User) -> str:
    full_name = f"{user.first_name} {user.last_name}".strip()
    role_label = str(user.role).strip().capitalize()
    if full_name:
        return f"{full_name} ({role_label})"
    return role_label


def get_notification_settings(
    db: Session,
    user: User,
) -> NotificationSettingsSuccessResponse:
    """Return the authenticated user's notification preferences."""
    logger.info("Fetching notification settings for user_id=%s", user.id)

    settings = ensure_user_notification_settings_exists(db, user.id)

    return NotificationSettingsSuccessResponse(
        message=messages.NOTIFICATION_SETTINGS_RETRIEVED_SUCCESS,
        data=_to_settings_data(settings),
    )


def update_notification_settings(
    db: Session,
    user: User,
    payload: UpdateNotificationSettingsRequest,
) -> UpdateNotificationSettingsSuccessResponse:
    """Update the authenticated user's notification preferences."""
    logger.info("Notification settings update requested for user_id=%s", user.id)

    settings = ensure_user_notification_settings_exists(db, user.id)
    settings.new_chatbot_email = payload.new_chatbot_email
    settings.chatbot_changes_email = payload.chatbot_changes_email
    settings.new_chat_start_push = payload.new_chat_start_push
    settings.critical_alert_sms = payload.critical_alert_sms
    settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings)

    logger.info("Notification settings updated successfully for user_id=%s", user.id)

    return UpdateNotificationSettingsSuccessResponse(
        message=messages.NOTIFICATION_SETTINGS_UPDATED_SUCCESS,
        data=_to_settings_data(settings),
    )


def trigger_new_chatbot_created_notification(
    db: Session,
    chatbot: Chatbot,
) -> None:
    """Notify the chatbot owner when a chatbot is first published."""
    notify_new_chatbot_created(db, chatbot.user_id, chatbot.id)


def trigger_chatbot_updated_notification(
    db: Session,
    chatbot: Chatbot,
    updated_by: User,
) -> None:
    """Notify the chatbot owner when a chatbot is updated."""
    notify_chatbot_updated(
        db,
        owner_user_id=chatbot.user_id,
        chatbot_id=chatbot.id,
        updated_by_user_id=updated_by.id,
    )


def notify_new_chatbot_created(
    db: Session,
    owner_user_id: int,
    chatbot_id: int | None = None,
) -> None:
    """Send an email when a new chatbot is created and the preference is enabled."""
    if not should_send_email(db, owner_user_id, "new_chatbot_email"):
        logger.debug(
            "Skipping new chatbot email for user_id=%s chatbot_id=%s (disabled)",
            owner_user_id,
            chatbot_id,
        )
        return

    owner = _get_owner_user(db, owner_user_id)
    if owner is None:
        return

    chatbot_name = _resolve_chatbot_name(db, chatbot_id)
    subject, plain_body, html_body = build_new_chatbot_created_email(
        first_name=owner.first_name,
        chatbot_name=chatbot_name,
    )
    _send_email(owner.email, subject, plain_body, html_body)
    logger.info(
        "New chatbot notification email sent to user_id=%s chatbot_id=%s",
        owner_user_id,
        chatbot_id,
    )


def notify_chatbot_updated(
    db: Session,
    owner_user_id: int,
    chatbot_id: int | None = None,
    updated_by_user_id: int | None = None,
) -> None:
    """Send an email when a chatbot is updated and the preference is enabled."""
    if not should_send_email(db, owner_user_id, "chatbot_changes_email"):
        logger.debug(
            "Skipping chatbot changes email for user_id=%s chatbot_id=%s (disabled)",
            owner_user_id,
            chatbot_id,
        )
        return

    owner = _get_owner_user(db, owner_user_id)
    if owner is None:
        return

    updated_by_label = "A team member"
    if updated_by_user_id is not None:
        updater = db.get(User, updated_by_user_id)
        if updater is not None:
            updated_by_label = _format_user_label(updater)

    chatbot_name = _resolve_chatbot_name(db, chatbot_id)
    subject, plain_body, html_body = build_chatbot_updated_email(
        first_name=owner.first_name,
        chatbot_name=chatbot_name,
        updated_by_label=updated_by_label,
    )
    _send_email(owner.email, subject, plain_body, html_body)
    logger.info(
        "Chatbot update notification email sent to user_id=%s chatbot_id=%s updated_by=%s",
        owner_user_id,
        chatbot_id,
        updated_by_user_id,
    )


def notify_new_chat_started(
    db: Session,
    owner_user_id: int,
    chatbot_id: int | None = None,
    session_id: int | None = None,
) -> None:
    """
    Placeholder for new chat session push notifications.

    Checks owner preference before future push integration.
    """
    if not should_send_push(db, owner_user_id, "new_chat_start_push"):
        logger.debug(
            "Skipping new chat push for user_id=%s chatbot_id=%s (disabled)",
            owner_user_id,
            chatbot_id,
        )
        return

    # TODO: Send Push Notification
    logger.info(
        "New chat started notification eligible for user_id=%s chatbot_id=%s session_id=%s",
        owner_user_id,
        chatbot_id,
        session_id,
    )


def notify_chatbot_deleted(
    db: Session,
    owner_user_id: int,
    chatbot_id: int | None = None,
    deleted_by_user_id: int | None = None,
) -> None:
    """
    Placeholder for critical chatbot deletion SMS alerts.

    Checks owner preference before future SMS integration.
    """
    if not should_send_sms(db, owner_user_id, "critical_alert_sms"):
        logger.debug(
            "Skipping chatbot deletion SMS for user_id=%s chatbot_id=%s (disabled)",
            owner_user_id,
            chatbot_id,
        )
        return

    # TODO: Send SMS
    logger.info(
        "Chatbot deletion alert eligible for user_id=%s chatbot_id=%s deleted_by=%s",
        owner_user_id,
        chatbot_id,
        deleted_by_user_id,
    )
