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
    SUBSCRIPTION_STATUS_ACTIVE,
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
    PLAN_PRO: 4,
    PLAN_ENTERPRISE: 10,
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
        "50 website messages/month",
        "20 playground messages/month",
        "Basic analytics",
        "Email support",
    ],
    PLAN_STARTER: [
        "5,000 website messages/month",
        "50 playground messages/month",
        "Advance analytics",
        "Email support",
    ],
    PLAN_PRO: [
        "10,000 website messages/month",
        "500 playground messages/month",
        "Advance analytics",
        "Email support",
    ],
    PLAN_ENTERPRISE: [
        "Unlimited website messages/month",
        "Unlimited playground messages/month",
        "Advance analytics",
        "Email support",
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


def get_user_plan_by_user_id(db: Session, user_id: int) -> UserPlan | None:
    """Return the user plan record for a user, if one exists."""
    return db.execute(
        select(UserPlan).where(UserPlan.user_id == user_id)
    ).scalar_one_or_none()


def build_default_user_plan(
    user_id: int,
    *,
    created_chatbots_count: int = 0,
    plan_name: str = DEFAULT_PLAN_NAME,
    status: str = PLAN_STATUS_ACTIVE,
    plan_id: int | None = None,
    chatbot_limit: int | None = None,
) -> UserPlan:
    """Build a default user plan record for a user."""
    resolved_limit = (
        chatbot_limit
        if chatbot_limit is not None
        else get_chatbot_limit_for_plan(plan_name)
    )
    now = datetime.now(timezone.utc)
    return UserPlan(
        user_id=user_id,
        plan_id=plan_id,
        plan_name=plan_name,
        chatbot_limit=resolved_limit,
        created_chatbots_count=created_chatbots_count,
        status=status,
        subscription_status=SUBSCRIPTION_STATUS_ACTIVE,
        start_date=now,
        end_date=None,
        subscription_start=now,
        subscription_end=None,
        current_billing=DEFAULT_CURRENT_BILLING,
        next_billing_date=None,
        billing_cycle=None,
        is_auto_renew=False,
        razorpay_customer_id=None,
        razorpay_subscription_id=None,
    )


def ensure_user_plan_exists(db: Session, user_id: int) -> UserPlan:
    """
    Return existing user plan for a user or create the default Free plan.

    Safe to call multiple times; never creates duplicate records.
    Links plan_id to plan_master when available.
    """
    existing = get_user_plan_by_user_id(db, user_id)
    if existing is not None:
        if existing.plan_id is None:
            from app.modules.plan_master.utils import get_plan_by_name

            plan = get_plan_by_name(db, existing.plan_name) or get_plan_by_name(
                db, DEFAULT_PLAN_NAME
            )
            if plan is not None:
                existing.plan_id = plan.id
                existing.chatbot_limit = plan.max_chatbots
                existing.plan_name = plan.plan_name
                db.flush()
        return existing

    plan_id = None
    chatbot_limit = get_chatbot_limit_for_plan(DEFAULT_PLAN_NAME)
    try:
        from app.modules.plan_master.utils import get_default_plan

        default_plan = get_default_plan(db)
        plan_id = default_plan.id
        chatbot_limit = default_plan.max_chatbots
    except Exception:
        logger.warning(
            "plan_master unavailable while creating user plan for user_id=%s; "
            "using legacy Free defaults",
            user_id,
        )

    user_plan = build_default_user_plan(
        user_id,
        plan_id=plan_id,
        chatbot_limit=chatbot_limit,
    )
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
    """Add billing / plan_id columns to existing user_plan tables when missing."""
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
    if "plan_id" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan ADD COLUMN plan_id INTEGER"
        )
        statements.append(
            "CREATE INDEX IF NOT EXISTS ix_user_plan_plan_id ON user_plan (plan_id)"
        )
        statements.append(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'plan_master') "
            "AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'user_plan_plan_id_fkey' "
            "AND table_name = 'user_plan') THEN "
            "ALTER TABLE user_plan ADD CONSTRAINT user_plan_plan_id_fkey "
            "FOREIGN KEY (plan_id) REFERENCES plan_master(id) ON DELETE SET NULL; "
            "END IF; END $$;"
        )
    if "subscription_status" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN subscription_status VARCHAR(20) NOT NULL DEFAULT 'active'"
        )
    if "subscription_start" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN subscription_start TIMESTAMP WITH TIME ZONE"
        )
    if "subscription_end" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN subscription_end TIMESTAMP WITH TIME ZONE"
        )
    if "is_auto_renew" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN is_auto_renew BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "razorpay_customer_id" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN razorpay_customer_id VARCHAR(100)"
        )
    if "razorpay_subscription_id" not in existing_columns:
        statements.append(
            "ALTER TABLE user_plan "
            "ADD COLUMN razorpay_subscription_id VARCHAR(100)"
        )
        statements.append(
            "CREATE INDEX IF NOT EXISTS ix_user_plan_razorpay_subscription_id "
            "ON user_plan (razorpay_subscription_id)"
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    logger.info("Applied %s user_plan migration statement(s)", len(statements))


def backfill_user_plan_subscription_fields(db_engine: Engine) -> int:
    """Backfill subscription_* fields from legacy status / start_date columns."""
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    updated = 0

    try:
        rows = list(db.scalars(select(UserPlan)).all())
        for row in rows:
            changed = False
            if not row.subscription_status:
                row.subscription_status = row.status or SUBSCRIPTION_STATUS_ACTIVE
                changed = True
            if row.subscription_start is None and row.start_date is not None:
                row.subscription_start = row.start_date
                changed = True
            if row.subscription_end is None and row.end_date is not None:
                row.subscription_end = row.end_date
                changed = True
            if changed:
                updated += 1

        if updated:
            db.commit()
            logger.info(
                "Backfilled subscription fields on %s user_plan row(s)",
                updated,
            )
    except Exception:
        db.rollback()
        logger.exception("Failed to backfill user_plan subscription fields")
        raise
    finally:
        db.close()

    return updated


def backfill_user_plan_plan_ids(db_engine: Engine) -> int:
    """Link existing user_plan rows to plan_master by plan_name."""
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    updated = 0

    try:
        from app.modules.plan_master.model import PlanMaster

        plans = {
            plan.plan_name: plan
            for plan in db.scalars(select(PlanMaster)).all()
        }
        if not plans:
            return 0

        rows = db.scalars(
            select(UserPlan).where(UserPlan.plan_id.is_(None))
        ).all()

        for row in rows:
            plan = plans.get(row.plan_name) or plans.get(DEFAULT_PLAN_NAME)
            if plan is None:
                continue
            row.plan_id = plan.id
            row.chatbot_limit = plan.max_chatbots
            row.plan_name = plan.plan_name
            updated += 1

        if updated:
            db.commit()
            logger.info("Backfilled plan_id on %s user_plan row(s)", updated)
    except Exception:
        db.rollback()
        logger.exception("Failed to backfill user_plan.plan_id")
        raise
    finally:
        db.close()

    return updated

