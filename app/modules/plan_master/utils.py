"""Plan master helpers, seed data, and limit lookups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.plan_master.model import (
    BILLING_CYCLE_MONTHLY,
    PLAN_NAME_ENTERPRISE,
    PLAN_NAME_FREE,
    PLAN_NAME_PRO,
    PLAN_NAME_STARTER,
    PlanMaster,
)

logger = logging.getLogger(__name__)

DEFAULT_PLAN_NAME = PLAN_NAME_FREE

# Seed catalog. NULL message limits mean unlimited.
PLAN_MASTER_SEED: tuple[dict, ...] = (
    {
        "plan_name": PLAN_NAME_FREE,
        "max_chatbots": 1,
        "chatbot_message_limit": 200,
        "playground_message_limit": 50,
        "price": Decimal("0.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "is_active": True,
    },
    {
        "plan_name": PLAN_NAME_STARTER,
        "max_chatbots": 3,
        "chatbot_message_limit": 5000,
        "playground_message_limit": 50,
        "price": Decimal("29.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "is_active": True,
    },
    {
        "plan_name": PLAN_NAME_PRO,
        "max_chatbots": 6,
        "chatbot_message_limit": None,
        "playground_message_limit": 50,
        "price": Decimal("79.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
        "is_active": True,
    },
    {
        "plan_name": PLAN_NAME_ENTERPRISE,
        "max_chatbots": 15,
        "chatbot_message_limit": None,
        "playground_message_limit": None,
        "price": Decimal("299.00"),
        "billing_cycle": BILLING_CYCLE_MONTHLY,
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


def plan_to_limits(plan: PlanMaster) -> PlanLimits:
    """Convert a PlanMaster ORM row into a PlanLimits DTO."""
    return PlanLimits(
        plan_id=plan.id,
        plan_name=plan.plan_name,
        max_chatbots=plan.max_chatbots,
        chatbot_message_limit=plan.chatbot_message_limit,
        playground_message_limit=plan.playground_message_limit,
        price=plan.price,
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


def seed_plan_master(db_engine: Engine) -> int:
    """
    Insert default plan_master rows when missing.

    Safe to run multiple times; never updates existing rows.
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
