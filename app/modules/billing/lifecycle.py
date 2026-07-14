"""Subscription lifecycle: cancel, retry failed payments, and expiry downgrade."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.core.config import get_settings
from app.modules.auth.model import User
from app.modules.billing.activation import (
    create_subscription_history,
    remaining_subscription_days,
    reset_usage,
)
from app.modules.billing.checkout import (
    BillingValidationError,
    normalize_billing_cycle,
    resolve_active_plan_or_raise,
)
from app.modules.billing.model import (
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_SUCCESS,
    PAYMENT_TYPE_RETRY,
    SUBSCRIPTION_ACTION_CANCEL,
    SUBSCRIPTION_ACTION_EXPIRE,
    PaymentTransaction,
)
from app.modules.billing.order import (
    calculate_order_amount,
    create_payment_transaction,
    create_razorpay_order,
    rupees_to_paise,
)
from app.modules.billing.razorpay_service import get_razorpay_service
from app.modules.plan_master.model import PLAN_NAME_FREE, PlanMaster
from app.modules.plan_master.utils import get_default_plan, get_plan_by_id, get_plan_by_name
from app.modules.user_plan.model import (
    PLAN_STATUS_ACTIVE,
    PLAN_STATUS_EXPIRED,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_EXPIRED,
    UserPlan,
)
from app.modules.user_plan.utils import ensure_user_plan_exists, get_plan_display_name

logger = logging.getLogger(__name__)


def cancel_subscription(
    db: Session,
    actor: User,
    *,
    subscription_id: str | None = None,
) -> dict[str, Any]:
    """
    Cancel Auto Renew at cycle end.

    Never immediately downgrades the plan. plan_id and subscription_end stay intact.
    """
    user_plan = ensure_user_plan_exists(db, actor.id)
    sub_id = (subscription_id or user_plan.razorpay_subscription_id or "").strip()
    if not sub_id:
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_REQUIRED)

    if (
        user_plan.razorpay_subscription_id
        and user_plan.razorpay_subscription_id != sub_id
    ):
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_INVALID)

    if not user_plan.is_auto_renew:
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_CANCELLED)

    status = (user_plan.subscription_status or "").strip().lower()
    if status and status not in {SUBSCRIPTION_STATUS_ACTIVE, "active"}:
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_INVALID)

    razorpay = get_razorpay_service()
    try:
        razorpay.cancel_subscription(sub_id, cancel_at_cycle_end=True)
    except BillingValidationError:
        logger.warning(
            "Gateway cancel failed for sub_id=%s; updating local Auto Renew flag",
            sub_id,
        )

    user_plan.is_auto_renew = False
    user_plan.subscription_status = SUBSCRIPTION_STATUS_ACTIVE
    user_plan.updated_at = datetime.now(timezone.utc)

    create_subscription_history(
        db,
        user_id=actor.id,
        old_plan_id=user_plan.plan_id,
        new_plan_id=user_plan.plan_id,
        action=SUBSCRIPTION_ACTION_CANCEL,
        payment_transaction_id=None,
        changed_by=actor.id,
    )
    db.commit()

    subscription_end = user_plan.subscription_end or user_plan.end_date
    return {
        "subscription_id": sub_id,
        "is_auto_renew": False,
        "subscription_status": user_plan.subscription_status,
        "subscription_end": subscription_end,
        "next_billing_date": user_plan.next_billing_date,
        "remaining_days": remaining_subscription_days(subscription_end),
        "message": messages.BILLING_SUBSCRIPTION_CANCELLED_SUCCESS,
    }


def retry_payment(
    db: Session,
    actor: User,
    *,
    payment_transaction_id: int,
) -> dict[str, Any]:
    """
    Retry a failed one-time/retry payment by creating a new Razorpay order.

    Only failed payments may be retried. Reuses plan_id + billing_cycle.
    """
    payment = db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.id == payment_transaction_id,
            PaymentTransaction.user_id == actor.id,
        )
    ).scalar_one_or_none()

    if payment is None:
        raise BillingValidationError(messages.BILLING_PAYMENT_NOT_FOUND)

    if payment.status == PAYMENT_STATUS_SUCCESS:
        raise BillingValidationError(messages.BILLING_PAYMENT_ALREADY_SUCCESSFUL)

    if payment.status == PAYMENT_STATUS_PENDING:
        raise BillingValidationError(messages.BILLING_PAYMENT_RETRY_PENDING)

    if payment.status != PAYMENT_STATUS_FAILED:
        raise BillingValidationError(messages.BILLING_PAYMENT_RETRY_INVALID)

    target_plan = resolve_active_plan_or_raise(db, payment.plan_id)
    if target_plan.plan_name.strip().lower() == PLAN_NAME_FREE:
        raise BillingValidationError(messages.BILLING_CHECKOUT_FREE_PLAN)

    cycle = normalize_billing_cycle(payment.billing_cycle)
    amounts = calculate_order_amount(target_plan, cycle)
    settings = get_settings()
    amount_paise = rupees_to_paise(amounts.total_amount)
    currency = (amounts.currency or settings.RAZORPAY_CURRENCY or "INR").upper()
    receipt = f"retry{payment.id}_u{actor.id}"[:40]
    notes = {
        "user_id": str(actor.id),
        "plan_id": str(target_plan.id),
        "plan_name": target_plan.plan_name,
        "billing_cycle": cycle,
        "action": "retry",
        "retry_of_payment_id": str(payment.id),
        "display_name": get_plan_display_name(target_plan.plan_name),
    }

    razorpay = get_razorpay_service()
    try:
        order = create_razorpay_order(
            amount_paise=amount_paise,
            currency=currency,
            receipt=receipt,
            notes=notes,
            razorpay=razorpay,
        )
        gateway_order_id = str(order["id"])
        create_payment_transaction(
            db,
            user_id=actor.id,
            plan_id=target_plan.id,
            billing_cycle=cycle,
            amount=amounts.total_amount,
            currency=currency,
            gateway_order_id=gateway_order_id,
            payment_type=PAYMENT_TYPE_RETRY,
            retry_of_payment_id=payment.id,
            status=PAYMENT_STATUS_PENDING,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "order_id": gateway_order_id,
        "key": razorpay.key_id,
        "amount": amount_paise,
        "currency": currency,
        "plan_id": target_plan.id,
        "plan_name": target_plan.plan_name,
        "display_name": get_plan_display_name(target_plan.plan_name),
        "billing_cycle": cycle,
        "action": "switch",
        "subtotal": float(amounts.subtotal),
        "discount": float(amounts.discount),
        "gst_percentage": float(amounts.gst_percentage),
        "gst_amount": float(amounts.gst_amount),
        "total_amount": float(amounts.total_amount),
        "retry_of_payment_id": payment.id,
        "payment_type": PAYMENT_TYPE_RETRY,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def downgrade_to_free(
    db: Session,
    *,
    user_id: int,
    changed_by: int | None = None,
    commit: bool = True,
) -> UserPlan:
    """
    Assign the Free plan after paid period expiry.

    Clears AutoPay ids, resets usage counters, writes expire history.
    """
    user_plan = ensure_user_plan_exists(db, user_id)
    try:
        free_plan = get_default_plan(db)
    except Exception:
        free_plan = get_plan_by_name(db, PLAN_NAME_FREE)
    if free_plan is None:
        raise BillingValidationError(messages.BILLING_PLAN_NOT_FOUND)

    if (
        user_plan.plan_id == free_plan.id
        or (user_plan.plan_name or "").strip().lower() == PLAN_NAME_FREE
    ):
        return user_plan

    old_plan_id = user_plan.plan_id
    now = datetime.now(timezone.utc)

    user_plan.plan_id = free_plan.id
    user_plan.plan_name = free_plan.plan_name
    user_plan.chatbot_limit = free_plan.max_chatbots
    user_plan.status = PLAN_STATUS_EXPIRED
    user_plan.subscription_status = SUBSCRIPTION_STATUS_EXPIRED
    user_plan.billing_cycle = None
    user_plan.current_billing = Decimal("0.00")
    user_plan.is_auto_renew = False
    user_plan.razorpay_subscription_id = None
    user_plan.next_billing_date = None
    user_plan.updated_at = now

    create_subscription_history(
        db,
        user_id=user_id,
        old_plan_id=old_plan_id,
        new_plan_id=free_plan.id,
        action=SUBSCRIPTION_ACTION_EXPIRE,
        payment_transaction_id=None,
        changed_by=changed_by or user_id,
        changed_at=now,
    )
    reset_usage(db, user_id)

    if commit:
        db.commit()
    else:
        db.flush()

    logger.info(
        "Downgraded user_id=%s to free plan (old_plan_id=%s)",
        user_id,
        old_plan_id,
    )
    return user_plan


def check_subscription_expiry(
    db: Session,
    *,
    user_id: int | None = None,
) -> list[int]:
    """
    Downgrade expired paid plans when Auto Renew is disabled.

    Reusable for future cron / Celery. No scheduler in this phase.

    Returns user_ids that were downgraded.
    """
    now = datetime.now(timezone.utc)
    query = select(UserPlan).where(
        UserPlan.is_auto_renew.is_(False),
        UserPlan.subscription_end.is_not(None),
    )
    if user_id is not None:
        query = query.where(UserPlan.user_id == user_id)

    rows = list(db.scalars(query).all())
    downgraded: list[int] = []

    for user_plan in rows:
        end = user_plan.subscription_end
        if end is None:
            continue
        if _as_utc(end) >= now:
            continue

        plan_name = (user_plan.plan_name or "").strip().lower()
        if plan_name == PLAN_NAME_FREE:
            continue

        if user_plan.plan_id is not None:
            plan = get_plan_by_id(db, user_plan.plan_id)
            if plan is not None and plan.plan_name.strip().lower() == PLAN_NAME_FREE:
                continue

        try:
            downgrade_to_free(
                db,
                user_id=user_plan.user_id,
                changed_by=user_plan.user_id,
                commit=True,
            )
            downgraded.append(user_plan.user_id)
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to expire subscription for user_id=%s",
                user_plan.user_id,
            )

    return downgraded


def build_subscription_status(
    db: Session,
    actor: User,
) -> dict[str, Any]:
    """Snapshot for GET /subscription-status (may run expiry first for this user)."""
    check_subscription_expiry(db, user_id=actor.id)

    user_plan = ensure_user_plan_exists(db, actor.id)
    plan: PlanMaster | None = None
    if user_plan.plan_id is not None:
        plan = get_plan_by_id(db, user_plan.plan_id)
    if plan is None:
        plan = get_plan_by_name(db, user_plan.plan_name)

    subscription_end = user_plan.subscription_end or user_plan.end_date
    remaining = remaining_subscription_days(subscription_end)
    is_expired = False
    if subscription_end is not None and _as_utc(subscription_end) < datetime.now(
        timezone.utc
    ):
        is_expired = True
        remaining = 0

    failed_count = db.scalar(
        select(PaymentTransaction.id)
        .where(
            PaymentTransaction.user_id == actor.id,
            PaymentTransaction.status == PAYMENT_STATUS_FAILED,
        )
        .limit(1)
    )
    can_retry = failed_count is not None

    plan_name = plan.plan_name if plan is not None else user_plan.plan_name
    is_paid = plan_name.strip().lower() != PLAN_NAME_FREE
    can_cancel = bool(
        user_plan.is_auto_renew
        and user_plan.razorpay_subscription_id
        and is_paid
        and not is_expired
    )

    return {
        "user_id": actor.id,
        "plan_id": plan.id if plan is not None else user_plan.plan_id,
        "plan_name": plan_name,
        "display_name": get_plan_display_name(plan_name),
        "subscription_status": user_plan.subscription_status
        or user_plan.status
        or SUBSCRIPTION_STATUS_ACTIVE,
        "is_auto_renew": bool(user_plan.is_auto_renew),
        "razorpay_subscription_id": user_plan.razorpay_subscription_id,
        "billing_cycle": user_plan.billing_cycle,
        "subscription_start": user_plan.subscription_start or user_plan.start_date,
        "subscription_end": subscription_end,
        "next_billing_date": user_plan.next_billing_date,
        "remaining_days": remaining,
        "is_expired": is_expired,
        "can_cancel": can_cancel,
        "can_retry_payment": can_retry,
    }
