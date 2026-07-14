"""Payment verification, plan activation, usage reset, and subscription history."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.billing.checkout import (
    BillingValidationError,
    classify_plan_change,
)
from app.modules.billing.model import (
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_SIX_MONTH,
    BILLING_CYCLE_YEARLY,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_SUCCESS,
    PaymentTransaction,
    SUBSCRIPTION_ACTION_DOWNGRADE,
    SUBSCRIPTION_ACTION_PURCHASE,
    SUBSCRIPTION_ACTION_UPGRADE,
    SubscriptionHistory,
)
from app.modules.billing.razorpay_service import get_razorpay_service
from app.modules.chatbot_usage.model import ChatbotUsage
from app.modules.plan_master.model import PLAN_NAME_FREE, PlanMaster
from app.modules.plan_master.utils import get_plan_by_id
from app.modules.user_plan.model import (
    PLAN_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_ACTIVE,
    UserPlan,
)
from app.modules.user_plan.utils import ensure_user_plan_exists

logger = logging.getLogger(__name__)

_CYCLE_MONTHS = {
    BILLING_CYCLE_MONTHLY: 1,
    BILLING_CYCLE_SIX_MONTH: 6,
    BILLING_CYCLE_YEARLY: 12,
}


def calculate_subscription_end_date(
    start: datetime,
    billing_cycle: str,
) -> datetime:
    """
    Compute subscription end from billing cycle.

    monthly → +1 month, six_month → +6 months, yearly → +12 months
    """
    months = _CYCLE_MONTHS.get((billing_cycle or "").strip().lower())
    if months is None:
        raise BillingValidationError(messages.BILLING_CYCLE_INVALID)
    return start + relativedelta(months=months)


def resolve_subscription_history_action(
    current_plan: PlanMaster | None,
    target_plan: PlanMaster,
) -> str:
    """
    Map plan change to subscription_history.action.

    Free / no plan → purchase; otherwise upgrade / downgrade / purchase.
    """
    if current_plan is None or current_plan.plan_name.strip().lower() == PLAN_NAME_FREE:
        return SUBSCRIPTION_ACTION_PURCHASE

    change = classify_plan_change(current_plan, target_plan)
    if change == "upgrade":
        return SUBSCRIPTION_ACTION_UPGRADE
    if change == "downgrade":
        return SUBSCRIPTION_ACTION_DOWNGRADE
    return SUBSCRIPTION_ACTION_PURCHASE


def get_payment_transaction_by_order_id(
    db: Session,
    *,
    user_id: int,
    gateway_order_id: str,
) -> PaymentTransaction | None:
    """Load the user's payment_transaction for a Razorpay order id."""
    return db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.user_id == user_id,
            PaymentTransaction.gateway_order_id == gateway_order_id,
        )
    ).scalar_one_or_none()


def get_payment_transaction_by_id(
    db: Session,
    *,
    payment_id: int,
) -> PaymentTransaction | None:
    """Load a payment_transaction by primary key."""
    return db.execute(
        select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
    ).scalar_one_or_none()


