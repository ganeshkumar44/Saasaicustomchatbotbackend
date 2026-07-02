"""
Chat messages ORM models.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.core.database import Base


class ChatMessage(Base):
    """Store chatbot conversations between website visitors and the chatbot."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chat_session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    bot_response: Mapped[str] = mapped_column(Text, nullable=False)
    response_time: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Backward-compatible alias for existing dashboard aggregation queries.
    session_id = synonym("chat_session_id")

    chatbot = relationship("Chatbot", backref="chat_messages")
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return (
            f"<ChatMessage id={self.id} chatbot_id={self.chatbot_id} "
            f"chat_session_id={self.chat_session_id}>"
        )
