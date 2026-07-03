"""
Chatbot module ORM models.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

CHATBOT_STATUS_DRAFT = "draft"
CHATBOT_STATUS_PUBLISHED = "published"


class Chatbot(Base):
    """Chatbot builder record owned by a user."""

    __tablename__ = "chatbots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chatbot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    personality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=CHATBOT_STATUS_DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    user = relationship("User", backref="chatbots")
    settings = relationship(
        "ChatbotSettings",
        back_populates="chatbot",
        uselist=False,
        cascade="all, delete-orphan",
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="chatbot",
        cascade="all, delete-orphan",
    )
    knowledge_chunks = relationship(
        "KnowledgeChunk",
        back_populates="chatbot",
        cascade="all, delete-orphan",
    )
    analysis = relationship(
        "ChatAnalysis",
        back_populates="chatbot",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Chatbot id={self.id} user_id={self.user_id} status={self.status!r}>"


class ChatbotSettings(Base):
    """Widget and embed configuration for a published chatbot."""

    __tablename__ = "chatbot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    typing_indicator: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    primary_color: Mapped[str] = mapped_column(String(20), default="#000000", nullable=False)
    text_color: Mapped[str] = mapped_column(String(20), default="#ffffff", nullable=False)
    widget_position: Mapped[str] = mapped_column(
        String(50),
        default="bottom-right",
        nullable=False,
    )
    show_avatar: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    chat_title: Mapped[str] = mapped_column(String(255), default="Chat with us", nullable=False)
    welcome_message: Mapped[str] = mapped_column(
        Text,
        default=(
            "Hi there! 👋 Welcome to our support chat. "
            "How can we assist you today?"
        ),
        nullable=False,
    )
    input_placeholder: Mapped[str] = mapped_column(
        String(255),
        default="Type your message...",
        nullable=False,
    )
    public_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    embed_code: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_domains: Mapped[str] = mapped_column(Text, nullable=False)
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

    chatbot = relationship("Chatbot", back_populates="settings")

    def __repr__(self) -> str:
        return f"<ChatbotSettings id={self.id} chatbot_id={self.chatbot_id}>"
