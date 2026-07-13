"""
Website feedback business logic.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import send_feedback_owner_email
from app.modules.feedback.model import (
    FEEDBACK_IP_MAX_LENGTH,
    FEEDBACK_USER_AGENT_MAX_LENGTH,
    Feedback,
)
from app.modules.feedback.schema import (
    CreateFeedbackRequest,
    CreateFeedbackSuccessResponse,
)
from app.modules.feedback.utils import (
    normalize_optional_text,
    validate_feedback_payload,
)

logger = logging.getLogger(__name__)


class FeedbackValidationError(Exception):
    """Raised when feedback payload fails field validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_feedback(payload: CreateFeedbackRequest) -> None:
    """Validate feedback request fields and raise on the first error."""
    error = validate_feedback_payload(
        rating=payload.rating,
        name=payload.name,
        email=str(payload.email) if payload.email is not None else None,
        phone_number=payload.phone_number,
        message=payload.message,
    )
    if error:
        raise FeedbackValidationError(error)


def create_feedback(
    db: Session,
    user: User,
    payload: CreateFeedbackRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CreateFeedbackSuccessResponse:
    """Persist website feedback for an authenticated user."""
    validate_feedback(payload)

    normalized_name = payload.name.strip()
    normalized_email = str(payload.email).strip().lower()
    normalized_phone = normalize_optional_text(payload.phone_number)
    normalized_message = normalize_optional_text(payload.message)
    normalized_ip = normalize_optional_text(ip_address)
    normalized_ua = normalize_optional_text(user_agent)

    if normalized_ip and len(normalized_ip) > FEEDBACK_IP_MAX_LENGTH:
        normalized_ip = normalized_ip[:FEEDBACK_IP_MAX_LENGTH]
    if normalized_ua and len(normalized_ua) > FEEDBACK_USER_AGENT_MAX_LENGTH:
        normalized_ua = normalized_ua[:FEEDBACK_USER_AGENT_MAX_LENGTH]

    feedback = Feedback(
        user_id=user.id,
        rating=payload.rating,
        name=normalized_name,
        email=normalized_email,
        phone_number=normalized_phone,
        message=normalized_message,
        ip_address=normalized_ip,
        user_agent=normalized_ua,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    logger.info(
        "Website feedback saved feedback_id=%s user_id=%s rating=%s",
        feedback.id,
        user.id,
        feedback.rating,
    )

    send_feedback_owner_email(
        rating=feedback.rating,
        name=feedback.name,
        email=feedback.email,
        phone_number=feedback.phone_number,
        message=feedback.message,
    )

    return CreateFeedbackSuccessResponse(
        message=messages.FEEDBACK_SUBMITTED_SUCCESS,
    )
