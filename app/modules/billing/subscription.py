"""Razorpay AutoPay subscription helpers."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core import messages
from app.core.config import get_settings
from app.modules.auth.model import User
from app.modules.billing.activation import (
    calculate_subscription_end_date,
    create_subscription_history,
    mark_payment_success,
    reset_usage,
    resolve_subscription_history_action,
)
from app.modules.billing.checkout import (
    BillingValidationError,
    normalize_billing_cycle,
)
from app.modules.billing.model import (
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_SIX_MONTH,
    BILLING_CYCLE_YEARLY,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_SUCCESS,
    PAYMENT_TYPE_RECURRING,
    PaymentTransaction,
    SUBSCRIPTION_ACTION_RENEW,
)
from app.modules.billing.order import (
    build_create_order_payload,
    create_payment_transaction,
    rupees_to_paise,
)
from app.modules.billing.razorpay_service import get_razorpay_service
from app.modules.billing.utils import resolve_user_plan_with_master
from app.modules.plan_master.model import PLAN_NAME_FREE, PlanMaster
from app.modules.plan_master.utils import get_plan_by_id
from app.modules.user_plan.model import UserPlan
from app.modules.user_plan.utils import ensure_user_plan_exists, get_plan_display_name
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Map internal billing cycles → Razorpay plan period/interval.
_RAZORPAY_PERIOD: dict[str, tuple[str, int]] = {
    BILLING_CYCLE_MONTHLY: ("monthly", 1),
    BILLING_CYCLE_SIX_MONTH: ("monthly", 6),
    BILLING_CYCLE_YEARLY: ("yearly", 1),
}

_TOTAL_COUNT: dict[str, int] = {
    BILLING_CYCLE_MONTHLY: 120,
    BILLING_CYCLE_SIX_MONTH: 40,
    BILLING_CYCLE_YEARLY: 20,
}

_PLAN_ID_ATTR: dict[str, str] = {
    BILLING_CYCLE_MONTHLY: "monthly_razorpay_plan_id",
    BILLING_CYCLE_SIX_MONTH: "six_month_razorpay_plan_id",
    BILLING_CYCLE_YEARLY: "yearly_razorpay_plan_id",
}


def calculate_next_billing(
    start: datetime,
    billing_cycle: str,
) -> datetime:
    """Alias for subscription end / next billing date calculation."""
    return calculate_subscription_end_date(start, billing_cycle)


def get_stored_razorpay_plan_id(plan: PlanMaster, billing_cycle: str) -> str | None:
    """Return cached Razorpay plan id for a billing cycle, if any."""
    cycle = normalize_billing_cycle(billing_cycle)
    attr = _PLAN_ID_ATTR.get(cycle)
    if not attr:
        return None
    value = getattr(plan, attr, None)
    return str(value).strip() if value else None


def set_stored_razorpay_plan_id(
    plan: PlanMaster,
    billing_cycle: str,
    razorpay_plan_id: str,
) -> None:
    """Persist Razorpay plan id onto plan_master for reuse."""
    cycle = normalize_billing_cycle(billing_cycle)
    attr = _PLAN_ID_ATTR[cycle]
    setattr(plan, attr, razorpay_plan_id)


def ensure_razorpay_plan_id(
    db: Session,
    plan: PlanMaster,
    billing_cycle: str,
    amount_paise: int,
    currency: str,
) -> str:
    """
    Resolve or create a Razorpay Plan for plan_master + billing cycle.

    Caches the returned plan id on plan_master so later checkouts reuse it.
    """
    cycle = normalize_billing_cycle(billing_cycle)
    existing = get_stored_razorpay_plan_id(plan, cycle)
    if existing:
        return existing

    period, interval = _RAZORPAY_PERIOD[cycle]
    display = get_plan_display_name(plan.plan_name)
    razorpay = get_razorpay_service()
    created = razorpay.create_plan(
        period=period,
        interval=interval,
        amount_paise=amount_paise,
        currency=currency,
        name=f"{display} ({cycle})",
        description=plan.description or f"{display} auto-renew {cycle}",
    )
    plan_id = str(created["id"])
    set_stored_razorpay_plan_id(plan, cycle, plan_id)
    db.flush()
    logger.info(
        "Created Razorpay plan %s for plan_master=%s cycle=%s",
        plan_id,
        plan.plan_name,
        cycle,
    )
    return plan_id


def get_payment_transaction_by_subscription_id(
    db: Session,
    *,
    user_id: int,
    gateway_subscription_id: str,
    status: str | None = None,
) -> PaymentTransaction | None:
    """Load payment_transaction by Razorpay subscription id."""
    filters = [
        PaymentTransaction.user_id == user_id,
        PaymentTransaction.gateway_subscription_id == gateway_subscription_id,
    ]
    if status is not None:
        filters.append(PaymentTransaction.status == status)
    return db.execute(
        select(PaymentTransaction)
        .where(*filters)
        .order_by(PaymentTransaction.id.desc())
    ).scalars().first()


def create_subscription(
    db: Session,
    actor: User,
    *,
    plan_id: int,
    billing_cycle: str,
    auto_renew: bool = True,
) -> dict[str, Any]:
    """
    Create a Razorpay subscription and pending payment_transaction.

    Does not activate user_plan until verify-payment succeeds.
    """
    if not auto_renew:
        raise BillingValidationError(messages.BILLING_AUTO_RENEW_REQUIRED)

    target_plan, cycle, amounts, action = build_create_order_payload(
        db,
        actor,
        plan_id=plan_id,
        billing_cycle=billing_cycle,
    )

    user_plan = ensure_user_plan_exists(db, actor.id)
    if (
        user_plan.is_auto_renew
        and user_plan.razorpay_subscription_id
        and user_plan.plan_id == target_plan.id
        and (user_plan.billing_cycle or "") == cycle
    ):
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_EXISTS)

    settings = get_settings()
    currency = (amounts.currency or settings.RAZORPAY_CURRENCY or "INR").upper()
    amount_paise = rupees_to_paise(amounts.total_amount)

    razorpay_plan_id = ensure_razorpay_plan_id(
        db,
        target_plan,
        cycle,
        amount_paise=amount_paise,
        currency=currency,
    )

    razorpay = get_razorpay_service()
    name = f"{(actor.first_name or '').strip()} {(actor.last_name or '').strip()}".strip()
    contact = getattr(actor, "mobile", None)
    customer = razorpay.create_customer(
        name=name or actor.email.split("@")[0],
        email=actor.email,
        contact=str(contact) if contact else None,
        notes={"user_id": str(actor.id)},
    )
    customer_id = str(customer["id"])

    subscription = razorpay.create_subscription(
        plan_id=razorpay_plan_id,
        total_count=_TOTAL_COUNT.get(cycle, 120),
        customer_id=customer_id,
        notes={
            "user_id": str(actor.id),
            "plan_id": str(target_plan.id),
            "plan_name": target_plan.plan_name,
            "billing_cycle": cycle,
            "action": action,
            "auto_renew": "true",
        },
    )
    subscription_id = str(subscription["id"])

    try:
        create_payment_transaction(
            db,
            user_id=actor.id,
            plan_id=target_plan.id,
            billing_cycle=cycle,
            amount=amounts.total_amount,
            currency=currency,
            gateway_order_id=None,
            gateway_subscription_id=subscription_id,
            gateway_customer_id=customer_id,
            payment_type=PAYMENT_TYPE_RECURRING,
        )
        # Keep customer id on user_plan early for continuity (subscription id after verify).
        user_plan.razorpay_customer_id = customer_id
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "subscription_id": subscription_id,
        "key": razorpay.key_id,
        "customer_id": customer_id,
        "plan_id": target_plan.id,
        "plan_name": target_plan.plan_name,
        "display_name": get_plan_display_name(target_plan.plan_name),
        "billing_cycle": cycle,
        "action": action,
        "currency": currency,
        "amount": amount_paise,
        "total_amount": float(amounts.total_amount),
        "subtotal": float(amounts.subtotal),
        "discount": float(amounts.discount),
        "gst_percentage": float(amounts.gst_percentage),
        "gst_amount": float(amounts.gst_amount),
        "auto_renew": True,
    }


def activate_subscription(
    db: Session,
    *,
    user_id: int,
    plan: PlanMaster,
    billing_cycle: str,
    amount: Decimal,
    razorpay_subscription_id: str,
    razorpay_customer_id: str | None,
    subscription_start: datetime | None = None,
) -> tuple[UserPlan, datetime, datetime]:
    """Activate user_plan with AutoPay flags and Razorpay subscription ids."""
    from app.modules.billing.activation import update_user_plan

    start = subscription_start or datetime.now(timezone.utc)
    end = calculate_next_billing(start, billing_cycle)
    user_plan = ensure_user_plan_exists(db, user_id)
    update_user_plan(
        user_plan,
        plan=plan,
        billing_cycle=billing_cycle,
        amount=amount,
        subscription_start=start,
        subscription_end=end,
        is_auto_renew=True,
        razorpay_subscription_id=razorpay_subscription_id,
        razorpay_customer_id=razorpay_customer_id,
    )
    db.flush()
    return user_plan, start, end


def verify_subscription(
    db: Session,
    actor: User,
    *,
    razorpay_subscription_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict[str, Any]:
    """
    Verify subscription payment signature and activate AutoPay plan.

    Idempotent for the same gateway payment id.
    """
    sub_id = (razorpay_subscription_id or "").strip()
    payment_id = (razorpay_payment_id or "").strip()
    signature = (razorpay_signature or "").strip()

    if not sub_id or not payment_id or not signature:
        raise BillingValidationError(messages.BILLING_PAYMENT_VERIFICATION_FAILED)

    payment = get_payment_transaction_by_subscription_id(
        db,
        user_id=actor.id,
        gateway_subscription_id=sub_id,
    )
    if payment is None:
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_NOT_FOUND)

    if payment.status == PAYMENT_STATUS_SUCCESS:
        if payment.gateway_payment_id == payment_id:
            plan = get_plan_by_id(db, payment.plan_id)
            user_plan = ensure_user_plan_exists(db, actor.id)
            return {
                "already_verified": True,
                "payment": payment,
                "plan": plan,
                "user_plan": user_plan,
                "action": None,
            }
        # Later renewal charge for same subscription — treat as renew flow
        return _process_subscription_renewal(
            db,
            actor,
            pending_or_template=payment,
            razorpay_subscription_id=sub_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
        )

    if payment.status != PAYMENT_STATUS_PENDING:
        raise BillingValidationError(messages.BILLING_PAYMENT_NOT_PENDING)

    razorpay = get_razorpay_service()
    razorpay.verify_subscription_payment_signature(
        razorpay_subscription_id=sub_id,
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

    gateway_payment = razorpay.fetch_payment(payment_id)
    payment_method = None
    if gateway_payment and gateway_payment.get("method"):
        payment_method = str(gateway_payment["method"])

    customer_id = payment.gateway_customer_id or user_plan.razorpay_customer_id
    now = datetime.now(timezone.utc)

    try:
        mark_payment_success(
            payment,
            gateway_payment_id=payment_id,
            gateway_signature=signature,
            payment_method=payment_method,
            transaction_date=now,
        )
        payment.payment_type = PAYMENT_TYPE_RECURRING
        user_plan, start, end = activate_subscription(
            db,
            user_id=actor.id,
            plan=target_plan,
            billing_cycle=payment.billing_cycle,
            amount=payment.amount,
            razorpay_subscription_id=sub_id,
            razorpay_customer_id=customer_id,
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

    return {
        "already_verified": False,
        "payment": payment,
        "plan": target_plan,
        "user_plan": user_plan,
        "action": history_action,
        "subscription_start": start,
        "subscription_end": end,
    }


def _process_subscription_renewal(
    db: Session,
    actor: User,
    *,
    pending_or_template: PaymentTransaction,
    razorpay_subscription_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict[str, Any]:
    """
    Handle a subsequent successful AutoPay charge for an existing subscription.

    Creates a new payment_transaction (recurring), renews dates, resets usage.
    """
    # Avoid duplicating the same payment id.
    existing = db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.user_id == actor.id,
            PaymentTransaction.gateway_payment_id == razorpay_payment_id,
        )
    ).scalar_one_or_none()
    if existing is not None and existing.status == PAYMENT_STATUS_SUCCESS:
        plan = get_plan_by_id(db, existing.plan_id)
        user_plan = ensure_user_plan_exists(db, actor.id)
        return {
            "already_verified": True,
            "payment": existing,
            "plan": plan,
            "user_plan": user_plan,
            "action": None,
        }

    razorpay = get_razorpay_service()
    razorpay.verify_subscription_payment_signature(
        razorpay_subscription_id=razorpay_subscription_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    )

    plan = get_plan_by_id(db, pending_or_template.plan_id)
    if plan is None:
        raise BillingValidationError(messages.BILLING_PLAN_NOT_FOUND)

    user_plan = ensure_user_plan_exists(db, actor.id)
    now = datetime.now(timezone.utc)
    gateway_payment = razorpay.fetch_payment(razorpay_payment_id)
    payment_method = (
        str(gateway_payment["method"])
        if gateway_payment and gateway_payment.get("method")
        else None
    )

    try:
        renewal = create_payment_transaction(
            db,
            user_id=actor.id,
            plan_id=plan.id,
            billing_cycle=pending_or_template.billing_cycle,
            amount=pending_or_template.amount,
            currency=pending_or_template.currency,
            gateway_order_id=None,
            gateway_subscription_id=razorpay_subscription_id,
            gateway_customer_id=pending_or_template.gateway_customer_id
            or user_plan.razorpay_customer_id,
            payment_type=PAYMENT_TYPE_RECURRING,
            status=PAYMENT_STATUS_PENDING,
        )
        mark_payment_success(
            renewal,
            gateway_payment_id=razorpay_payment_id,
            gateway_signature=razorpay_signature,
            payment_method=payment_method,
            transaction_date=now,
        )
        end = calculate_next_billing(now, pending_or_template.billing_cycle)
        user_plan.subscription_start = now
        user_plan.subscription_end = end
        user_plan.start_date = now
        user_plan.end_date = end
        user_plan.next_billing_date = end
        user_plan.current_billing = pending_or_template.amount
        user_plan.is_auto_renew = True
        user_plan.razorpay_subscription_id = razorpay_subscription_id
        user_plan.updated_at = now

        create_subscription_history(
            db,
            user_id=actor.id,
            old_plan_id=plan.id,
            new_plan_id=plan.id,
            action=SUBSCRIPTION_ACTION_RENEW,
            payment_transaction_id=renewal.id,
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
            payment=renewal,
            plan=plan,
        )
    except Exception:
        logger.exception(
            "Post-renewal invoice pipeline failed payment_id=%s",
            renewal.id,
        )

    return {
        "already_verified": False,
        "payment": renewal,
        "plan": plan,
        "user_plan": user_plan,
        "action": SUBSCRIPTION_ACTION_RENEW,
        "subscription_start": now,
        "subscription_end": end,
    }


def disable_auto_renew(
    db: Session,
    actor: User,
    *,
    subscription_id: str | None = None,
) -> dict[str, Any]:
    """
    Disable AutoPay at cycle end. Current plan remains active until expiry.

    Delegates to cancel_subscription (Phase 6 canonical cancel path).
    """
    from app.modules.billing.lifecycle import cancel_subscription

    return cancel_subscription(db, actor, subscription_id=subscription_id)


def enable_auto_renew(
    db: Session,
    actor: User,
) -> dict[str, Any]:
    """
    Re-enable AutoPay.

    Tries Razorpay resume first; otherwise creates a fresh subscription payload
    the frontend can use to complete mandate checkout.
    """
    user_plan = ensure_user_plan_exists(db, actor.id)
    if user_plan.plan_id is None:
        raise BillingValidationError(messages.BILLING_PLAN_NOT_FOUND)

    plan = get_plan_by_id(db, user_plan.plan_id)
    if plan is None or not plan.is_active:
        raise BillingValidationError(messages.BILLING_PLAN_INACTIVE)

    if plan.plan_name.strip().lower() == PLAN_NAME_FREE:
        raise BillingValidationError(messages.BILLING_CHECKOUT_FREE_PLAN)

    cycle = normalize_billing_cycle(user_plan.billing_cycle or BILLING_CYCLE_MONTHLY)

    if user_plan.is_auto_renew and user_plan.razorpay_subscription_id:
        raise BillingValidationError(messages.BILLING_SUBSCRIPTION_ALREADY_ACTIVE)

    razorpay = get_razorpay_service()
    existing_sub = (user_plan.razorpay_subscription_id or "").strip()
    if existing_sub:
        resumed = razorpay.resume_subscription(existing_sub)
        if resumed and resumed.get("id"):
            user_plan.is_auto_renew = True
            user_plan.updated_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "mode": "resumed",
                "subscription_id": existing_sub,
                "key": razorpay.key_id,
                "is_auto_renew": True,
                "requires_checkout": False,
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "display_name": get_plan_display_name(plan.plan_name),
                "billing_cycle": cycle,
            }

    # Create a new subscription — frontend must open Razorpay Checkout.
    created = create_subscription(
        db,
        actor,
        plan_id=plan.id,
        billing_cycle=cycle,
        auto_renew=True,
    )
    return {
        "mode": "created",
        "requires_checkout": True,
        **created,
    }
