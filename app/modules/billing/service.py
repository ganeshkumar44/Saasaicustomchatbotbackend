"""Billing service layer — plans, checkout preview, comparison, history."""

from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.billing.activation import (
    remaining_subscription_days,
    verify_and_activate_payment,
)
from app.modules.billing.checkout import (
    BillingValidationError,
    build_checkout_amounts,
    money_to_float,
    normalize_billing_cycle,
    resolve_active_plan_or_raise,
    validate_plan_change,
)
from app.modules.billing.order import create_pending_razorpay_order
from app.modules.billing.razorpay_service import RazorpayServiceError
from app.modules.billing.schema import (
    BillingPlanData,
    BillingPlansSuccessResponse,
    CheckoutData,
    CheckoutRequest,
    CheckoutSuccessResponse,
    CreateOrderData,
    CreateOrderRequest,
    CreateOrderSuccessResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionSuccessResponse,
    AutoRenewRequest,
    AutoRenewSuccessResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionSuccessResponse,
    CurrentPlanData,
    CurrentPlanSuccessResponse,
    InvoiceItem,
    InvoicesSuccessResponse,
    InvoiceDetailSuccessResponse,
    ResendInvoiceRequest,
    ResendInvoiceSuccessResponse,
    PaymentDetailSuccessResponse,
    PaymentHistoryItem,
    PaymentHistorySuccessResponse,
    PlanComparisonSuccessResponse,
    RetryPaymentRequest,
    RetryPaymentSuccessResponse,
    SubscriptionHistoryItem,
    SubscriptionHistorySuccessResponse,
    SubscriptionStatusSuccessResponse,
    VerifyPaymentData,
    VerifyPaymentRequest,
    VerifyPaymentSuccessResponse,
)
from app.modules.billing.utils import (
    BillingAccessDeniedError,
    BillingUserNotFoundError,
    build_plan_comparison,
    fetch_active_plans,
    fetch_invoices,
    fetch_payment_history,
    fetch_subscription_history,
    resolve_billing_target_user,
    resolve_user_plan_with_master,
    serialize_billing_plan,
    serialize_current_plan,
    serialize_invoice,
    serialize_payment_transaction,
    serialize_subscription_history,
)
from app.modules.user_plan.utils import get_plan_display_name

logger = logging.getLogger(__name__)

__all__ = [
    "BillingAccessDeniedError",
    "BillingUserNotFoundError",
    "BillingValidationError",
    "RazorpayServiceError",
    "get_all_plans",
    "get_plans",
    "get_current_plan",
    "prepare_checkout",
    "create_order",
    "create_subscription_order",
    "verify_payment",
    "disable_user_auto_renew",
    "enable_user_auto_renew",
    "cancel_user_subscription",
    "retry_user_payment",
    "get_subscription_status",
    "get_payment_detail",
    "get_plan_comparison",
    "get_payment_history",
    "get_subscription_history",
    "get_invoices",
]


def get_all_plans(
    db: Session,
    actor: User | None = None,
) -> BillingPlansSuccessResponse:
    """Return all active plans; mark current / recommended / upgrade flags when actor provided."""
    return get_plans(db, actor)


def get_plans(
    db: Session,
    actor: User | None = None,
) -> BillingPlansSuccessResponse:
    """Reusable plans catalog for pricing page."""
    plans = fetch_active_plans(db)
    current_plan = None
    if actor is not None:
        _, current_plan = resolve_user_plan_with_master(db, actor.id)

    data: list[BillingPlanData] = [
        serialize_billing_plan(plan, current_plan=current_plan) for plan in plans
    ]
    logger.info("Listed %s active billing plan(s)", len(data))
    return BillingPlansSuccessResponse(data=data)


def get_current_plan(
    db: Session,
    actor: User,
    *,
    user_id: int | None = None,
) -> CurrentPlanSuccessResponse:
    """Return the actor's (or permitted target user's) current subscription."""
    target = resolve_billing_target_user(db, actor, user_id)
    user_plan, plan = resolve_user_plan_with_master(db, target.id)
    data: CurrentPlanData = serialize_current_plan(
        user=target,
        user_plan=user_plan,
        plan=plan,
    )
    logger.info(
        "Billing current-plan fetched actor_id=%s target_user_id=%s plan=%s",
        actor.id,
        target.id,
        data.plan_name,
    )
    return CurrentPlanSuccessResponse(data=data)


