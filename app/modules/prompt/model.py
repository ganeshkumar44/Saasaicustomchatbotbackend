"""ORM model for per-chatbot prompt configuration."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatbotPrompt(Base):
    """Optional per-chatbot prompt overrides. NULL fields use global defaults."""

    __tablename__ = "chatbot_prompt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_length: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    chatbot = relationship("Chatbot", back_populates="prompt_config")

    def __repr__(self) -> str:
        return f"<ChatbotPrompt id={self.id} chatbot_id={self.chatbot_id}>"
