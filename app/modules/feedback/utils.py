"""Feedback validation helpers."""

from __future__ import annotations

import re

from app.core import messages
from app.modules.feedback.model import (
    FEEDBACK_MESSAGE_MAX_LENGTH,
    FEEDBACK_NAME_MAX_LENGTH,
    FEEDBACK_PHONE_MAX_LENGTH,
    FEEDBACK_RATING_MAX,
    FEEDBACK_RATING_MIN,
)

_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
)


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def validate_rating(rating: int | None) -> str | None:
    """Validate rating is an integer between 1 and 5."""
    if rating is None:
        return messages.FEEDBACK_RATING_REQUIRED
    if not isinstance(rating, int) or isinstance(rating, bool):
        return messages.FEEDBACK_RATING_INVALID
    if rating < FEEDBACK_RATING_MIN or rating > FEEDBACK_RATING_MAX:
        return messages.FEEDBACK_RATING_INVALID
    return None


def validate_name(name: str | None) -> str | None:
    """Validate feedback name."""
    if _is_blank(name):
        return messages.FEEDBACK_NAME_REQUIRED
    assert name is not None
    if len(name.strip()) > FEEDBACK_NAME_MAX_LENGTH:
        return messages.FEEDBACK_NAME_TOO_LONG
    return None


def validate_email(email: str | None) -> str | None:
    """Validate feedback email format."""
    if _is_blank(email):
        return messages.FEEDBACK_EMAIL_REQUIRED
    assert email is not None
    normalized = email.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        return messages.FEEDBACK_EMAIL_INVALID
    return None


def validate_phone_number(phone_number: str | None) -> str | None:
    """Validate optional phone number length."""
    if phone_number is None or not phone_number.strip():
        return None
    if len(phone_number.strip()) > FEEDBACK_PHONE_MAX_LENGTH:
        return messages.FEEDBACK_PHONE_TOO_LONG
    return None


def validate_message(message: str | None) -> str | None:
    """Validate optional feedback message length."""
    if message is None or not message.strip():
        return None
    if len(message.strip()) > FEEDBACK_MESSAGE_MAX_LENGTH:
        return messages.FEEDBACK_MESSAGE_TOO_LONG
    return None


def validate_feedback_payload(
    *,
    rating: int | None,
    name: str | None,
    email: str | None,
    phone_number: str | None,
    message: str | None,
) -> str | None:
    """
    Run all feedback field validations in order.

    Returns the first validation error message, or None when valid.
    """
    validators = (
        validate_rating(rating),
        validate_name(name),
        validate_email(email),
        validate_phone_number(phone_number),
        validate_message(message),
    )
    for error in validators:
        if error:
            return error
    return None


def normalize_optional_text(value: str | None) -> str | None:
    """Return trimmed text or None when blank."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None
