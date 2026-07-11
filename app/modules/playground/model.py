"""
Playground ORM models.

Playground conversations are independent from website widget chat_sessions /
chat_messages and are used only by chatbot owners for pre-embed testing.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

SENDER_USER = "user"
SENDER_ASSISTANT = "assistant"
ALLOWED_SENDERS = frozenset({SENDER_USER, SENDER_ASSISTANT})

DEFAULT_PLAYGROUND_SESSION_TITLE = "New Chat"
PLAYGROUND_TITLE_MAX_LENGTH = 60


class PlaygroundSession(Base):
    """Owner-facing Playground conversation for a chatbot."""

    __tablename__ = "playground_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default=DEFAULT_PLAYGROUND_SESSION_TITLE,
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

    chatbot = relationship("Chatbot", backref="playground_sessions")
    user = relationship("User", backref="playground_sessions")
    messages = relationship(
        "PlaygroundMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PlaygroundMessage.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<PlaygroundSession id={self.id} chatbot_id={self.chatbot_id} "
            f"user_id={self.user_id} title={self.title!r}>"
        )


class PlaygroundMessage(Base):
    """Single Playground message (user or assistant)."""

    __tablename__ = "playground_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("playground_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    response_time: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session = relationship("PlaygroundSession", back_populates="messages")

    def __repr__(self) -> str:
        return (
            f"<PlaygroundMessage id={self.id} session_id={self.session_id} "
            f"sender={self.sender!r}>"
        )