def prepare_checkout(
    db: Session,
    actor: User,
    payload: CheckoutRequest,
) -> CheckoutSuccessResponse:
    """
    Validate plan selection and return a checkout preview.

    Does not create a Razorpay order or mutate subscription state.
    """
    billing_cycle = normalize_billing_cycle(payload.billing_cycle)
    target_plan = resolve_active_plan_or_raise(db, payload.plan_id)
    _, current_plan = resolve_user_plan_with_master(db, actor.id)

    action = validate_plan_change(current_plan, target_plan)
    if action not in {"upgrade", "downgrade", "switch"}:
        raise BillingValidationError(messages.BILLING_ALREADY_ON_PLAN)

    amounts = build_checkout_amounts(target_plan, billing_cycle)
    checkout_action: Literal["upgrade", "downgrade", "switch"] = action  # type: ignore[assignment]

    checkout = CheckoutData(
        plan_id=target_plan.id,
        plan_name=target_plan.plan_name,
        display_name=get_plan_display_name(target_plan.plan_name),
        billing_cycle=billing_cycle,
        action=checkout_action,
        price=money_to_float(amounts.price),
        currency=amounts.currency,
        subtotal=money_to_float(amounts.subtotal),
        discount=money_to_float(amounts.discount),
        discount_percentage=money_to_float(amounts.discount_percentage),
        saving=money_to_float(amounts.saving),
        list_price=money_to_float(amounts.list_price),
        gst_percentage=money_to_float(amounts.gst_percentage),
        gst_amount=money_to_float(amounts.gst_amount),
        total_amount=money_to_float(amounts.total_amount),
        chatbot_limit=target_plan.max_chatbots,
        website_message_limit=target_plan.chatbot_message_limit,
        playground_message_limit=target_plan.playground_message_limit,
        features=serialize_billing_plan(target_plan, current_plan=current_plan).features,
    )

    logger.info(
        "Checkout preview prepared user_id=%s plan_id=%s cycle=%s action=%s total=%s",
        actor.id,
        target_plan.id,
        billing_cycle,
        checkout_action,
        checkout.total_amount,
    )
    return CheckoutSuccessResponse(
        message=messages.BILLING_CHECKOUT_PREPARED_SUCCESS,
        checkout=checkout,
    )


def create_order(
    db: Session,
    actor: User,
    payload: CreateOrderRequest,
) -> CreateOrderSuccessResponse:
    """
    Validate plan selection, create a Razorpay order, and store a pending transaction.

    Does not verify payment or activate the user's plan.
    """
    result = create_pending_razorpay_order(
        db,
        actor,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
    )
    action: Literal["upgrade", "downgrade", "switch"] = result["action"]
    data = CreateOrderData(
        order_id=result["order_id"],
        key=result["key"],
        amount=result["amount"],
        currency=result["currency"],
        plan_id=result["plan_id"],
        plan_name=result["plan_name"],
        display_name=result["display_name"],
        billing_cycle=result["billing_cycle"],
        action=action,
        subtotal=result["subtotal"],
        discount=result["discount"],
        gst_percentage=result["gst_percentage"],
        gst_amount=result["gst_amount"],
        total_amount=result["total_amount"],
    )
    logger.info(
        "Razorpay order created user_id=%s plan_id=%s cycle=%s order_id=%s amount_paise=%s",
        actor.id,
        result["plan_id"],
        result["billing_cycle"],
        result["order_id"],
        result["amount"],
    )
    return CreateOrderSuccessResponse(
        message=messages.BILLING_ORDER_CREATED_SUCCESS,
        order_id=data.order_id,
        key=data.key,
        amount=data.amount,
        currency=data.currency,
        plan_name=data.plan_name,
        billing_cycle=data.billing_cycle,
        data=data,
    )


