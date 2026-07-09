"""
User subscription plan business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.user_plan.utils import (
    build_chatbot_creation_limit_message,
    ensure_user_plan_exists,
    get_user_plan_by_user_id,
    has_unlimited_chatbot_creation,
)

logger = logging.getLogger(__name__)


class ChatbotCreationLimitExceededError(Exception):
    """Raised when a user has reached their plan chatbot creation limit."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def create_default_user_plan(db: Session, user_id: int) -> None:
    """Create the default Free plan for a newly registered user."""
    ensure_user_plan_exists(db, user_id)


def get_user_plan(db: Session, user_id: int):
    """Return the user's plan record, creating the default plan when missing."""
    return ensure_user_plan_exists(db, user_id)


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
