"""
User plan helper utilities and plan constants.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import USER_ROLE_ADMIN, USER_ROLE_SUPERADMIN
from app.modules.chatbot.model import Chatbot
from app.modules.user_plan.model import (
    DEFAULT_CURRENT_BILLING,
    PLAN_STATUS_ACTIVE,
    UserPlan,
)
from app.modules.user_plan.schema import (
    BillingPlanCatalogItem,
    UserPlanBillingData,
    UserPlanSummaryData,
)

logger = logging.getLogger(__name__)

PLAN_FREE = "free"
PLAN_STARTER = "starter"
PLAN_PRO = "pro"
PLAN_ENTERPRISE = "enterprise"

PLAN_CHATBOT_LIMITS: dict[str, int] = {
    PLAN_FREE: 1,
    PLAN_STARTER: 3,
    PLAN_PRO: 6,
    PLAN_ENTERPRISE: 20,
}

PLAN_DISPLAY_NAMES: dict[str, str] = {
    PLAN_FREE: "Free",
    PLAN_STARTER: "Starter",
    PLAN_PRO: "Pro",
    PLAN_ENTERPRISE: "Enterprise",
}

PLAN_CATALOG_ORDER: tuple[str, ...] = (
    PLAN_FREE,
    PLAN_STARTER,
    PLAN_PRO,
    PLAN_ENTERPRISE,
)

PLAN_PRICES: dict[str, str] = {
    PLAN_FREE: "0.00",
    PLAN_STARTER: "29.00",
    PLAN_PRO: "79.00",
    PLAN_ENTERPRISE: "299.00",
}

PLAN_BILLING_CYCLES: dict[str, str] = {
    PLAN_FREE: "free",
    PLAN_STARTER: "monthly",
    PLAN_PRO: "monthly",
    PLAN_ENTERPRISE: "monthly",
}

PLAN_FEATURES: dict[str, list[str]] = {
    PLAN_FREE: [
        "1 chatbot",
        "Basic analytics",
        "Email support",
        "7-day chat history",
    ],
    PLAN_STARTER: [
        "1,000 conversations/month",
        "3 chatbots",
        "Basic analytics",
        "Email support",
        "7-day chat history",
    ],
    PLAN_PRO: [
        "10,000 conversations/month",
        "6 chatbots",
        "Advanced analytics",
        "Priority support",
        "Unlimited chat history",
        "Custom branding",
    ],
    PLAN_ENTERPRISE: [
        "Unlimited conversations",
        "20 chatbots",
        "Custom analytics",
        "Dedicated support",
        "Unlimited chat history",
        "Custom branding",
        "API access",
        "SSO & SAML",
    ],
}

PLAN_CATALOG_STATUS_AVAILABLE = "available"

DEFAULT_PLAN_NAME = PLAN_FREE


def get_chatbot_limit_for_plan(plan_name: str) -> int:
    """Return the chatbot creation limit for a supported plan name."""
    return PLAN_CHATBOT_LIMITS.get(plan_name, PLAN_CHATBOT_LIMITS[DEFAULT_PLAN_NAME])


def get_plan_display_name(plan_name: str) -> str:
    """Return a user-facing label for a stored plan name."""
    return PLAN_DISPLAY_NAMES.get(plan_name, plan_name.title())


def build_chatbot_creation_limit_message(plan_name: str) -> str:
    """Build the chatbot creation limit error message for a plan."""
    return messages.CHATBOT_CREATION_LIMIT_REACHED.format(
        plan_name=get_plan_display_name(plan_name),
    )


def has_unlimited_chatbot_creation(user: User) -> bool:
    """Return True when the user's role bypasses plan chatbot limits."""
    return user.role in {USER_ROLE_SUPERADMIN, USER_ROLE_ADMIN}


def count_user_chatbots_ever_created(db: Session, user_id: int) -> int:
    """Count all chatbots ever created by a user, including soft-deleted rows."""
    return int(
        db.execute(
            select(func.count(Chatbot.id)).where(Chatbot.user_id == user_id)
        ).scalar_one()
    )


def serialize_user_plan_summary(
    user_plan: UserPlan,
    *,
    has_draft: bool = False,
    draft_chatbot_id: int | None = None,
) -> UserPlanSummaryData:
    """Serialize a user plan record for API responses."""
    return UserPlanSummaryData(
        plan_name=user_plan.plan_name,
        chatbot_limit=user_plan.chatbot_limit,
        created_chatbots_count=user_plan.created_chatbots_count,
        status=user_plan.status,
        start_date=user_plan.start_date,
        end_date=user_plan.end_date,
        has_draft=has_draft,
        draft_chatbot_id=draft_chatbot_id,
    )


def format_current_billing_amount(amount: Decimal) -> str:
    """Format a billing amount as a fixed two-decimal string."""
    return f"{amount:.2f}"