def verify_payment(
    db: Session,
    actor: User,
    payload: VerifyPaymentRequest,
) -> VerifyPaymentSuccessResponse:
    """
    Verify Razorpay signature (order or subscription), activate plan, reset usage.

    Idempotent for already-verified payments. Does not trust frontend amounts.
    """
    result = verify_and_activate_payment(
        db,
        actor,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
        razorpay_subscription_id=payload.razorpay_subscription_id,
    )
    payment = result["payment"]
    plan = result["plan"]
    user_plan = result["user_plan"]
    already = bool(result.get("already_verified"))

    plan_name = plan.plan_name if plan is not None else user_plan.plan_name
    subscription_end = user_plan.subscription_end or user_plan.end_date
    data = VerifyPaymentData(
        payment_id=payment.id,
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        gateway_subscription_id=getattr(payment, "gateway_subscription_id", None),
        status=payment.status,
        plan_id=payment.plan_id,
        plan_name=plan_name,
        display_name=get_plan_display_name(plan_name),
        billing_cycle=payment.billing_cycle,
        action=result.get("action"),
        amount=money_to_float(payment.amount),
        currency=payment.currency,
        payment_method=payment.payment_method,
        payment_type=getattr(payment, "payment_type", None),
        subscription_status=user_plan.subscription_status,
        subscription_start=user_plan.subscription_start or user_plan.start_date,
        subscription_end=subscription_end,
        next_billing_date=user_plan.next_billing_date,
        remaining_days=remaining_subscription_days(subscription_end),
        is_auto_renew=bool(user_plan.is_auto_renew),
        already_verified=already,
    )
    message = (
        messages.BILLING_PAYMENT_ALREADY_VERIFIED
        if already
        else messages.BILLING_PAYMENT_VERIFIED_SUCCESS
    )
    return VerifyPaymentSuccessResponse(message=message, data=data)


def create_subscription_order(
    db: Session,
    actor: User,
    payload: CreateSubscriptionRequest,
) -> CreateSubscriptionSuccessResponse:
    """Create a Razorpay subscription for AutoPay checkout."""
    from app.modules.billing.schema import CreateSubscriptionData
    from app.modules.billing.subscription import create_subscription

    result = create_subscription(
        db,
        actor,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
        auto_renew=payload.auto_renew,
    )
    action: Literal["upgrade", "downgrade", "switch"] = result["action"]
    data = CreateSubscriptionData(
        subscription_id=result["subscription_id"],
        key=result["key"],
        customer_id=result.get("customer_id"),
        plan_id=result["plan_id"],
        plan_name=result["plan_name"],
        display_name=result["display_name"],
        billing_cycle=result["billing_cycle"],
        action=action,
        currency=result["currency"],
        amount=result["amount"],
        total_amount=result["total_amount"],
        subtotal=result["subtotal"],
        discount=result["discount"],
        gst_percentage=result["gst_percentage"],
        gst_amount=result["gst_amount"],
        auto_renew=True,
    )
    return CreateSubscriptionSuccessResponse(
        message=messages.BILLING_SUBSCRIPTION_CREATED_SUCCESS,
        subscription_id=data.subscription_id,
        key=data.key,
        data=data,
    )


def disable_user_auto_renew(
    db: Session,
    actor: User,
    payload: AutoRenewRequest,
) -> AutoRenewSuccessResponse:
    """Disable AutoPay at cycle end without ending the current period early."""
    from app.modules.billing.schema import AutoRenewData
    from app.modules.billing.subscription import disable_auto_renew

    result = disable_auto_renew(
        db,
        actor,
        subscription_id=payload.subscription_id,
    )
    data = AutoRenewData(
        subscription_id=result.get("subscription_id"),
        is_auto_renew=False,
        requires_checkout=False,
        mode="disabled",
        subscription_end=result.get("subscription_end"),
        next_billing_date=result.get("next_billing_date"),
    )
    return AutoRenewSuccessResponse(
        message=result.get("message") or messages.BILLING_AUTO_RENEW_DISABLED_SUCCESS,
        data=data,
    )


def enable_user_auto_renew(
    db: Session,
    actor: User,
) -> AutoRenewSuccessResponse:
    """Resume AutoPay or create a new subscription requiring checkout."""
    from app.modules.billing.schema import AutoRenewData
    from app.modules.billing.subscription import enable_auto_renew

    result = enable_auto_renew(db, actor)
    data = AutoRenewData(
        subscription_id=result.get("subscription_id"),
        is_auto_renew=bool(result.get("is_auto_renew", result.get("mode") == "resumed")),
        requires_checkout=bool(result.get("requires_checkout")),
        mode=result.get("mode"),
        key=result.get("key"),
        plan_id=result.get("plan_id"),
        plan_name=result.get("plan_name"),
        display_name=result.get("display_name"),
        billing_cycle=result.get("billing_cycle"),
        amount=result.get("amount"),
        currency=result.get("currency"),
        customer_id=result.get("customer_id"),
        total_amount=result.get("total_amount"),
    )
    return AutoRenewSuccessResponse(
        message=messages.BILLING_AUTO_RENEW_ENABLED_SUCCESS,
        data=data,
    )


