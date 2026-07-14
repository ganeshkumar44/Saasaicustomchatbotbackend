"""Billing helpers: access control, serialization, and queries."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import USER_ROLE_ADMIN, USER_ROLE_USER
from app.modules.billing.model import Invoice, PaymentTransaction, SubscriptionHistory
from app.modules.billing.activation import remaining_subscription_days
from app.modules.billing.checkout import (
    classify_plan_change,
    current_price_for_user_plan,
    is_recommended_plan,
    money_to_float,
    plan_catalog_savings,
    plan_rank,
)
from app.modules.billing.schema import (
    BillingPlanData,
    CurrentPlanData,
    InvoiceItem,
    PaymentHistoryItem,
    PlanComparisonData,
    PlanComparisonPlanHeader,
    PlanComparisonRow,
    PlanComparisonValue,
    SubscriptionHistoryItem,
    format_money,
)
from app.modules.plan_master.model import PlanMaster
from app.modules.plan_master.utils import (
    _features_from_limits,
    is_unlimited,
    list_active_plans,
)
from app.modules.user_details.utils import is_superadmin
from app.modules.user_plan.model import (
    BILLING_CYCLE_MONTHLY,
    SUBSCRIPTION_STATUS_ACTIVE,
    UserPlan,
)
from app.modules.user_plan.utils import (
    ensure_user_plan_exists,
    get_plan_display_name,
)


class BillingAccessDeniedError(Exception):
    """Raised when the actor cannot view the requested billing records."""

    def __init__(self, message: str = messages.BILLING_ACCESS_DENIED) -> None:
        self.message = message
        super().__init__(message)


class BillingUserNotFoundError(Exception):
    """Raised when a billing target user does not exist."""

    def __init__(self, message: str = messages.BILLING_USER_NOT_FOUND) -> None:
        self.message = message
        super().__init__(message)


def resolve_billing_target_user(
    db: Session,
    actor: User,
    user_id: int | None,
) -> User:
    """
    Resolve which user's billing data the actor may view.

    - User: own records only
    - Admin: User-role accounts only
    - SuperAdmin: any account
    """
    if user_id is None or user_id == actor.id:
        return actor

    target = db.execute(
        select(User).where(
            User.id == user_id,
            User.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if target is None:
        raise BillingUserNotFoundError()

    if is_superadmin(actor):
        return target

    if actor.role == USER_ROLE_ADMIN:
        if target.role != USER_ROLE_USER:
            raise BillingAccessDeniedError()
        return target

    raise BillingAccessDeniedError()


def _normalize_features(raw: object | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item is not None and str(item).strip()]
    return []


def serialize_billing_plan(
    plan: PlanMaster,
    *,
    current_plan: PlanMaster | None = None,
) -> BillingPlanData:
    """Serialize a plan_master row for the billing plans catalog."""
    stored_features = _normalize_features(plan.features)
    # Always prefix with live limit bullets so display stays dynamic from DB.
    limit_features = _features_from_limits(
        max_chatbots=plan.max_chatbots,
        chatbot_message_limit=plan.chatbot_message_limit,
        playground_message_limit=plan.playground_message_limit,
    )
    extras = [
        item
        for item in stored_features
        if item not in limit_features
        and "website messages" not in item.lower()
        and "playground messages" not in item.lower()
        and "chatbot" not in item.lower()
    ]
    features = limit_features + extras

    is_current = current_plan is not None and current_plan.id == plan.id
    change = classify_plan_change(current_plan, plan)
    six_month_saving, yearly_saving = plan_catalog_savings(plan)

    return BillingPlanData(
        plan_id=plan.id,
        id=plan.id,
        plan_name=plan.plan_name,
        display_name=get_plan_display_name(plan.plan_name),
        description=plan.description,
        monthly_price=money_to_float(plan.monthly_price),
        six_month_price=money_to_float(plan.six_month_price),
        yearly_price=money_to_float(plan.yearly_price),
        six_month_discount_percentage=money_to_float(
            getattr(plan, "six_month_discount_percentage", 0)
        ),
        yearly_discount_percentage=money_to_float(
            getattr(plan, "yearly_discount_percentage", 0)
        ),
        six_month_saving=money_to_float(six_month_saving),
        yearly_saving=money_to_float(yearly_saving),
        currency=plan.currency or "INR",
        chatbot_limit=plan.max_chatbots,
        website_message_limit=plan.chatbot_message_limit,
        playground_message_limit=plan.playground_message_limit,
        website_message_unlimited=is_unlimited(plan.chatbot_message_limit),
        playground_message_unlimited=is_unlimited(plan.playground_message_limit),
        features=features,
        display_order=plan.display_order,
        is_active=plan.is_active,
        current_plan=is_current,
        recommended=is_recommended_plan(plan),
        can_upgrade=change == "upgrade",
        can_downgrade=change == "downgrade",
    )


def serialize_current_plan(
    *,
    user: User,
    user_plan: UserPlan,
    plan: PlanMaster | None,
) -> CurrentPlanData:
    """Serialize the user's active subscription with live plan_master limits."""
    plan_name = plan.plan_name if plan is not None else user_plan.plan_name
    chatbot_limit = plan.max_chatbots if plan is not None else user_plan.chatbot_limit
    website_limit = plan.chatbot_message_limit if plan is not None else None
    playground_limit = plan.playground_message_limit if plan is not None else None
    currency = plan.currency if plan is not None else None
    monthly_price = (
        money_to_float(plan.monthly_price) if plan is not None else None
    )
    current_price_value = current_price_for_user_plan(plan, user_plan)
    current_price = (
        money_to_float(current_price_value) if current_price_value is not None else None
    )
    created_count = int(user_plan.created_chatbots_count or 0)
    remaining = max(chatbot_limit - created_count, 0)

    subscription_status = (
        user_plan.subscription_status
        or user_plan.status
        or SUBSCRIPTION_STATUS_ACTIVE
    )
    billing_cycle = user_plan.billing_cycle or (
        BILLING_CYCLE_MONTHLY if plan is not None else None
    )
    subscription_end = user_plan.subscription_end or user_plan.end_date
    remaining_days = remaining_subscription_days(subscription_end)
    is_expired = False
    if subscription_end is not None:
        end = subscription_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < datetime.now(timezone.utc):
            is_expired = True
            remaining_days = 0

    current_billing = money_to_float(user_plan.current_billing)

    return CurrentPlanData(
        user_id=user.id,
        plan_id=plan.id if plan is not None else user_plan.plan_id,
        plan_name=plan_name,
        display_name=get_plan_display_name(plan_name),
        subscription_status=subscription_status,
        billing_cycle=billing_cycle,
        subscription_start=user_plan.subscription_start or user_plan.start_date,
        subscription_end=subscription_end,
        next_billing_date=user_plan.next_billing_date,
        is_auto_renew=bool(user_plan.is_auto_renew),
        remaining_days=remaining_days,
        is_expired=is_expired,
        razorpay_subscription_id=user_plan.razorpay_subscription_id,
        website_message_limit=website_limit,
        playground_message_limit=playground_limit,
        chatbot_limit=chatbot_limit,
        website_message_unlimited=is_unlimited(website_limit),
        playground_message_unlimited=is_unlimited(playground_limit),
        currency=currency,
        monthly_price=monthly_price,
        current_price=current_price,
        current_billing=current_billing,
        created_chatbots_count=created_count,
        remaining_chatbots=remaining,
    )


