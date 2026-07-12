"""Plan master service helpers."""

from sqlalchemy.orm import Session

from app.modules.plan_master.utils import (
    PlanLimits,
    get_default_plan,
    get_plan_by_id,
    get_plan_by_name,
    plan_to_limits,
)
from app.modules.user_plan.utils import ensure_user_plan_exists


def get_plan_limits(db: Session, user_id: int) -> PlanLimits:
    """
    Resolve subscription limits for a user from plan_master.

    Prefers user_plan.plan_id, then plan_name, then the default Free plan.
    """
    user_plan = ensure_user_plan_exists(db, user_id)

    plan = None
    if getattr(user_plan, "plan_id", None):
        plan = get_plan_by_id(db, user_plan.plan_id)

    if plan is None and user_plan.plan_name:
        plan = get_plan_by_name(db, user_plan.plan_name)

    if plan is None:
        plan = get_default_plan(db)

    # Keep denormalized columns aligned for legacy API consumers.
    if user_plan.plan_id != plan.id or user_plan.chatbot_limit != plan.max_chatbots:
        user_plan.plan_id = plan.id
        user_plan.plan_name = plan.plan_name
        user_plan.chatbot_limit = plan.max_chatbots
        db.flush()

    return plan_to_limits(plan)
