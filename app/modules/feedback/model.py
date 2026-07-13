"""
Website feedback ORM model.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

FEEDBACK_RATING_MIN = 1
FEEDBACK_RATING_MAX = 5
FEEDBACK_NAME_MAX_LENGTH = 100
FEEDBACK_PHONE_MAX_LENGTH = 20
FEEDBACK_MESSAGE_MAX_LENGTH = 2000
FEEDBACK_EMAIL_MAX_LENGTH = 255
FEEDBACK_IP_MAX_LENGTH = 64
FEEDBACK_USER_AGENT_MAX_LENGTH = 512


class Feedback(Base):
    """Authenticated-user website feedback submissions."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(FEEDBACK_NAME_MAX_LENGTH), nullable=False)
    email: Mapped[str] = mapped_column(String(FEEDBACK_EMAIL_MAX_LENGTH), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(
        String(FEEDBACK_PHONE_MAX_LENGTH),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(
        String(FEEDBACK_IP_MAX_LENGTH),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(FEEDBACK_USER_AGENT_MAX_LENGTH),
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

    user = relationship("User", backref="feedback_entries")

    def __repr__(self) -> str:
        return (
            f"<Feedback id={self.id} user_id={self.user_id} "
            f"rating={self.rating} email={self.email!r}>"
        )
