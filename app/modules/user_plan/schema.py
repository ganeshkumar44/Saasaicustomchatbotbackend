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


class BillingPlanCatalogItem(BaseModel):
    """A subscription plan option exposed on billing endpoints."""

    plan_name: str
    display_name: str
    price: str | None = None
    billing_cycle: str | None = None
    chatbot_limit: int
    features: list[str]
    status: str
    is_popular: bool = False


class UserPlanBillingData(BaseModel):
    """Billing-focused subscription details for the authenticated user."""

    plan_name: str
    status: str
    current_billing: str
    next_billing_date: datetime | None = None
    billing_cycle: str | None = None
    plan_price: str | None = None
    chatbot_limit: int
    plans: list[BillingPlanCatalogItem]


class UserPlanBillingSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: UserPlanBillingData

