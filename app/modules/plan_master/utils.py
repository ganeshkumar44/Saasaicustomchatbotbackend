"""Plan master helpers, seed data, migrations, and limit lookups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.plan_master.model import (
    BILLING_CYCLE_MONTHLY,
    DEFAULT_CURRENCY,
    PLAN_NAME_ENTERPRISE,
    PLAN_NAME_FREE,
    PLAN_NAME_PRO,
    PLAN_NAME_STARTER,
    PlanMaster,
)

logger = logging.getLogger(__name__)

DEFAULT_PLAN_NAME = PLAN_NAME_FREE

def _features_from_limits(
    *,
    max_chatbots: int,
    chatbot_message_limit: int | None,
    playground_message_limit: int | None,
    extra: list[str] | None = None,
) -> list[str]:
    """Build feature bullets from live plan_master limit columns."""
    website = (
        "Unlimited website messages/month"
        if chatbot_message_limit is None
        else f"{chatbot_message_limit:,} website messages/month"
    )
    playground = (
        "Unlimited playground messages/month"
        if playground_message_limit is None
        else f"{playground_message_limit:,} playground messages/month"
    )
    features = [
        f"{max_chatbots} chatbot" + ("s" if max_chatbots != 1 else ""),
        website,
        playground,
    ]
    if extra:
        features.extend(extra)
    return features


# Seed catalog. NULL message limits mean unlimited.
# Limits and prices are configurable via plan_master rows (never hardcode at runtime).
PLAN_MASTER_SEED: tuple[dict, ...] = (
    {
        "plan_name": PLAN_NAME_FREE,
        "max_chatbots": 1,
        "chatbot_message_limit": 200,
        "playground_message_limit": 50,
        "price": Decimal("0.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "monthly_price": Decimal("0.00"),
        "six_month_price": Decimal("0.00"),
        "yearly_price": Decimal("0.00"),
        "six_month_discount_percentage": Decimal("0.00"),
        "yearly_discount_percentage": Decimal("0.00"),
        "currency": DEFAULT_CURRENCY,
        "display_order": 1,
        "description": "Get started with a free plan for personal use.",
        "features": _features_from_limits(
            max_chatbots=1,
            chatbot_message_limit=200,
            playground_message_limit=50,
            extra=["Basic analytics", "Email support"],
        ),
        "is_active": True,
    },
    {
        "plan_name": PLAN_NAME_STARTER,
        "max_chatbots": 3,
        "chatbot_message_limit": 5000,
        "playground_message_limit": 50,
        "price": Decimal("499.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "monthly_price": Decimal("499.00"),
        "six_month_price": Decimal("2695.00"),
        "yearly_price": Decimal("4790.00"),
        "six_month_discount_percentage": Decimal("10.00"),
        "yearly_discount_percentage": Decimal("20.00"),
        "currency": DEFAULT_CURRENCY,
        "display_order": 2,
        "description": "For growing teams that need more capacity.",
        "features": _features_from_limits(
            max_chatbots=3,
            chatbot_message_limit=5000,
            playground_message_limit=50,
            extra=["Advance analytics", "Email support"],
        ),
        "is_active": True,
    },
    {
        "plan_name": PLAN_NAME_PRO,
        "max_chatbots": 6,
        "chatbot_message_limit": None,
        "playground_message_limit": 50,
        "price": Decimal("899.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "monthly_price": Decimal("899.00"),
        "six_month_price": Decimal("4855.00"),
        "yearly_price": Decimal("8630.00"),
        "six_month_discount_percentage": Decimal("10.00"),
        "yearly_discount_percentage": Decimal("20.00"),
        "currency": DEFAULT_CURRENCY,
        "display_order": 3,
        "description": "Unlimited website messages for serious product teams.",
        "features": _features_from_limits(
            max_chatbots=6,
            chatbot_message_limit=None,
            playground_message_limit=50,
            extra=["Advance analytics", "Priority email support"],
        ),
        "is_active": True,
    },
    {
        "plan_name": PLAN_NAME_ENTERPRISE,
        "max_chatbots": 15,
        "chatbot_message_limit": None,
        "playground_message_limit": None,
        "price": Decimal("1499.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "monthly_price": Decimal("1499.00"),
        "six_month_price": Decimal("8095.00"),
        "yearly_price": Decimal("14390.00"),
        "six_month_discount_percentage": Decimal("10.00"),
        "yearly_discount_percentage": Decimal("20.00"),
        "currency": DEFAULT_CURRENCY,
        "display_order": 4,
        "description": "Full capacity and unlimited usage for large organizations.",
        "features": _features_from_limits(
            max_chatbots=15,
            chatbot_message_limit=None,
            playground_message_limit=None,
            extra=["Advance analytics", "Dedicated support"],
        ),
        "is_active": True,
    },
)


@dataclass(frozen=True)
class PlanLimits:
    """Resolved plan limits for validation and API responses."""

    plan_id: int
    plan_name: str
    max_chatbots: int
    chatbot_message_limit: int | None
    playground_message_limit: int | None
    price: Decimal
    billing_cycle: str


def is_unlimited(limit: int | None) -> bool:
    """Return True when a limit value represents unlimited usage."""
    return limit is None


def get_plan_by_name(db: Session, plan_name: str) -> PlanMaster | None:
    """Return an active plan_master row by plan name."""
    return db.execute(
        select(PlanMaster).where(
            PlanMaster.plan_name == plan_name,
            PlanMaster.is_active.is_(True),
        )
    ).scalar_one_or_none()


def get_plan_by_id(db: Session, plan_id: int) -> PlanMaster | None:
    """Return a plan_master row by id."""
    return db.get(PlanMaster, plan_id)


def list_active_plans(db: Session) -> list[PlanMaster]:
    """Return active plans ordered for billing display."""
    return list(
        db.scalars(
            select(PlanMaster)
            .where(PlanMaster.is_active.is_(True))
            .order_by(PlanMaster.display_order.asc(), PlanMaster.id.asc())
        ).all()
    )


def plan_to_limits(plan: PlanMaster) -> PlanLimits:
    """Convert a PlanMaster ORM row into a PlanLimits DTO."""
    return PlanLimits(
        plan_id=plan.id,
        plan_name=plan.plan_name,
        max_chatbots=plan.max_chatbots,
        chatbot_message_limit=plan.chatbot_message_limit,
        playground_message_limit=plan.playground_message_limit,
        price=plan.monthly_price if plan.monthly_price is not None else plan.price,
        billing_cycle=plan.billing_cycle,
    )


def get_default_plan(db: Session) -> PlanMaster:
    """Return the Free plan, raising if seed data is missing."""
    plan = get_plan_by_name(db, DEFAULT_PLAN_NAME)
    if plan is None:
        raise RuntimeError(
            "Default Free plan is missing from plan_master. "
            "Ensure seed_plan_master() ran at startup."
        )
    return plan


def apply_plan_master_migrations(db_engine: Engine) -> None:
    """Add billing catalog columns to an existing plan_master table when missing."""
    inspector = inspect(db_engine)
    if "plan_master" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("plan_master")
    }
    statements: list[str] = []

    if "monthly_price" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN monthly_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00"
        )
    if "six_month_price" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN six_month_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00"
        )
    if "yearly_price" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN yearly_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00"
        )
    if "six_month_discount_percentage" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN six_month_discount_percentage DECIMAL(5, 2) "
            "NOT NULL DEFAULT 0.00"
        )
    if "yearly_discount_percentage" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN yearly_discount_percentage DECIMAL(5, 2) "
            "NOT NULL DEFAULT 0.00"
        )
    if "monthly_razorpay_plan_id" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN monthly_razorpay_plan_id VARCHAR(100)"
        )
    if "six_month_razorpay_plan_id" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN six_month_razorpay_plan_id VARCHAR(100)"
        )
    if "yearly_razorpay_plan_id" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN yearly_razorpay_plan_id VARCHAR(100)"
        )
    if "currency" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            f"ADD COLUMN currency VARCHAR(10) NOT NULL DEFAULT '{DEFAULT_CURRENCY}'"
        )
    if "display_order" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master "
            "ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0"
        )
    if "description" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master ADD COLUMN description TEXT"
        )
    if "features" not in existing_columns:
        statements.append(
            "ALTER TABLE plan_master ADD COLUMN features JSONB"
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    logger.info("Applied %s plan_master migration statement(s)", len(statements))


def seed_plan_master(db_engine: Engine) -> int:
    """
    Insert default plan_master rows when missing.

    Safe to run multiple times; never overwrites customized prices on existing rows.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created = 0

    try:
        for seed in PLAN_MASTER_SEED:
            existing = db.execute(
                select(PlanMaster).where(PlanMaster.plan_name == seed["plan_name"])
            ).scalar_one_or_none()
            if existing is not None:
                continue

            db.add(PlanMaster(**seed))
            created += 1

        if created:
            db.commit()
            logger.info("Seeded %s plan_master row(s)", created)
        else:
            logger.info("plan_master seed complete; no new rows")
    except Exception:
        db.rollback()
        logger.exception("Failed to seed plan_master")
        raise
    finally:
        db.close()

    return created


