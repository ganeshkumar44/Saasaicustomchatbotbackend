"""
Notification module ORM models.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

DEFAULT_NEW_CHATBOT_EMAIL = False
DEFAULT_CHATBOT_CHANGES_EMAIL = False
DEFAULT_NEW_CHAT_START_PUSH = False
DEFAULT_CRITICAL_ALERT_SMS = False


class NotificationSettings(Base):
    """Store each user's notification preferences."""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    new_chatbot_email: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_NEW_CHATBOT_EMAIL,
        nullable=False,
    )
    chatbot_changes_email: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_CHATBOT_CHANGES_EMAIL,
        nullable=False,
    )
    new_chat_start_push: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_NEW_CHAT_START_PUSH,
        nullable=False,
    )
    critical_alert_sms: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_CRITICAL_ALERT_SMS,
        nullable=False,
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

    user = relationship("User", backref="notification_settings", uselist=False)

    def __repr__(self) -> str:
        return (
            f"<NotificationSettings id={self.id} user_id={self.user_id} "
            f"new_chatbot_email={self.new_chatbot_email} "
            f"chatbot_changes_email={self.chatbot_changes_email} "
            f"new_chat_start_push={self.new_chat_start_push} "
            f"critical_alert_sms={self.critical_alert_sms}>"
        )
