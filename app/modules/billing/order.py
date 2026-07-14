"""Payment order helpers: amount calculation and pending transaction storage."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from app.core import messages
from app.core.config import get_settings
from app.modules.auth.model import User
from app.modules.billing.checkout import (
    BillingValidationError,
    CheckoutAmounts,
    build_checkout_amounts,
    normalize_billing_cycle,
    resolve_active_plan_or_raise,
    validate_plan_change,
)
from app.modules.billing.model import (
    GATEWAY_RAZORPAY,
    PAYMENT_STATUS_PENDING,
    PAYMENT_TYPE_ONE_TIME,
    PaymentTransaction,
)
from app.modules.billing.razorpay_service import RazorpayService, get_razorpay_service
from app.modules.billing.utils import resolve_user_plan_with_master
from app.modules.plan_master.model import PlanMaster, PLAN_NAME_FREE
from app.modules.user_plan.utils import get_plan_display_name

_PAISE = Decimal("100")


def rupees_to_paise(amount: Decimal | float | int) -> int:
    """Convert a rupee Decimal amount to integer paise for Razorpay."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((value * _PAISE).to_integral_value(rounding=ROUND_HALF_UP))


def calculate_order_amount(
    plan: PlanMaster,
    billing_cycle: str,
) -> CheckoutAmounts:
    """
    Calculate price / discount / GST / grand total from plan_master.

    Never trust a frontend-provided amount.
    """
    amounts = build_checkout_amounts(plan, billing_cycle)
    if amounts.total_amount <= Decimal("0.00"):
        raise BillingValidationError(messages.BILLING_ORDER_AMOUNT_INVALID)
    return amounts


def create_payment_transaction(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    billing_cycle: str,
    amount: Decimal,
    currency: str,
    gateway_order_id: str | None = None,
    gateway_subscription_id: str | None = None,
    gateway_customer_id: str | None = None,
    payment_type: str = PAYMENT_TYPE_ONE_TIME,
    gateway: str = GATEWAY_RAZORPAY,
    status: str = PAYMENT_STATUS_PENDING,
    retry_of_payment_id: int | None = None,
) -> PaymentTransaction:
    """Persist a pending payment_transaction row for order or subscription."""
    row = PaymentTransaction(
        user_id=user_id,
        plan_id=plan_id,
        gateway=gateway,
        gateway_order_id=gateway_order_id,
        gateway_subscription_id=gateway_subscription_id,
        gateway_customer_id=gateway_customer_id,
        amount=amount,
        currency=currency.upper(),
        billing_cycle=billing_cycle,
        payment_type=payment_type,
        status=status,
        retry_of_payment_id=retry_of_payment_id,
    )
    db.add(row)
    db.flush()
    return row


def create_razorpay_order(
    *,
    amount_paise: int,
    currency: str,
    receipt: str,
    notes: dict[str, str],
    razorpay: RazorpayService | None = None,
) -> dict[str, Any]:
    """Create a Razorpay order via the reusable service."""
    client = razorpay or get_razorpay_service()
    return client.create_order(
        amount_paise=amount_paise,
        currency=currency,
        receipt=receipt,
        notes=notes,
    )


def build_create_order_payload(
    db: Session,
    actor: User,
    *,
    plan_id: int,
    billing_cycle: str,
) -> tuple[PlanMaster, str, CheckoutAmounts, str]:
    """
    Validate plan change and return (plan, cycle, amounts, action).

    Does not create a gateway order or mutate user_plan.
    """
    cycle = normalize_billing_cycle(billing_cycle)
    target_plan = resolve_active_plan_or_raise(db, plan_id)

    if target_plan.plan_name.strip().lower() == PLAN_NAME_FREE:
        raise BillingValidationError(messages.BILLING_CHECKOUT_FREE_PLAN)

    _, current_plan = resolve_user_plan_with_master(db, actor.id)
    action = validate_plan_change(current_plan, target_plan)
    if action not in {"upgrade", "downgrade", "switch"}:
        raise BillingValidationError(messages.BILLING_ALREADY_ON_PLAN)

    amounts = calculate_order_amount(target_plan, cycle)
    return target_plan, cycle, amounts, action


def create_pending_razorpay_order(
    db: Session,
    actor: User,
    *,
    plan_id: int,
    billing_cycle: str,
) -> dict[str, Any]:
    """
    Full create-order flow:

    validate → calculate totals → Razorpay order → pending payment_transaction.

    Does NOT activate the plan or update user_plan.
    """
    settings = get_settings()
    target_plan, cycle, amounts, action = build_create_order_payload(
        db,
        actor,
        plan_id=plan_id,
        billing_cycle=billing_cycle,
    )

    amount_paise = rupees_to_paise(amounts.total_amount)
    currency = (amounts.currency or settings.RAZORPAY_CURRENCY or "INR").upper()
    receipt = f"uid{actor.id}_p{target_plan.id}_{cycle}"[:40]
    notes = {
        "user_id": str(actor.id),
        "plan_id": str(target_plan.id),
        "plan_name": target_plan.plan_name,
        "billing_cycle": cycle,
        "action": action,
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
        "action": action,
        "subtotal": float(amounts.subtotal),
        "discount": float(amounts.discount),
        "gst_percentage": float(amounts.gst_percentage),
        "gst_amount": float(amounts.gst_amount),
        "total_amount": float(amounts.total_amount),
    }
