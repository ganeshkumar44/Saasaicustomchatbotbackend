"""
User subscription plan ORM model.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

PLAN_STATUS_ACTIVE = "active"
PLAN_STATUS_EXPIRED = "expired"
PLAN_STATUS_CANCELLED = "cancelled"

BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_QUARTERLY = "quarterly"
BILLING_CYCLE_YEARLY = "yearly"

ALLOWED_BILLING_CYCLES = frozenset({
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_QUARTERLY,
    BILLING_CYCLE_YEARLY,
})

DEFAULT_CURRENT_BILLING = Decimal("0.00")


class UserPlan(Base):
    """Store each user's subscription plan and chatbot creation quota."""

    __tablename__ = "user_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False)
    chatbot_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    created_chatbots_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=PLAN_STATUS_ACTIVE,
        nullable=False,
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_billing: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=DEFAULT_CURRENT_BILLING,
        server_default="0.00",
        nullable=False,
    )
    next_billing_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    billing_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)
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

    user = relationship("User", backref="user_plan", uselist=False)

    def __repr__(self) -> str:
        return (
            f"<UserPlan id={self.id} user_id={self.user_id} "
            f"plan_name={self.plan_name!r} chatbot_limit={self.chatbot_limit} "
            f"created_chatbots_count={self.created_chatbots_count} "
            f"status={self.status!r}>"
        )
