"""Billing checkout helpers: pricing, GST, upgrade/downgrade validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from sqlalchemy.orm import Session

from app.core import messages
from app.core.config import get_settings
from app.modules.billing.model import (
    ALLOWED_BILLING_CYCLES,
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_SIX_MONTH,
    BILLING_CYCLE_YEARLY,
)
from app.modules.plan_master.model import PlanMaster
from app.modules.plan_master.utils import get_plan_by_id
from app.modules.user_plan.model import UserPlan

PlanChangeAction = Literal["upgrade", "downgrade", "same", "switch"]

_MONEY = Decimal("0.01")
_ZERO = Decimal("0.00")


class BillingValidationError(Exception):
    """Raised when checkout / plan selection validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class PlanPricingBreakdown:
    """
    Dynamic pricing breakdown for a plan + billing cycle.

    Savings / discounts are calculated — never stored in the database.
    """

    billing_cycle: str
    currency: str
    monthly_price: Decimal
    cycle_price: Decimal
    list_price: Decimal
    discount_percentage: Decimal
    discount: Decimal
    saving: Decimal
    subtotal: Decimal
    gst_percentage: Decimal
    gst_amount: Decimal
    total_amount: Decimal


@dataclass(frozen=True)
class CheckoutAmounts:
    """Calculated checkout money fields (Decimal precision)."""

    price: Decimal
    subtotal: Decimal
    discount: Decimal
    saving: Decimal
    discount_percentage: Decimal
    gst_percentage: Decimal
    gst_amount: Decimal
    total_amount: Decimal
    currency: str
    list_price: Decimal


def normalize_billing_cycle(value: str | None) -> str:
    """Normalize and validate a billing cycle string."""
    if value is None or not str(value).strip():
        raise BillingValidationError(messages.BILLING_CYCLE_INVALID)

    cycle = str(value).strip().lower()
    aliases = {
        "month": BILLING_CYCLE_MONTHLY,
        "6_month": BILLING_CYCLE_SIX_MONTH,
        "6month": BILLING_CYCLE_SIX_MONTH,
        "six-month": BILLING_CYCLE_SIX_MONTH,
        "six months": BILLING_CYCLE_SIX_MONTH,
        "year": BILLING_CYCLE_YEARLY,
        "annual": BILLING_CYCLE_YEARLY,
        "annually": BILLING_CYCLE_YEARLY,
    }
    cycle = aliases.get(cycle, cycle)

    if cycle not in ALLOWED_BILLING_CYCLES:
        raise BillingValidationError(messages.BILLING_CYCLE_INVALID)
    return cycle


def _as_money(value: Decimal | float | int | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY, rounding=ROUND_HALF_UP)


def calculate_plan_price(plan: PlanMaster, billing_cycle: str) -> Decimal:
    """Return the plan price for a billing cycle from plan_master."""
    cycle = normalize_billing_cycle(billing_cycle)
    if cycle == BILLING_CYCLE_MONTHLY:
        return _as_money(plan.monthly_price)
    if cycle == BILLING_CYCLE_SIX_MONTH:
        return _as_money(plan.six_month_price)
    if cycle == BILLING_CYCLE_YEARLY:
        return _as_money(plan.yearly_price)
    raise BillingValidationError(messages.BILLING_CYCLE_INVALID)


def calculate_cycle_saving(plan: PlanMaster, billing_cycle: str) -> Decimal:
    """
    Dynamic saving vs paying monthly for the same duration.

    six_month_saving = (monthly_price × 6) − six_month_price
    yearly_saving = (monthly_price × 12) − yearly_price
    """
    cycle = normalize_billing_cycle(billing_cycle)
    monthly = _as_money(plan.monthly_price)
    if cycle == BILLING_CYCLE_MONTHLY:
        return _ZERO
    if cycle == BILLING_CYCLE_SIX_MONTH:
        list_price = (monthly * Decimal("6")).quantize(_MONEY, rounding=ROUND_HALF_UP)
        return max(list_price - _as_money(plan.six_month_price), _ZERO)
    if cycle == BILLING_CYCLE_YEARLY:
        list_price = (monthly * Decimal("12")).quantize(_MONEY, rounding=ROUND_HALF_UP)
        return max(list_price - _as_money(plan.yearly_price), _ZERO)
    raise BillingValidationError(messages.BILLING_CYCLE_INVALID)