def backfill_plan_master_billing_fields(db_engine: Engine) -> int:
    """
    Fill missing catalog pricing / discount fields on plan_master from seed.

    Does not overwrite non-zero custom prices or discounts (editable later).
    Does not change max_chatbots or message limits. Savings are never stored.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    updated = 0
    seed_by_name = {item["plan_name"]: item for item in PLAN_MASTER_SEED}
    price_keys = (
        "price",
        "monthly_price",
        "six_month_price",
        "yearly_price",
    )
    discount_keys = (
        "six_month_discount_percentage",
        "yearly_discount_percentage",
    )

    try:
        plans = list(db.scalars(select(PlanMaster)).all())
        for plan in plans:
            seed = seed_by_name.get(plan.plan_name)
            if seed is None:
                if plan.monthly_price == Decimal("0.00") and plan.price != Decimal("0.00"):
                    plan.monthly_price = plan.price
                    updated += 1
                continue

            changed = False
            for key in price_keys:
                current = getattr(plan, key)
                new_value = seed[key]
                if current == Decimal("0.00") and new_value != Decimal("0.00"):
                    setattr(plan, key, new_value)
                    changed = True

            for key in discount_keys:
                current = getattr(plan, key)
                new_value = seed[key]
                if current == Decimal("0.00") and new_value != Decimal("0.00"):
                    setattr(plan, key, new_value)
                    changed = True

            if not plan.currency:
                plan.currency = seed["currency"]
                changed = True
            if plan.display_order == 0 and seed["display_order"]:
                plan.display_order = seed["display_order"]
                changed = True
            if plan.description is None and seed.get("description"):
                plan.description = seed["description"]
                changed = True
            if plan.features is None and seed.get("features") is not None:
                plan.features = seed["features"]
                changed = True

            if changed:
                updated += 1

        if updated:
            db.commit()
            logger.info(
                "Backfilled catalog pricing/discounts on %s plan_master row(s)",
                updated,
            )
    except Exception:
        db.rollback()
        logger.exception("Failed to backfill plan_master billing fields")
        raise
    finally:
        db.close()

    return updated