def build_plan_catalog() -> list[BillingPlanCatalogItem]:
    """Return the ordered list of subscription plans for billing pages."""
    catalog: list[BillingPlanCatalogItem] = []

    for plan_name in PLAN_CATALOG_ORDER:
        catalog.append(
            BillingPlanCatalogItem(
                plan_name=plan_name,
                display_name=get_plan_display_name(plan_name),
                price=PLAN_PRICES.get(plan_name),
                billing_cycle=PLAN_BILLING_CYCLES.get(plan_name),
                chatbot_limit=get_chatbot_limit_for_plan(plan_name),
                features=PLAN_FEATURES.get(plan_name, []),
                status=PLAN_CATALOG_STATUS_AVAILABLE,
                is_popular=plan_name == PLAN_PRO,
            )
        )

    return catalog


def serialize_user_plan_billing(user_plan: UserPlan) -> UserPlanBillingData:
    """Serialize billing fields from a user plan record."""
    billing_cycle = user_plan.billing_cycle or PLAN_BILLING_CYCLES.get(
        user_plan.plan_name,
    )

    return UserPlanBillingData(
        plan_name=user_plan.plan_name,
        status=user_plan.status,
        current_billing=format_current_billing_amount(user_plan.current_billing),
        next_billing_date=user_plan.next_billing_date,
        billing_cycle=billing_cycle,
        plan_price=PLAN_PRICES.get(user_plan.plan_name),
        chatbot_limit=user_plan.chatbot_limit,
        plans=build_plan_catalog(),
    )


def build_default_user_plan(
    user_id: int,
    *,
    created_chatbots_count: int = 0,
    plan_name: str = DEFAULT_PLAN_NAME,
    status: str = PLAN_STATUS_ACTIVE,
) -> UserPlan:
    """Build a default user plan record for a user."""
    return UserPlan(
        user_id=user_id,
        plan_name=plan_name,
        chatbot_limit=get_chatbot_limit_for_plan(plan_name),
        created_chatbots_count=created_chatbots_count,
        status=status,
        start_date=datetime.now(timezone.utc),
        end_date=None,
        current_billing=DEFAULT_CURRENT_BILLING,
        next_billing_date=None,
        billing_cycle=None,
    )


def get_user_plan_by_user_id(db: Session, user_id: int) -> UserPlan | None:
    """Return the user plan record for a user, if one exists."""
    return db.execute(
        select(UserPlan).where(UserPlan.user_id == user_id)
    ).scalar_one_or_none()


def ensure_user_plan_exists(db: Session, user_id: int) -> UserPlan:
    """
    Return existing user plan for a user or create the default Free plan.

    Safe to call multiple times; never creates duplicate records.
    """
    existing = get_user_plan_by_user_id(db, user_id)
    if existing is not None:
        return existing

    user_plan = build_default_user_plan(user_id)
    db.add(user_plan)
    db.commit()
    db.refresh(user_plan)

    logger.info("Created default user plan for user_id=%s", user_id)
    return user_plan


def sync_existing_user_plans(db_engine: Engine) -> int:
    """
    Create missing user_plan records for existing users.

    Existing chatbot totals are calculated from all chatbot rows, including
    soft-deleted chatbots. Safe to run multiple times.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created_count = 0

    try:
        missing_user_ids = db.execute(
            select(User.id)
            .outerjoin(UserPlan, User.id == UserPlan.user_id)
            .where(UserPlan.id.is_(None))
        ).scalars().all()

        for user_id in missing_user_ids:
            created_count_value = count_user_chatbots_ever_created(db, user_id)
            db.add(
                build_default_user_plan(
                    user_id,
                    created_chatbots_count=created_count_value,
                )
            )
            created_count += 1

        if created_count:
            db.commit()
            logger.info(
                "Synchronized %s missing user plan records",
                created_count,
            )
        else:
            logger.info(
                "User plan synchronization complete; no missing records",
            )
    except Exception:
        db.rollback()
        logger.exception("Failed to synchronize existing user plans")
        raise
    finally:
        db.close()

    return created_count


def apply_user_plan_migrations(db_engine: Engine) -> None:
    """Add billing columns to existing user_plan tables when missing."""
    inspector = inspect(db_engine)
    if "user_plan" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("user_plan")
    }
    statements: list[str] = []

    if "current_billing" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN current_billing DECIMAL(10, 2) NOT NULL DEFAULT 0.00"
        )
    if "next_billing_date" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN next_billing_date TIMESTAMP WITH TIME ZONE"
        )
    if "billing_cycle" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan ADD COLUMN billing_cycle VARCHAR(20)"
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    logger.info("Applied %s user_plan billing migration statement(s)", len(statements))