def cancel_user_subscription(
    db: Session,
    actor: User,
    payload: CancelSubscriptionRequest,
) -> CancelSubscriptionSuccessResponse:
    """Cancel Auto Renew at cycle end; keep current plan until subscription_end."""
    from app.modules.billing.lifecycle import cancel_subscription
    from app.modules.billing.schema import CancelSubscriptionData

    result = cancel_subscription(
        db,
        actor,
        subscription_id=payload.subscription_id,
    )
    data = CancelSubscriptionData(
        subscription_id=result.get("subscription_id"),
        is_auto_renew=False,
        subscription_status=result.get("subscription_status") or "active",
        subscription_end=result.get("subscription_end"),
        next_billing_date=result.get("next_billing_date"),
        remaining_days=result.get("remaining_days"),
    )
    return CancelSubscriptionSuccessResponse(
        message=result.get("message") or messages.BILLING_SUBSCRIPTION_CANCELLED_SUCCESS,
        data=data,
    )


def retry_user_payment(
    db: Session,
    actor: User,
    payload: RetryPaymentRequest,
) -> RetryPaymentSuccessResponse:
    """Create a new Razorpay order for a failed payment_transaction."""
    from app.modules.billing.lifecycle import retry_payment

    result = retry_payment(
        db,
        actor,
        payment_transaction_id=payload.payment_transaction_id,
    )
    action: Literal["upgrade", "downgrade", "switch"] = "switch"
    data = CreateOrderData(
        order_id=result["order_id"],
        key=result["key"],
        amount=result["amount"],
        currency=result["currency"],
        plan_id=result["plan_id"],
        plan_name=result["plan_name"],
        display_name=result["display_name"],
        billing_cycle=result["billing_cycle"],
        action=action,
        subtotal=result["subtotal"],
        discount=result["discount"],
        gst_percentage=result["gst_percentage"],
        gst_amount=result["gst_amount"],
        total_amount=result["total_amount"],
    )
    return RetryPaymentSuccessResponse(
        message=messages.BILLING_PAYMENT_RETRY_SUCCESS,
        order_id=data.order_id,
        key=data.key,
        amount=data.amount,
        currency=data.currency,
        plan_name=data.plan_name,
        billing_cycle=data.billing_cycle,
        data=data,
    )


def get_subscription_status(
    db: Session,
    actor: User,
) -> SubscriptionStatusSuccessResponse:
    """Return current subscription status flags for the billing UI."""
    from app.modules.billing.lifecycle import build_subscription_status
    from app.modules.billing.schema import SubscriptionStatusData

    result = build_subscription_status(db, actor)
    data = SubscriptionStatusData(**result)
    return SubscriptionStatusSuccessResponse(
        message=messages.BILLING_SUBSCRIPTION_STATUS_RETRIEVED_SUCCESS,
        data=data,
    )


