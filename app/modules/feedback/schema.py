"""Feedback API schemas."""

from pydantic import BaseModel, EmailStr, Field


class CreateFeedbackRequest(BaseModel):
    """Request body for submitting website feedback."""

    rating: int = Field(..., description="Star rating from 1 to 5")
    name: str = Field(..., description="Submitter display name")
    email: EmailStr = Field(..., description="Submitter email address")
    phone_number: str | None = Field(
        default=None,
        description="Optional phone number",
    )
    message: str | None = Field(
        default=None,
        description="Optional feedback message",
    )


class CreateFeedbackSuccessResponse(BaseModel):
    """Success response after feedback is saved."""

    success: bool = True
    message: str
