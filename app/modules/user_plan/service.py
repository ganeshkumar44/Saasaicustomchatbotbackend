"""
User subscription plan business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.user_plan.schema import UserPlanBillingData
from app.modules.user_plan.utils import (
    build_chatbot_creation_limit_message,
    count_user_chatbots_ever_created,
    ensure_user_plan_exists,
    get_user_plan_by_user_id,
    has_unlimited_chatbot_creation,
    serialize_user_plan_billing,
)

logger = logging.getLogger(__name__)


class ChatbotCreationLimitExceededError(Exception):
    """Raised when a user has reached their plan chatbot creation limit."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UserPlanNotFoundError(Exception):
    """Raised when a user has no subscription plan record."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.USER_SUBSCRIPTION_DETAILS_NOT_FOUND
        super().__init__(self.message)


def create_default_user_plan(db: Session, user_id: int) -> None:
    """Create the default Free plan for a newly registered user."""
    ensure_user_plan_exists(db, user_id)


def get_user_plan(db: Session, user_id: int):
    """Return the user's plan record, creating the default plan when missing."""
    return ensure_user_plan_exists(db, user_id)


def get_user_plan_details(db: Session, user_id: int) -> UserPlanBillingData:
    """Return billing subscription details for a user without auto-creating a plan."""
    user_plan = get_user_plan_by_user_id(db, user_id)
    if user_plan is None:
        raise UserPlanNotFoundError()
    return serialize_user_plan_billing(user_plan)


def validate_chatbot_creation_limit(db: Session, user: User) -> None:
    """
    Validate whether the user may create another chatbot under their plan.

    SuperAdmin and Admin users bypass plan limits.
    """
    if has_unlimited_chatbot_creation(user):
        return

    user_plan = get_user_plan(db, user.id)

    if user_plan.created_chatbots_count >= user_plan.chatbot_limit:
        raise ChatbotCreationLimitExceededError(
            build_chatbot_creation_limit_message(user_plan.plan_name),
        )


def increment_created_chatbot_count(db: Session, user_id: int) -> None:
    """Increment the lifetime chatbot creation counter for a user plan."""
    user_plan = get_user_plan_by_user_id(db, user_id)
    if user_plan is None:
        user_plan = ensure_user_plan_exists(db, user_id)

    user_plan.created_chatbots_count += 1
    user_plan.updated_at = datetime.now(timezone.utc)


def decrement_created_chatbot_count(db: Session, user_id: int) -> None:
    """
    Decrement the chatbot creation counter when a draft is permanently deleted.

    Soft-deleted published chatbots still count toward the plan limit.
    """
    user_plan = get_user_plan_by_user_id(db, user_id)
    if user_plan is None:
        return

    if user_plan.created_chatbots_count > 0:
        user_plan.created_chatbots_count -= 1
        user_plan.updated_at = datetime.now(timezone.utc)


def reconcile_created_chatbot_count(db: Session, user_id: int) -> int:
    """
    Align created_chatbots_count with chatbot rows that still exist.

    Hard-deleted drafts no longer occupy a plan slot. Soft-deleted published
    chatbots still count because their rows remain in the database.
    """
    user_plan = get_user_plan(db, user_id)
    actual_count = count_user_chatbots_ever_created(db, user_id)

    if user_plan.created_chatbots_count != actual_count:
        logger.info(
            "Reconciling created_chatbots_count user_id=%s stored=%s actual=%s",
            user_id,
            user_plan.created_chatbots_count,
            actual_count,
        )
        user_plan.created_chatbots_count = actual_count
        user_plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_plan)

    return user_plan.created_chatbots_count
