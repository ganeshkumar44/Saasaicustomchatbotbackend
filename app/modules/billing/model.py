"""Billing foundation ORM models for future Razorpay integration."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

GATEWAY_RAZORPAY = "razorpay"
DEFAULT_CURRENCY = "INR"

PAYMENT_TYPE_ONE_TIME = "one_time"
PAYMENT_TYPE_RECURRING = "recurring"
PAYMENT_TYPE_RETRY = "retry"
ALLOWED_PAYMENT_TYPES = frozenset({
    PAYMENT_TYPE_ONE_TIME,
    PAYMENT_TYPE_RECURRING,
    PAYMENT_TYPE_RETRY,
})

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_SUCCESS = "success"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REFUNDED = "refunded"
PAYMENT_STATUS_CANCELLED = "cancelled"

ALLOWED_PAYMENT_STATUSES = frozenset({
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_SUCCESS,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_CANCELLED,
})

BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_SIX_MONTH = "six_month"
BILLING_CYCLE_YEARLY = "yearly"

ALLOWED_BILLING_CYCLES = frozenset({
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_SIX_MONTH,
    BILLING_CYCLE_YEARLY,
})

SUBSCRIPTION_ACTION_PURCHASE = "purchase"
SUBSCRIPTION_ACTION_UPGRADE = "upgrade"
SUBSCRIPTION_ACTION_DOWNGRADE = "downgrade"
SUBSCRIPTION_ACTION_RENEW = "renew"
SUBSCRIPTION_ACTION_CANCEL = "cancel"
SUBSCRIPTION_ACTION_EXPIRE = "expire"

ALLOWED_SUBSCRIPTION_ACTIONS = frozenset({
    SUBSCRIPTION_ACTION_PURCHASE,
    SUBSCRIPTION_ACTION_UPGRADE,
    SUBSCRIPTION_ACTION_DOWNGRADE,
    SUBSCRIPTION_ACTION_RENEW,
    SUBSCRIPTION_ACTION_CANCEL,
    SUBSCRIPTION_ACTION_EXPIRE,
})

INVOICE_STATUS_DRAFT = "draft"
INVOICE_STATUS_ISSUED = "issued"
INVOICE_STATUS_PAID = "paid"
INVOICE_STATUS_CANCELLED = "cancelled"
INVOICE_STATUS_REFUNDED = "refunded"

ALLOWED_INVOICE_STATUSES = frozenset({
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_ISSUED,
    INVOICE_STATUS_PAID,
    INVOICE_STATUS_CANCELLED,
    INVOICE_STATUS_REFUNDED,
})


class PaymentTransaction(Base):
    """Gateway payment attempts and settlements (Razorpay-ready)."""

    __tablename__ = "payment_transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plan_master.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    gateway: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=GATEWAY_RAZORPAY,
        server_default=GATEWAY_RAZORPAY,
    )
    gateway_order_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    gateway_subscription_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    gateway_customer_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    gateway_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    gateway_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=DEFAULT_CURRENCY,
        server_default=DEFAULT_CURRENCY,
    )
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PAYMENT_TYPE_ONE_TIME,
        server_default=PAYMENT_TYPE_ONE_TIME,
    )
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PAYMENT_STATUS_PENDING,
        server_default=PAYMENT_STATUS_PENDING,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_payment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("payment_transaction.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
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

    user = relationship("User", backref="payment_transactions")
    plan = relationship("PlanMaster", back_populates="payment_transactions")
    invoice = relationship(
        "Invoice",
        back_populates="payment_transaction",
        uselist=False,
    )
    subscription_histories = relationship(
        "SubscriptionHistory",
        back_populates="payment_transaction",
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentTransaction id={self.id} user_id={self.user_id} "
            f"status={self.status!r} amount={self.amount}>"
        )


class SubscriptionHistory(Base):
    """Audit log of subscription plan changes."""

    __tablename__ = "subscription_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_plan_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("plan_master.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    new_plan_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("plan_master.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payment_transaction_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("payment_transaction.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref="subscription_histories",
    )
    changed_by_user = relationship("User", foreign_keys=[changed_by])
    old_plan = relationship("PlanMaster", foreign_keys=[old_plan_id])
    new_plan = relationship("PlanMaster", foreign_keys=[new_plan_id])
    payment_transaction = relationship(
        "PaymentTransaction",
        back_populates="subscription_histories",
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionHistory id={self.id} user_id={self.user_id} "
            f"action={self.action!r}>"
        )


class Invoice(Base):
    """Invoice records linked to payment transactions (PDF later)."""

    __tablename__ = "invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    payment_transaction_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("payment_transaction.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plan_master.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    gst_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    gst_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=DEFAULT_CURRENCY,
        server_default=DEFAULT_CURRENCY,
    )
    invoice_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=INVOICE_STATUS_DRAFT,
        server_default=INVOICE_STATUS_DRAFT,
        index=True,
    )
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    billing_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
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

    user = relationship("User", backref="invoices")
    plan = relationship("PlanMaster", back_populates="invoices")
    payment_transaction = relationship(
        "PaymentTransaction",
        back_populates="invoice",
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} invoice_number={self.invoice_number!r} "
            f"status={self.invoice_status!r}>"
        )