def verify_payment_signature(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> None:
    """Verify Razorpay signature; raises on failure without mutating DB."""
    get_razorpay_service().verify_payment_signature(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    )


def mark_payment_success(
    payment: PaymentTransaction,
    *,
    gateway_payment_id: str,
    gateway_signature: str,
    payment_method: str | None,
    transaction_date: datetime | None = None,
) -> PaymentTransaction:
    """Update a pending payment_transaction to success."""
    now = transaction_date or datetime.now(timezone.utc)
    payment.status = PAYMENT_STATUS_SUCCESS
    payment.gateway_payment_id = gateway_payment_id
    payment.gateway_signature = gateway_signature
    if payment_method:
        payment.payment_method = payment_method[:50]
    payment.transaction_date = now
    payment.updated_at = now
    return payment


def update_user_plan(
    user_plan: UserPlan,
    *,
    plan: PlanMaster,
    billing_cycle: str,
    amount: Decimal,
    subscription_start: datetime,
    subscription_end: datetime,
    is_auto_renew: bool = False,
    razorpay_subscription_id: str | None = None,
    razorpay_customer_id: str | None = None,
) -> UserPlan:
    """Apply purchased plan_master limits and billing dates onto user_plan."""
    user_plan.plan_id = plan.id
    user_plan.plan_name = plan.plan_name
    user_plan.chatbot_limit = plan.max_chatbots
    user_plan.status = PLAN_STATUS_ACTIVE
    user_plan.subscription_status = SUBSCRIPTION_STATUS_ACTIVE
    user_plan.billing_cycle = billing_cycle
    user_plan.subscription_start = subscription_start
    user_plan.subscription_end = subscription_end
    user_plan.start_date = subscription_start
    user_plan.end_date = subscription_end
    user_plan.next_billing_date = subscription_end
    user_plan.current_billing = amount
    user_plan.is_auto_renew = bool(is_auto_renew)
    if razorpay_subscription_id is not None:
        user_plan.razorpay_subscription_id = razorpay_subscription_id
    if razorpay_customer_id is not None:
        user_plan.razorpay_customer_id = razorpay_customer_id
    if not is_auto_renew:
        # One-time purchases clear residual AutoPay ids.
        user_plan.razorpay_subscription_id = None
    user_plan.updated_at = datetime.now(timezone.utc)
    return user_plan


def activate_plan(
    db: Session,
    *,
    user_id: int,
    plan: PlanMaster,
    billing_cycle: str,
    amount: Decimal,
    subscription_start: datetime | None = None,
    is_auto_renew: bool = False,
    razorpay_subscription_id: str | None = None,
    razorpay_customer_id: str | None = None,
) -> tuple[UserPlan, datetime, datetime]:
    """
    Activate purchased plan on user_plan.

    Returns (user_plan, subscription_start, subscription_end).
    """
    start = subscription_start or datetime.now(timezone.utc)
    end = calculate_subscription_end_date(start, billing_cycle)
    user_plan = ensure_user_plan_exists(db, user_id)
    update_user_plan(
        user_plan,
        plan=plan,
        billing_cycle=billing_cycle,
        amount=amount,
        subscription_start=start,
        subscription_end=end,
        is_auto_renew=is_auto_renew,
        razorpay_subscription_id=razorpay_subscription_id,
        razorpay_customer_id=razorpay_customer_id,
    )
    db.flush()
    return user_plan, start, end


def create_subscription_history(
    db: Session,
    *,
    user_id: int,
    old_plan_id: int | None,
    new_plan_id: int | None,
    action: str,
    payment_transaction_id: int | None = None,
    changed_by: int | None = None,
    changed_at: datetime | None = None,
) -> SubscriptionHistory:
    """Insert a subscription_history audit row."""
    now = changed_at or datetime.now(timezone.utc)
    row = SubscriptionHistory(
        user_id=user_id,
        old_plan_id=old_plan_id,
        new_plan_id=new_plan_id,
        action=action,
        payment_transaction_id=payment_transaction_id,
        changed_by=changed_by,
        changed_at=now,
    )
    db.add(row)
    db.flush()
    return row


def reset_usage(db: Session, user_id: int) -> int:
    """
    Reset chatbot_usage counters for all of the user's chatbots.

    Does not delete analytics or chat history.
    """
    now = datetime.now(timezone.utc)
    rows = list(
        db.scalars(
            select(ChatbotUsage).where(ChatbotUsage.user_id == user_id)
        ).all()
    )
    for usage in rows:
        usage.website_messages_used = 0
        usage.playground_messages_used = 0
        usage.website_tokens_used = 0
        usage.playground_tokens_used = 0
        usage.website_last_reset_at = now
        usage.playground_last_reset_at = now
        usage.updated_at = now
    if rows:
        db.flush()
    logger.info("Reset chatbot_usage for user_id=%s rows=%s", user_id, len(rows))
    return len(rows)


def _extract_payment_method(payment_payload: dict | None) -> str | None:
    if not payment_payload:
        return None
    method = payment_payload.get("method")
    if method:
        return str(method)
    return None


def verify_and_activate_payment(
    db: Session,
    actor: User,
    *,
    razorpay_order_id: str | None = None,
    razorpay_payment_id: str,
    razorpay_signature: str,
    razorpay_subscription_id: str | None = None,
) -> dict:
    """
    Full verify-payment orchestration for one-time or subscription checkouts.

    Subscription path is delegated when razorpay_subscription_id is present.
    """
    subscription_id = (razorpay_subscription_id or "").strip()
    if subscription_id:
        from app.modules.billing.subscription import verify_subscription

        return verify_subscription(
            db,
            actor,
            razorpay_subscription_id=subscription_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

    order_id = (razorpay_order_id or "").strip()
    payment_id = (razorpay_payment_id or "").strip()
    signature = (razorpay_signature or "").strip()

    if not order_id or not payment_id or not signature:
        raise BillingValidationError(messages.BILLING_PAYMENT_VERIFICATION_FAILED)

    payment = get_payment_transaction_by_order_id(
        db,
        user_id=actor.id,
        gateway_order_id=order_id,
    )
    if payment is None:
        raise BillingValidationError(messages.BILLING_PAYMENT_ORDER_INVALID)

    # Idempotent: already verified for this payment.
    if payment.status == PAYMENT_STATUS_SUCCESS:
        if (
            payment.gateway_payment_id
            and payment.gateway_payment_id == payment_id
        ):
            plan = get_plan_by_id(db, payment.plan_id)
            user_plan = ensure_user_plan_exists(db, actor.id)
            return {
                "already_verified": True,
                "payment": payment,
                "plan": plan,
                "user_plan": user_plan,
                "action": None,
            }
        raise BillingValidationError(messages.BILLING_PAYMENT_ALREADY_VERIFIED)

    if payment.status != PAYMENT_STATUS_PENDING:
        raise BillingValidationError(messages.BILLING_PAYMENT_NOT_PENDING)

    # Signature first — no DB mutations on failure.
    verify_payment_signature(
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=signature,
    )

    target_plan = get_plan_by_id(db, payment.plan_id)
    if target_plan is None or not target_plan.is_active:
        raise BillingValidationError(messages.BILLING_PLAN_NOT_FOUND)

    user_plan = ensure_user_plan_exists(db, actor.id)
    old_plan_id = user_plan.plan_id
    current_plan = get_plan_by_id(db, old_plan_id) if old_plan_id else None
    history_action = resolve_subscription_history_action(current_plan, target_plan)

    razorpay = get_razorpay_service()
    gateway_payment = razorpay.fetch_payment(payment_id)
    payment_method = _extract_payment_method(gateway_payment)

    now = datetime.now(timezone.utc)
    try:
        mark_payment_success(
            payment,
            gateway_payment_id=payment_id,
            gateway_signature=signature,
            payment_method=payment_method,
            transaction_date=now,
        )
        user_plan, start, end = activate_plan(
            db,
            user_id=actor.id,
            plan=target_plan,
            billing_cycle=payment.billing_cycle,
            amount=payment.amount,
            subscription_start=now,
        )
        create_subscription_history(
            db,
            user_id=actor.id,
            old_plan_id=old_plan_id,
            new_plan_id=target_plan.id,
            action=history_action,
            payment_transaction_id=payment.id,
            changed_by=actor.id,
            changed_at=now,
        )
        reset_usage(db, actor.id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        from app.modules.billing.invoice_service import issue_invoice_after_payment

        issue_invoice_after_payment(
            db,
            user=actor,
            payment=payment,
            plan=target_plan,
        )
    except Exception:
        logger.exception(
            "Post-payment invoice pipeline failed payment_id=%s",
            payment.id,
        )

    logger.info(
        "Payment verified user_id=%s payment_id=%s plan=%s action=%s",
        actor.id,
        payment.id,
        target_plan.plan_name,
        history_action,
    )
    return {
        "already_verified": False,
        "payment": payment,
        "plan": target_plan,
        "user_plan": user_plan,
        "action": history_action,
        "subscription_start": start,
        "subscription_end": end,
    }


def remaining_subscription_days(subscription_end: datetime | None) -> int | None:
    """Days remaining until subscription_end (0 if expired)."""
    if subscription_end is None:
        return None
    end = subscription_end
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = end - now
    return max(delta.days, 0)