def _limit_display(value: int | None) -> str:
    if value is None:
        return "Unlimited"
    return f"{value:,}"


def build_plan_comparison(
    plans: list[PlanMaster],
    *,
    current_plan: PlanMaster | None = None,
) -> PlanComparisonData:
    """Build a feature comparison matrix for the pricing page table."""
    headers = [
        PlanComparisonPlanHeader(
            plan_id=plan.id,
            plan_name=plan.plan_name,
            display_name=get_plan_display_name(plan.plan_name),
            recommended=is_recommended_plan(plan),
            current_plan=current_plan is not None and current_plan.id == plan.id,
            display_order=plan.display_order,
        )
        for plan in plans
    ]

    def values_for(
        feature_key: str,
        resolver,
    ) -> list[PlanComparisonValue]:
        return [
            PlanComparisonValue(
                plan_id=plan.id,
                plan_name=plan.plan_name,
                display_name=get_plan_display_name(plan.plan_name),
                value=resolver(plan),
            )
            for plan in plans
        ]

    rows = [
        PlanComparisonRow(
            feature_key="chatbots",
            feature_label="Chatbots",
            values=values_for("chatbots", lambda p: p.max_chatbots),
        ),
        PlanComparisonRow(
            feature_key="website_messages",
            feature_label="Website Messages",
            values=values_for(
                "website_messages",
                lambda p: _limit_display(p.chatbot_message_limit),
            ),
        ),
        PlanComparisonRow(
            feature_key="playground_messages",
            feature_label="Playground Messages",
            values=values_for(
                "playground_messages",
                lambda p: _limit_display(p.playground_message_limit),
            ),
        ),
        PlanComparisonRow(
            feature_key="analytics",
            feature_label="Analytics",
            values=values_for(
                "analytics",
                lambda p: "Advanced" if plan_rank(p) >= 2 else "Basic",
            ),
        ),
        PlanComparisonRow(
            feature_key="priority_support",
            feature_label="Priority Support",
            values=values_for(
                "priority_support",
                lambda p: plan_rank(p) >= 3,
            ),
        ),
        PlanComparisonRow(
            feature_key="dedicated_support",
            feature_label="Dedicated Support",
            values=values_for(
                "dedicated_support",
                lambda p: plan_rank(p) >= 4,
            ),
        ),
    ]

    return PlanComparisonData(plans=headers, rows=rows)


