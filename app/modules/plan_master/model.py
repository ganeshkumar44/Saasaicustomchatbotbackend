"""
Static subscription plan catalog (plan_master).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_SIX_MONTH = "six_month"
BILLING_CYCLE_QUARTERLY = "quarterly"
BILLING_CYCLE_YEARLY = "yearly"

PLAN_NAME_FREE = "free"
PLAN_NAME_STARTER = "starter"
PLAN_NAME_PRO = "pro"
PLAN_NAME_ENTERPRISE = "enterprise"

DEFAULT_CURRENCY = "INR"

# Prefer JSONB on PostgreSQL; fall back to generic JSON for other dialects.
FeaturesJSON = JSON().with_variant(JSONB(), "postgresql")


class PlanMaster(Base):
    """Static subscription plan definitions. Limits live here, not on user_plan."""

    __tablename__ = "plan_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    max_chatbots: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL means unlimited (existing subscription / usage enforcement source of truth)
    chatbot_message_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playground_message_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Legacy single price kept for backward compatibility with existing APIs.
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
    monthly_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    six_month_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    yearly_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    six_month_discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    yearly_discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    monthly_razorpay_plan_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    six_month_razorpay_plan_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    yearly_razorpay_plan_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=DEFAULT_CURRENCY,
        server_default=DEFAULT_CURRENCY,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    features: Mapped[list[Any] | None] = mapped_column(FeaturesJSON, nullable=True)
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
    payment_transactions = relationship(
        "PaymentTransaction",
        back_populates="plan",
    )
    invoices = relationship("Invoice", back_populates="plan")

    def __repr__(self) -> str:
        return (
            f"<PlanMaster id={self.id} plan_name={self.plan_name!r} "
            f"max_chatbots={self.max_chatbots}>"
        )
