"""
Static subscription plan catalog (plan_master).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_QUARTERLY = "quarterly"
BILLING_CYCLE_YEARLY = "yearly"

PLAN_NAME_FREE = "free"
PLAN_NAME_STARTER = "starter"
PLAN_NAME_PRO = "pro"
PLAN_NAME_ENTERPRISE = "enterprise"


class PlanMaster(Base):
    """Static subscription plan definitions. Limits live here, not on user_plan."""

    __tablename__ = "plan_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    max_chatbots: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL means unlimited
    chatbot_message_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playground_message_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    billing_cycle: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BILLING_CYCLE_MONTHLY,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    user_plans = relationship("UserPlan", back_populates="plan")

    def __repr__(self) -> str:
        return (
            f"<PlanMaster id={self.id} plan_name={self.plan_name!r} "
            f"max_chatbots={self.max_chatbots}>"
        )
