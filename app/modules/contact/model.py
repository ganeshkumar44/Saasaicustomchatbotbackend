"""
Landing-page contact submission ORM model.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

CONTACT_NAME_MAX_LENGTH = 100
CONTACT_EMAIL_MAX_LENGTH = 255
CONTACT_COMPANY_MAX_LENGTH = 150
CONTACT_PHONE_MAX_LENGTH = 20
CONTACT_SUBJECT_MAX_LENGTH = 150
CONTACT_MESSAGE_MAX_LENGTH = 2000
CONTACT_STATUS_MAX_LENGTH = 32
CONTACT_IP_MAX_LENGTH = 64
CONTACT_USER_AGENT_MAX_LENGTH = 512

CONTACT_STATUS_NEW = "new"
CONTACT_STATUS_NOTIFIED = "notified"
CONTACT_STATUS_FAILED_NOTIFY = "failed_notify"


class ContactSubmission(Base):
    """Unauthenticated landing-page contact / demo requests."""

    __tablename__ = "contact_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(CONTACT_NAME_MAX_LENGTH), nullable=False)
    email: Mapped[str] = mapped_column(String(CONTACT_EMAIL_MAX_LENGTH), nullable=False)
    company: Mapped[str] = mapped_column(String(CONTACT_COMPANY_MAX_LENGTH), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(
        String(CONTACT_PHONE_MAX_LENGTH),
        nullable=True,
    )
    subject: Mapped[str] = mapped_column(String(CONTACT_SUBJECT_MAX_LENGTH), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(CONTACT_STATUS_MAX_LENGTH),
        nullable=False,
        default=CONTACT_STATUS_NEW,
        server_default=CONTACT_STATUS_NEW,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(CONTACT_IP_MAX_LENGTH),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(CONTACT_USER_AGENT_MAX_LENGTH),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ContactSubmission id={self.id} email={self.email!r} "
            f"status={self.status!r}>"
        )
