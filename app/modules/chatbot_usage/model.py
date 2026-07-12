"""
Per-chatbot subscription usage counters.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatbotUsage(Base):
    """Track website and Playground message/token usage for one chatbot."""

    __tablename__ = "chatbot_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    website_messages_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    playground_messages_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    website_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    playground_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    website_last_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    playground_last_reset_at: Mapped[datetime | None] = mapped_column(
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

    chatbot = relationship("Chatbot", backref="usage", uselist=False)
    user = relationship("User", backref="chatbot_usages")

    def __repr__(self) -> str:
        return (
            f"<ChatbotUsage id={self.id} chatbot_id={self.chatbot_id} "
            f"website_messages_used={self.website_messages_used} "
            f"playground_messages_used={self.playground_messages_used}>"
        )