def get_payment_detail(
    db: Session,
    actor: User,
    payment_id: int,
    *,
    user_id: int | None = None,
) -> PaymentDetailSuccessResponse:
    """Return a single payment_transaction the actor is allowed to view."""
    from sqlalchemy.orm import joinedload

    from app.modules.billing.model import PaymentTransaction

    target = resolve_billing_target_user(db, actor, user_id)
    payment = (
        db.execute(
            select(PaymentTransaction)
            .options(joinedload(PaymentTransaction.plan))
            .where(PaymentTransaction.id == payment_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if payment is None or payment.user_id != target.id:
        raise BillingUserNotFoundError(messages.BILLING_PAYMENT_NOT_FOUND)

    return PaymentDetailSuccessResponse(
        message=messages.BILLING_PAYMENT_DETAIL_RETRIEVED_SUCCESS,
        data=serialize_payment_transaction(payment),
    )


def get_plan_comparison(
    db: Session,
    actor: User,
) -> PlanComparisonSuccessResponse:
    """Return feature comparison matrix for active plans."""
    plans = fetch_active_plans(db)
    _, current_plan = resolve_user_plan_with_master(db, actor.id)
    data = build_plan_comparison(plans, current_plan=current_plan)
    logger.info(
        "Plan comparison built user_id=%s plans=%s rows=%s",
        actor.id,
        len(data.plans),
        len(data.rows),
    )
    return PlanComparisonSuccessResponse(data=data)


def get_payment_history(
    db: Session,
    actor: User,
    *,
    user_id: int | None = None,
) -> PaymentHistorySuccessResponse:
    """Return payment history newest first (empty until Razorpay integration)."""
    target = resolve_billing_target_user(db, actor, user_id)
    rows = fetch_payment_history(db, target.id)
    data: list[PaymentHistoryItem] = [
        serialize_payment_transaction(row) for row in rows
    ]
    logger.info(
        "Billing payment-history fetched actor_id=%s target_user_id=%s count=%s",
        actor.id,
        target.id,
        len(data),
    )
    return PaymentHistorySuccessResponse(data=data)


def get_subscription_history(
    db: Session,
    actor: User,
    *,
    user_id: int | None = None,
) -> SubscriptionHistorySuccessResponse:
    """Return purchase/upgrade/downgrade/renew/cancel/expire history."""
    target = resolve_billing_target_user(db, actor, user_id)
    rows = fetch_subscription_history(db, target.id)
    data: list[SubscriptionHistoryItem] = [
        serialize_subscription_history(row) for row in rows
    ]
    logger.info(
        "Billing subscription-history fetched actor_id=%s target_user_id=%s count=%s",
        actor.id,
        target.id,
        len(data),
    )
    return SubscriptionHistorySuccessResponse(data=data)


def get_invoices(
    db: Session,
    actor: User,
    *,
    user_id: int | None = None,
) -> InvoicesSuccessResponse:
    """Return invoice records newest first."""
    target = resolve_billing_target_user(db, actor, user_id)
    rows = fetch_invoices(db, target.id)
    data: list[InvoiceItem] = [
        serialize_invoice(row) for row in rows
    ]
    logger.info(
        "Billing invoices fetched actor_id=%s target_user_id=%s count=%s",
        actor.id,
        target.id,
        len(data),
    )
    return InvoicesSuccessResponse(
        message=messages.BILLING_INVOICES_RETRIEVED_SUCCESS,
        data=data,
    )


def get_invoice_detail(
    db: Session,
    actor: User,
    invoice_id: int,
    *,
    user_id: int | None = None,
) -> InvoiceDetailSuccessResponse:
    """Return a single invoice the actor may view."""
    from app.modules.billing.invoice_service import get_invoice_for_actor
    from app.modules.billing.schema import InvoiceDetailSuccessResponse

    invoice = get_invoice_for_actor(db, actor, invoice_id, user_id=user_id)
    return InvoiceDetailSuccessResponse(
        message=messages.BILLING_INVOICE_DETAIL_RETRIEVED_SUCCESS,
        data=serialize_invoice(invoice),
    )


def resend_invoice_email(
    db: Session,
    actor: User,
    payload: ResendInvoiceRequest,
) -> ResendInvoiceSuccessResponse:
    """Resend invoice PDF email to the bill-to address."""
    from app.modules.billing.invoice_service import (
        get_invoice_for_actor,
        send_invoice_email,
    )
    from app.modules.billing.schema import ResendInvoiceSuccessResponse

    invoice = get_invoice_for_actor(db, actor, payload.invoice_id)
    try:
        send_invoice_email(invoice)
    except BillingValidationError:
        raise
    except Exception as exc:
        logger.exception("Resend invoice failed invoice_id=%s", invoice.id)
        raise BillingValidationError(messages.BILLING_INVOICE_EMAIL_FAILED) from exc

    return ResendInvoiceSuccessResponse(
        message=messages.BILLING_INVOICE_RESENT_SUCCESS,
        data=serialize_invoice(invoice),
    )


def resolve_invoice_pdf_path(
    db: Session,
    actor: User,
    invoice_id: int,
    *,
    user_id: int | None = None,
):
    """Return filesystem path for invoice download."""
    from app.modules.billing.invoice_service import (
        download_invoice,
        get_invoice_for_actor,
    )

    invoice = get_invoice_for_actor(db, actor, invoice_id, user_id=user_id)
    path = download_invoice(invoice)
    if invoice.pdf_path and invoice.pdf_path != str(path):
        # Persist regenerated path if download regenerated the PDF.
        db.add(invoice)
        db.commit()
    return path, invoice

