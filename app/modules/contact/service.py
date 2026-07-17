"""
Public landing-page contact business logic.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.utils import send_contact_owner_email
from app.modules.contact.model import (
    CONTACT_IP_MAX_LENGTH,
    CONTACT_STATUS_FAILED_NOTIFY,
    CONTACT_STATUS_NEW,
    CONTACT_STATUS_NOTIFIED,
    CONTACT_USER_AGENT_MAX_LENGTH,
    ContactSubmission,
)
from app.modules.contact.schema import (
    CreateContactRequest,
    CreateContactSuccessResponse,
)
from app.modules.contact.utils import normalize_optional_text, validate_contact_payload

logger = logging.getLogger(__name__)


class ContactValidationError(Exception):
    """Raised when contact payload fails field validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def create_contact_submission(
    db: Session,
    payload: CreateContactRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CreateContactSuccessResponse:
    """
    Persist a public contact submission.

    Honeypot (`website`) submissions are acknowledged without persistence.
    Email delivery failures do not roll back the saved submission.
    """
    if payload.website and payload.website.strip():
        logger.warning("Contact honeypot triggered; ignoring submission")
        return CreateContactSuccessResponse(message=messages.CONTACT_SUBMITTED_SUCCESS)

    error = validate_contact_payload(
        name=payload.name,
        email=str(payload.email) if payload.email is not None else None,
        company=payload.company,
        phone_number=payload.phone_number,
        subject=payload.subject,
        message=payload.message,
    )
    if error:
        raise ContactValidationError(error)

    normalized_ip = normalize_optional_text(ip_address)
    normalized_ua = normalize_optional_text(user_agent)
    if normalized_ip and len(normalized_ip) > CONTACT_IP_MAX_LENGTH:
        normalized_ip = normalized_ip[:CONTACT_IP_MAX_LENGTH]
    if normalized_ua and len(normalized_ua) > CONTACT_USER_AGENT_MAX_LENGTH:
        normalized_ua = normalized_ua[:CONTACT_USER_AGENT_MAX_LENGTH]

    submission = ContactSubmission(
        name=payload.name.strip(),
        email=str(payload.email).strip().lower(),
        company=payload.company.strip(),
        phone_number=normalize_optional_text(payload.phone_number),
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        status=CONTACT_STATUS_NEW,
        ip_address=normalized_ip,
        user_agent=normalized_ua,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    logger.info(
        "Contact submission saved contact_id=%s email=%s",
        submission.id,
        submission.email,
    )

    notified = send_contact_owner_email(
        name=submission.name,
        email=submission.email,
        company=submission.company,
        phone_number=submission.phone_number,
        subject=submission.subject,
        message=submission.message,
    )
    submission.status = (
        CONTACT_STATUS_NOTIFIED if notified else CONTACT_STATUS_FAILED_NOTIFY
    )
    db.commit()

    return CreateContactSuccessResponse(message=messages.CONTACT_SUBMITTED_SUCCESS)