def serialize_payment_transaction(
    payment: PaymentTransaction,
) -> PaymentHistoryItem:
    """Serialize a payment_transaction row."""
    plan_name = payment.plan.plan_name if payment.plan is not None else None
    return PaymentHistoryItem(
        id=payment.id,
        plan_id=payment.plan_id,
        plan_name=plan_name,
        gateway=payment.gateway,
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        gateway_subscription_id=getattr(payment, "gateway_subscription_id", None),
        amount=format_money(payment.amount),
        currency=payment.currency,
        billing_cycle=payment.billing_cycle,
        payment_method=payment.payment_method,
        payment_type=getattr(payment, "payment_type", None) or "one_time",
        retry_of_payment_id=getattr(payment, "retry_of_payment_id", None),
        status=payment.status,
        failure_reason=payment.failure_reason,
        transaction_date=payment.transaction_date,
        created_at=payment.created_at,
    )


def serialize_subscription_history(
    entry: SubscriptionHistory,
) -> SubscriptionHistoryItem:
    """Serialize a subscription_history row."""
    return SubscriptionHistoryItem(
        id=entry.id,
        old_plan_id=entry.old_plan_id,
        old_plan_name=entry.old_plan.plan_name if entry.old_plan is not None else None,
        new_plan_id=entry.new_plan_id,
        new_plan_name=entry.new_plan.plan_name if entry.new_plan is not None else None,
        action=entry.action,
        payment_transaction_id=entry.payment_transaction_id,
        changed_by=entry.changed_by,
        changed_at=entry.changed_at,
        created_at=entry.created_at,
    )


