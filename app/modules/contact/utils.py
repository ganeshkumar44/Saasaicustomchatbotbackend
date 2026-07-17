"""Validation helpers for public contact submissions."""

from __future__ import annotations

import re

from app.core import messages
from app.modules.contact.model import (
    CONTACT_COMPANY_MAX_LENGTH,
    CONTACT_MESSAGE_MAX_LENGTH,
    CONTACT_NAME_MAX_LENGTH,
    CONTACT_PHONE_MAX_LENGTH,
    CONTACT_SUBJECT_MAX_LENGTH,
)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def validate_contact_payload(
    *,
    name: str | None,
    email: str | None,
    company: str | None,
    phone_number: str | None,
    subject: str | None,
    message: str | None,
) -> str | None:
    if _is_blank(name):
        return messages.CONTACT_NAME_REQUIRED
    assert name is not None
    if len(name.strip()) > CONTACT_NAME_MAX_LENGTH:
        return messages.CONTACT_NAME_TOO_LONG

    if _is_blank(email):
        return messages.CONTACT_EMAIL_REQUIRED
    assert email is not None
    normalized_email = email.strip().lower()
    if not _EMAIL_RE.match(normalized_email):
        return messages.CONTACT_EMAIL_INVALID

    if _is_blank(company):
        return messages.CONTACT_COMPANY_REQUIRED
    assert company is not None
    if len(company.strip()) > CONTACT_COMPANY_MAX_LENGTH:
        return messages.CONTACT_COMPANY_TOO_LONG

    if phone_number is not None and len(phone_number.strip()) > CONTACT_PHONE_MAX_LENGTH:
        return messages.CONTACT_PHONE_TOO_LONG

    if _is_blank(subject):
        return messages.CONTACT_SUBJECT_REQUIRED
    assert subject is not None
    if len(subject.strip()) > CONTACT_SUBJECT_MAX_LENGTH:
        return messages.CONTACT_SUBJECT_TOO_LONG

    if _is_blank(message):
        return messages.CONTACT_MESSAGE_REQUIRED
    assert message is not None
    if len(message.strip()) < 10:
        return messages.CONTACT_MESSAGE_TOO_SHORT
    if len(message.strip()) > CONTACT_MESSAGE_MAX_LENGTH:
        return messages.CONTACT_MESSAGE_TOO_LONG

    return None
