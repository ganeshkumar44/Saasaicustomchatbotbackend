"""
Chatbot subscription usage validation and counters.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.chatbot_usage.model import ChatbotUsage
from app.modules.chatbot_usage.schema import (
    ChatbotUsageData,
    ChatbotUsageSuccessResponse,
    PlanLimitsData,
)
from app.modules.chatbot_usage.utils import (
    ensure_chatbot_usage_exists,
    get_usage_by_chatbot_id,
)
from app.modules.plan_master.service import get_plan_limits
from app.modules.plan_master.utils import PlanLimits, is_unlimited

logger = logging.getLogger(__name__)

USAGE_CHANNEL_WEBSITE = "website"
USAGE_CHANNEL_PLAYGROUND = "playground"


class WebsiteMessageLimitExceededError(Exception):
    """Raised when website widget message quota is exhausted."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.WEBSITE_MESSAGE_LIMIT_REACHED
        super().__init__(self.message)


class PlaygroundMessageLimitExceededError(Exception):
    """Raised when Playground message quota is exhausted."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.PLAYGROUND_MESSAGE_LIMIT_REACHED
        super().__init__(self.message)


def get_chatbot_usage(db: Session, chatbot_id: int, user_id: int) -> ChatbotUsage:
    """Return (or create) usage for a chatbot owned by user_id."""
    return ensure_chatbot_usage_exists(db, chatbot_id, user_id)


def validate_chatbot_usage(
    db: Session,
    *,
    chatbot_id: int,
    owner_user_id: int,
    channel: str,
) -> ChatbotUsage:
    """
    Validate that a chatbot still has remaining messages for the given channel.

    ``channel`` must be ``website`` or ``playground``.
    """
    limits = get_plan_limits(db, owner_user_id)
    usage = get_chatbot_usage(db, chatbot_id, owner_user_id)

    if channel == USAGE_CHANNEL_WEBSITE:
        if not is_unlimited(limits.chatbot_message_limit):
            if usage.website_messages_used >= int(limits.chatbot_message_limit):
                logger.info(
                    "Website message limit reached chatbot_id=%s used=%s limit=%s",
                    chatbot_id,
                    usage.website_messages_used,
                    limits.chatbot_message_limit,
                )
                raise WebsiteMessageLimitExceededError()
        return usage

    if channel == USAGE_CHANNEL_PLAYGROUND:
        if not is_unlimited(limits.playground_message_limit):
            if usage.playground_messages_used >= int(limits.playground_message_limit):
                logger.info(
                    "Playground message limit reached chatbot_id=%s used=%s limit=%s",
                    chatbot_id,
                    usage.playground_messages_used,
                    limits.playground_message_limit,
                )
                raise PlaygroundMessageLimitExceededError()
        return usage

    raise ValueError(f"Unsupported usage channel: {channel}")


def increment_widget_usage(
    db: Session,
    *,
    chatbot_id: int,
    owner_user_id: int,
    tokens_used: int | None = None,
) -> ChatbotUsage:
    """Increment website message usage after a successful widget AI response."""
    usage = get_chatbot_usage(db, chatbot_id, owner_user_id)
    token_delta = int(tokens_used or 0)
    usage.website_messages_used += 1
    usage.website_tokens_used += token_delta
    usage.updated_at = datetime.now(timezone.utc)
    db.flush()
    logger.info(
        "Incremented website usage chatbot_id=%s messages=%s tokens_delta=%s",
        chatbot_id,
        usage.website_messages_used,
        token_delta,
    )
    return usage


def increment_playground_usage(
    db: Session,
    *,
    chatbot_id: int,
    owner_user_id: int,
    tokens_used: int | None = None,
) -> ChatbotUsage:
    """Increment Playground message usage after a successful AI response."""
    usage = get_chatbot_usage(db, chatbot_id, owner_user_id)
    token_delta = int(tokens_used or 0)
    usage.playground_messages_used += 1
    usage.playground_tokens_used += token_delta
    usage.updated_at = datetime.now(timezone.utc)
    db.flush()
    logger.info(
        "Incremented playground usage chatbot_id=%s messages=%s tokens_delta=%s",
        chatbot_id,
        usage.playground_messages_used,
        token_delta,
    )
    return usage


def reset_chatbot_usage(db: Session, chatbot_id: int) -> ChatbotUsage | None:
    """
    Reset all usage counters for a chatbot.

    Prepared for a future monthly scheduler. Safe to call anytime.
    """
    usage = get_usage_by_chatbot_id(db, chatbot_id)
    if usage is None:
        return None

    now = datetime.now(timezone.utc)
    usage.website_messages_used = 0
    usage.playground_messages_used = 0
    usage.website_tokens_used = 0
    usage.playground_tokens_used = 0
    usage.website_last_reset_at = now
    usage.playground_last_reset_at = now
    usage.updated_at = now
    db.flush()

    logger.info("Reset chatbot usage chatbot_id=%s", chatbot_id)
    return usage


def _limits_to_data(limits: PlanLimits) -> PlanLimitsData:
    return PlanLimitsData(
        plan_name=limits.plan_name,
        max_chatbots=limits.max_chatbots,
        chatbot_message_limit=limits.chatbot_message_limit,
        playground_message_limit=limits.playground_message_limit,
        chatbot_message_unlimited=is_unlimited(limits.chatbot_message_limit),
        playground_message_unlimited=is_unlimited(limits.playground_message_limit),
    )


def get_chatbot_usage_overview(
    db: Session,
    *,
    chatbot_id: int,
    owner_user_id: int,
) -> ChatbotUsageSuccessResponse:
    """Return plan limits and current usage for a chatbot."""
    limits = get_plan_limits(db, owner_user_id)
    usage = get_chatbot_usage(db, chatbot_id, owner_user_id)

    return ChatbotUsageSuccessResponse(
        data=ChatbotUsageData(
            chatbot_id=chatbot_id,
            website_messages_used=usage.website_messages_used,
            playground_messages_used=usage.playground_messages_used,
            website_tokens_used=usage.website_tokens_used,
            playground_tokens_used=usage.playground_tokens_used,
            website_last_reset_at=usage.website_last_reset_at,
            playground_last_reset_at=usage.playground_last_reset_at,
            limits=_limits_to_data(limits),
        )
    )
