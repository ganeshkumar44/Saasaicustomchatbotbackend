"""
Chat analysis ORM models.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatAnalysis(Base):
    """Aggregated chatbot analytics prepared for future dashboard reporting."""

    __tablename__ = "chat_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    total_conversations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    total_visitors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    resolved_conversations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    unresolved_conversations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    resolution_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )
    average_response_time: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )
    total_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    total_user_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    total_bot_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
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

    chatbot = relationship("Chatbot", back_populates="analysis", uselist=False)

    def __repr__(self) -> str:
        return f"<ChatAnalysis id={self.id} chatbot_id={self.chatbot_id}>"