def serialize_invoice(invoice: Invoice) -> InvoiceItem:
    """Serialize an invoice row."""
    from app.modules.user_plan.utils import get_plan_display_name

    plan_name = invoice.plan.plan_name if invoice.plan is not None else None
    return InvoiceItem(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        invoice_date=getattr(invoice, "invoice_date", None) or invoice.created_at,
        payment_transaction_id=invoice.payment_transaction_id,
        plan_id=invoice.plan_id,
        plan_name=plan_name,
        display_name=get_plan_display_name(plan_name) if plan_name else None,
        billing_cycle=getattr(invoice, "billing_cycle", None),
        subtotal=format_money(invoice.subtotal),
        discount=format_money(invoice.discount),
        gst_percentage=format_money(invoice.gst_percentage),
        gst_amount=format_money(invoice.gst_amount),
        total_amount=format_money(invoice.total_amount),
        currency=invoice.currency,
        invoice_status=invoice.invoice_status,
        pdf_path=invoice.pdf_path,
        billing_name=invoice.billing_name,
        billing_email=invoice.billing_email,
        billing_phone=invoice.billing_phone,
        billing_address=invoice.billing_address,
        billing_city=getattr(invoice, "billing_city", None),
        billing_state=invoice.billing_state,
        billing_country=invoice.billing_country,
        billing_pincode=invoice.billing_pincode,
        gst_number=invoice.gst_number,
        company_name=getattr(invoice, "company_name", None),
        payment_method=getattr(invoice, "payment_method", None),
        payment_status=getattr(invoice, "payment_status", None),
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def fetch_active_plans(db: Session) -> list[PlanMaster]:
    """Repository helper: list active plans from plan_master."""
    return list_active_plans(db)


def fetch_payment_history(db: Session, user_id: int) -> list[PaymentTransaction]:
    """Repository helper: payment history newest first."""
    return list(
        db.scalars(
            select(PaymentTransaction)
            .options(joinedload(PaymentTransaction.plan))
            .where(PaymentTransaction.user_id == user_id)
            .order_by(
                PaymentTransaction.transaction_date.desc(),
                PaymentTransaction.id.desc(),
            )
        ).unique().all()
    )


def fetch_subscription_history(
    db: Session,
    user_id: int,
) -> list[SubscriptionHistory]:
    """Repository helper: subscription history newest first."""
    return list(
        db.scalars(
            select(SubscriptionHistory)
            .options(
                joinedload(SubscriptionHistory.old_plan),
                joinedload(SubscriptionHistory.new_plan),
            )
            .where(SubscriptionHistory.user_id == user_id)
            .order_by(
                SubscriptionHistory.changed_at.desc(),
                SubscriptionHistory.id.desc(),
            )
        ).unique().all()
    )


def fetch_invoices(db: Session, user_id: int) -> list[Invoice]:
    """Repository helper: invoices newest first."""
    return list(
        db.scalars(
            select(Invoice)
            .options(joinedload(Invoice.plan))
            .where(Invoice.user_id == user_id)
            .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        ).unique().all()
    )


def resolve_user_plan_with_master(
    db: Session,
    user_id: int,
) -> tuple[UserPlan, PlanMaster | None]:
    """Ensure user_plan exists and resolve linked plan_master row."""
    from app.modules.plan_master.utils import get_default_plan, get_plan_by_id, get_plan_by_name

    user_plan = ensure_user_plan_exists(db, user_id)
    plan: PlanMaster | None = None

    if user_plan.plan_id is not None:
        plan = get_plan_by_id(db, user_plan.plan_id)
    if plan is None and user_plan.plan_name:
        plan = get_plan_by_name(db, user_plan.plan_name)
    if plan is None:
        plan = get_default_plan(db)

    if user_plan.plan_id != plan.id or user_plan.chatbot_limit != plan.max_chatbots:
        user_plan.plan_id = plan.id
        user_plan.plan_name = plan.plan_name
        user_plan.chatbot_limit = plan.max_chatbots
        db.flush()

    return user_plan, plan
