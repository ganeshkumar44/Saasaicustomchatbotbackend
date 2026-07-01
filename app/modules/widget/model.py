"""
Widget visitor ORM models.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WidgetVisitor(Base):
    """Persistent widget visitor profile reused across chat sessions."""

    __tablename__ = "widget_visitors"
    __table_args__ = (
        UniqueConstraint("chatbot_id", "visitor_key", name="uq_widget_visitors_chatbot_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visitor_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visitor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    visitor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    visitor_phone: Mapped[str] = mapped_column(String(20), nullable=False)
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

    chatbot = relationship("Chatbot")

    def __repr__(self) -> str:
        return (
            f"<WidgetVisitor id={self.id} chatbot_id={self.chatbot_id} "
            f"visitor_key={self.visitor_key!r}>"
        )
