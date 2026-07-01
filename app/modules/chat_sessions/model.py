"""
Chat sessions ORM models.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

VISITOR_STEP_NAME = "name"
VISITOR_STEP_EMAIL = "email"
VISITOR_STEP_PHONE = "phone"
VISITOR_STEP_COMPLETED = "completed"

SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_CLOSED = "closed"

SESSION_RESOLVED_PENDING = "pending"
SESSION_RESOLVED_RESOLVED = "resolved"
SESSION_RESOLVED_UNRESOLVED = "unresolved"

ALLOWED_SESSION_STATUSES = {SESSION_STATUS_ACTIVE, SESSION_STATUS_CLOSED}
ALLOWED_RESOLUTION_STATUSES = {
    SESSION_RESOLVED_PENDING,
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
}


class ChatSession(Base):
    """Track website visitors and chatbot conversations."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    visitor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visitor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visitor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visitor_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    visitor_step: Mapped[str] = mapped_column(
        String(20),
        default=VISITOR_STEP_NAME,
        nullable=False,
    )
    is_active: Mapped[str] = mapped_column(
        String(20),
        default=SESSION_STATUS_ACTIVE,
        nullable=False,
    )
    is_resolved: Mapped[str] = mapped_column(
        String(20),
        default=SESSION_RESOLVED_PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
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

    chatbot = relationship("Chatbot", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ChatSession id={self.id} chatbot_id={self.chatbot_id} "
            f"session_id={self.session_id!r}>"
        )
