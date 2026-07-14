"""Billing API request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


class BillingPlanData(BaseModel):
    """Active plan catalog item for pricing / billing pages."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: int
    id: int
    plan_name: str
    display_name: str
    description: str | None = None
    monthly_price: float
    six_month_price: float
    yearly_price: float
    six_month_discount_percentage: float = 0.0
    yearly_discount_percentage: float = 0.0
    six_month_saving: float = 0.0
    yearly_saving: float = 0.0
    currency: str
    chatbot_limit: int
    website_message_limit: int | None = None
    playground_message_limit: int | None = None
    website_message_unlimited: bool = False
    playground_message_unlimited: bool = False
    features: list[str] = Field(default_factory=list)
    display_order: int = 0
    is_active: bool = True
    current_plan: bool = False
    recommended: bool = False
    can_upgrade: bool = False
    can_downgrade: bool = False


class BillingPlansSuccessResponse(BaseModel):
    success: bool = True
    data: list[BillingPlanData]


class CurrentPlanData(BaseModel):
    """Logged-in user's current subscription snapshot."""

    user_id: int
    plan_id: int | None = None
    plan_name: str
    display_name: str
    subscription_status: str
    billing_cycle: str | None = None
    subscription_start: datetime | None = None
    subscription_end: datetime | None = None
    next_billing_date: datetime | None = None
    is_auto_renew: bool = False
    remaining_days: int | None = None
    is_expired: bool = False
    razorpay_subscription_id: str | None = None
    website_message_limit: int | None = None
    playground_message_limit: int | None = None
    chatbot_limit: int
    website_message_unlimited: bool = False
    playground_message_unlimited: bool = False
    currency: str | None = None
    monthly_price: float | None = None
    current_price: float | None = None
    current_billing: float | None = None
    created_chatbots_count: int = 0
    remaining_chatbots: int | None = None


class CurrentPlanSuccessResponse(BaseModel):
    success: bool = True
    data: CurrentPlanData


class CheckoutRequest(BaseModel):
    """Checkout preview request (no Razorpay order creation)."""

    plan_id: int = Field(..., ge=1)
    billing_cycle: str


class CheckoutData(BaseModel):
    """Checkout preview payload ready for future Razorpay order creation."""

    plan_id: int
    plan_name: str
    display_name: str
    billing_cycle: str
    action: Literal["upgrade", "downgrade", "switch"]
    price: float
    currency: str
    subtotal: float
    discount: float
    discount_percentage: float = 0.0
    saving: float = 0.0
    list_price: float = 0.0
    gst_percentage: float
    gst_amount: float
    total_amount: float
    chatbot_limit: int
    website_message_limit: int | None = None
    playground_message_limit: int | None = None
    features: list[str] = Field(default_factory=list)


class CheckoutSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    checkout: CheckoutData


class CreateOrderRequest(BaseModel):
    """Create Razorpay order request (amount calculated server-side only)."""

    plan_id: int = Field(..., ge=1)
    billing_cycle: str


class CreateOrderData(BaseModel):
    """Razorpay Checkout open payload + order metadata."""

    order_id: str
    key: str
    amount: int = Field(..., description="Amount in paise")
    currency: str
    plan_id: int
    plan_name: str
    display_name: str
    billing_cycle: str
    action: Literal["upgrade", "downgrade", "switch"]
    subtotal: float
    discount: float
    gst_percentage: float
    gst_amount: float
    total_amount: float


class CreateOrderSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    order_id: str
    key: str
    amount: int
    currency: str
    plan_name: str
    billing_cycle: str
    data: CreateOrderData


class CreateSubscriptionRequest(BaseModel):
    """Create Razorpay subscription (AutoPay) request."""

    plan_id: int = Field(..., ge=1)
    billing_cycle: str
    auto_renew: bool = True


class CreateSubscriptionData(BaseModel):
    subscription_id: str
    key: str
    customer_id: str | None = None
    plan_id: int
    plan_name: str
    display_name: str
    billing_cycle: str
    action: Literal["upgrade", "downgrade", "switch"]
    currency: str
    amount: int
    total_amount: float
    subtotal: float
    discount: float
    gst_percentage: float
    gst_amount: float
    auto_renew: bool = True


class CreateSubscriptionSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    subscription_id: str
    key: str
    data: CreateSubscriptionData


class AutoRenewRequest(BaseModel):
    subscription_id: str | None = None


class AutoRenewData(BaseModel):
    subscription_id: str | None = None
    is_auto_renew: bool
    requires_checkout: bool = False
    mode: str | None = None
    key: str | None = None
    plan_id: int | None = None
    plan_name: str | None = None
    display_name: str | None = None
    billing_cycle: str | None = None
    subscription_end: datetime | None = None
    next_billing_date: datetime | None = None
    amount: int | None = None
    currency: str | None = None
    customer_id: str | None = None
    total_amount: float | None = None


class AutoRenewSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: AutoRenewData


class CancelSubscriptionRequest(BaseModel):
    subscription_id: str | None = None


class CancelSubscriptionData(BaseModel):
    subscription_id: str | None = None
    is_auto_renew: bool = False
    subscription_status: str
    subscription_end: datetime | None = None
    next_billing_date: datetime | None = None
    remaining_days: int | None = None


class CancelSubscriptionSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: CancelSubscriptionData


class RetryPaymentRequest(BaseModel):
    payment_transaction_id: int = Field(..., ge=1)


class RetryPaymentSuccessResponse(BaseModel):
    """Same shape as create-order so frontend can reuse Razorpay Checkout."""

    success: bool = True
    message: str | None = None
    order_id: str
    key: str
    amount: int
    currency: str
    plan_name: str
    billing_cycle: str
    data: CreateOrderData


class SubscriptionStatusData(BaseModel):
    user_id: int
    plan_id: int | None = None
    plan_name: str
    display_name: str
    subscription_status: str
    is_auto_renew: bool = False
    razorpay_subscription_id: str | None = None
    billing_cycle: str | None = None
    subscription_start: datetime | None = None
    subscription_end: datetime | None = None
    next_billing_date: datetime | None = None
    remaining_days: int | None = None
    is_expired: bool = False
    can_cancel: bool = False
    can_retry_payment: bool = False


class SubscriptionStatusSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: SubscriptionStatusData


class VerifyPaymentRequest(BaseModel):
    """Razorpay Checkout success payload for order or subscription verification."""

    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_signature: str = Field(..., min_length=1)
    razorpay_order_id: str | None = None
    razorpay_subscription_id: str | None = None


class VerifyPaymentData(BaseModel):
    """Activated subscription snapshot after successful verification."""

    payment_id: int
    gateway_order_id: str | None = None
    gateway_payment_id: str | None = None
    gateway_subscription_id: str | None = None
    status: str
    plan_id: int
    plan_name: str
    display_name: str
    billing_cycle: str
    action: str | None = None
    amount: float
    currency: str
    payment_method: str | None = None
    payment_type: str | None = None
    subscription_status: str
    subscription_start: datetime | None = None
    subscription_end: datetime | None = None
    next_billing_date: datetime | None = None
    remaining_days: int | None = None
    is_auto_renew: bool = False
    already_verified: bool = False


class VerifyPaymentSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: VerifyPaymentData


class PlanComparisonValue(BaseModel):
    plan_id: int
    plan_name: str
    display_name: str
    value: str | bool | int | None = None


class PlanComparisonRow(BaseModel):
    feature_key: str
    feature_label: str
    values: list[PlanComparisonValue]


class PlanComparisonPlanHeader(BaseModel):
    plan_id: int
    plan_name: str
    display_name: str
    recommended: bool = False
    current_plan: bool = False
    display_order: int = 0


class PlanComparisonData(BaseModel):
    plans: list[PlanComparisonPlanHeader]
    rows: list[PlanComparisonRow]


class PlanComparisonSuccessResponse(BaseModel):
    success: bool = True
    data: PlanComparisonData


class PaymentHistoryItem(BaseModel):
    id: int
    plan_id: int
    plan_name: str | None = None
    gateway: str
    gateway_order_id: str | None = None
    gateway_payment_id: str | None = None
    gateway_subscription_id: str | None = None
    amount: str
    currency: str
    billing_cycle: str
    payment_method: str | None = None
    payment_type: str = "one_time"
    retry_of_payment_id: int | None = None
    status: str
    failure_reason: str | None = None
    transaction_date: datetime
    created_at: datetime


class PaymentHistorySuccessResponse(BaseModel):
    success: bool = True
    data: list[PaymentHistoryItem]


class PaymentDetailSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: PaymentHistoryItem


class SubscriptionHistoryItem(BaseModel):
    id: int
    old_plan_id: int | None = None
    old_plan_name: str | None = None
    new_plan_id: int | None = None
    new_plan_name: str | None = None
    action: str
    payment_transaction_id: int | None = None
    changed_by: int | None = None
    changed_at: datetime
    created_at: datetime


class SubscriptionHistorySuccessResponse(BaseModel):
    success: bool = True
    data: list[SubscriptionHistoryItem]


class InvoiceItem(BaseModel):
    id: int
    invoice_number: str
    invoice_date: datetime | None = None
    payment_transaction_id: int | None = None
    plan_id: int
    plan_name: str | None = None
    display_name: str | None = None
    billing_cycle: str | None = None
    subtotal: str
    discount: str
    gst_percentage: str
    gst_amount: str
    total_amount: str
    currency: str
    invoice_status: str
    pdf_path: str | None = None
    billing_name: str | None = None
    billing_email: str | None = None
    billing_phone: str | None = None
    billing_address: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_country: str | None = None
    billing_pincode: str | None = None
    gst_number: str | None = None
    company_name: str | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    created_at: datetime
    updated_at: datetime


class InvoicesSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: list[InvoiceItem]


class InvoiceDetailSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: InvoiceItem


class ResendInvoiceRequest(BaseModel):
    invoice_id: int = Field(..., ge=1)


class ResendInvoiceSuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: InvoiceItem | None = None


def format_money(value: Decimal | None) -> str:
    """Format a Decimal amount as a two-decimal string."""
    return _decimal_str(value if value is not None else Decimal("0.00")) or "0.00"