def calculate_cycle_list_price(plan: PlanMaster, billing_cycle: str) -> Decimal:
    """List price if the user paid monthly for the full cycle duration."""
    cycle = normalize_billing_cycle(billing_cycle)
    monthly = _as_money(plan.monthly_price)
    if cycle == BILLING_CYCLE_MONTHLY:
        return monthly
    if cycle == BILLING_CYCLE_SIX_MONTH:
        return (monthly * Decimal("6")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    if cycle == BILLING_CYCLE_YEARLY:
        return (monthly * Decimal("12")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    raise BillingValidationError(messages.BILLING_CYCLE_INVALID)


def discount_percentage_for_cycle(plan: PlanMaster, billing_cycle: str) -> Decimal:
    """Return the editable discount percentage stored on plan_master for a cycle."""
    cycle = normalize_billing_cycle(billing_cycle)
    if cycle == BILLING_CYCLE_SIX_MONTH:
        return _as_money(getattr(plan, "six_month_discount_percentage", 0))
    if cycle == BILLING_CYCLE_YEARLY:
        return _as_money(getattr(plan, "yearly_discount_percentage", 0))
    return _ZERO


def calculate_gst(
    taxable: Decimal,
    *,
    gst_percentage: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Calculate GST and grand total from a taxable amount.

    Returns (gst_percentage, gst_amount, total_amount).
    """
    settings = get_settings()
    rate = (
        gst_percentage
        if gst_percentage is not None
        else Decimal(str(settings.GST_PERCENTAGE))
    ).quantize(_MONEY, rounding=ROUND_HALF_UP)
    base = max(_as_money(taxable), _ZERO)
    gst_amount = (base * rate / Decimal("100")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    total = (base + gst_amount).quantize(_MONEY, rounding=ROUND_HALF_UP)
    return rate, gst_amount, total


def calculate_plan_pricing(
    plan: PlanMaster,
    billing_cycle: str,
) -> PlanPricingBreakdown:
    """
    Reusable pricing helper used by plans catalog and checkout.

    Input: plan + billing cycle
    Output: price, discount/saving, GST, grand total — all derived from DB values.
    """
    cycle = normalize_billing_cycle(billing_cycle)
    monthly_price = _as_money(plan.monthly_price)
    cycle_price = calculate_plan_price(plan, cycle)
    list_price = calculate_cycle_list_price(plan, cycle)
    saving = calculate_cycle_saving(plan, cycle)
    discount_percentage = discount_percentage_for_cycle(plan, cycle)
    discount = saving
    # Chargeable subtotal is the cycle price from DB (after catalog discount).
    subtotal = cycle_price
    gst_percentage, gst_amount, total_amount = calculate_gst(subtotal)
    currency = (plan.currency or get_settings().BILLING_CURRENCY or "INR").upper()

    return PlanPricingBreakdown(
        billing_cycle=cycle,
        currency=currency,
        monthly_price=monthly_price,
        cycle_price=cycle_price,
        list_price=list_price,
        discount_percentage=discount_percentage,
        discount=discount,
        saving=saving,
        subtotal=subtotal,
        gst_percentage=gst_percentage,
        gst_amount=gst_amount,
        total_amount=total_amount,
    )


def build_checkout_amounts(
    plan: PlanMaster,
    billing_cycle: str,
) -> CheckoutAmounts:
    """Build a full checkout money breakdown via calculate_plan_pricing()."""
    pricing = calculate_plan_pricing(plan, billing_cycle)
    return CheckoutAmounts(
        price=pricing.cycle_price,
        subtotal=pricing.subtotal,
        discount=pricing.discount,
        saving=pricing.saving,
        discount_percentage=pricing.discount_percentage,
        gst_percentage=pricing.gst_percentage,
        gst_amount=pricing.gst_amount,
        total_amount=pricing.total_amount,
        currency=pricing.currency,
        list_price=pricing.list_price,
    )


def plan_catalog_savings(plan: PlanMaster) -> tuple[Decimal, Decimal]:
    """Return (six_month_saving, yearly_saving) calculated dynamically."""
    return (
        calculate_cycle_saving(plan, BILLING_CYCLE_SIX_MONTH),
        calculate_cycle_saving(plan, BILLING_CYCLE_YEARLY),
    )


def plan_rank(plan: PlanMaster) -> int:
    """Higher display_order means a higher tier plan."""
    return int(plan.display_order or 0)


def classify_plan_change(
    current_plan: PlanMaster | None,
    target_plan: PlanMaster,
) -> PlanChangeAction:
    """Classify checkout as upgrade, downgrade, same, or switch."""
    if current_plan is None:
        return "upgrade"
    if current_plan.id == target_plan.id:
        return "same"
    if plan_rank(target_plan) > plan_rank(current_plan):
        return "upgrade"
    if plan_rank(target_plan) < plan_rank(current_plan):
        return "downgrade"
    return "switch"


def validate_plan_change(
    current_plan: PlanMaster | None,
    target_plan: PlanMaster,
) -> PlanChangeAction:
    """
    Validate that the user may move to the target plan.

    Raises BillingValidationError when already on the same plan.
    """
    if not target_plan.is_active:
        raise BillingValidationError(messages.BILLING_PLAN_INACTIVE)

    action = classify_plan_change(current_plan, target_plan)
    if action == "same":
        raise BillingValidationError(messages.BILLING_ALREADY_ON_PLAN)
    return action


def resolve_active_plan_or_raise(db: Session, plan_id: int) -> PlanMaster:
    """Load an active plan by id or raise a billing validation error."""
    plan = get_plan_by_id(db, plan_id)
    if plan is None:
        raise BillingValidationError(messages.BILLING_PLAN_NOT_FOUND)
    if not plan.is_active:
        raise BillingValidationError(messages.BILLING_PLAN_INACTIVE)
    return plan


def is_recommended_plan(plan: PlanMaster) -> bool:
    """Return True when this plan is the configured recommended plan."""
    recommended = get_settings().BILLING_RECOMMENDED_PLAN
    return plan.plan_name.strip().lower() == recommended


def money_to_float(value: Decimal) -> float:
    """Convert Decimal money to float for JSON responses."""
    return float(_as_money(value))


def current_price_for_user_plan(
    plan: PlanMaster | None,
    user_plan: UserPlan,
) -> Decimal | None:
    """Resolve the price the user is currently billed at for their cycle."""
    if plan is None:
        return None
    cycle = (user_plan.billing_cycle or BILLING_CYCLE_MONTHLY).strip().lower()
    try:
        return calculate_plan_price(plan, cycle)
    except BillingValidationError:
        return _as_money(plan.monthly_price)
