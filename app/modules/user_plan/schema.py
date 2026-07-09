"""User plan API schemas."""

from datetime import datetime

from pydantic import BaseModel


class UserPlanSummaryData(BaseModel):
    """Subscription plan summary exposed on user profile endpoints."""

    plan_name: str
    chatbot_limit: int
    created_chatbots_count: int
    status: str
    start_date: datetime
    end_date: datetime | None = None
