"""
Manage Users module Pydantic schemas.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ManageUserListItem(BaseModel):
    """User row returned by the manage-users listing endpoint."""

    user_id: int
    first_name: str
    last_name: str
    full_name: str
    email: str
    mobile: str | None
    company: str | None
    website: str | None
    language: str | None
    profile_image: str | None
    role: str
    account_status: str
    email_verified: bool
    mobile_verified: bool
    total_chatbots: int
    created_at: datetime
    updated_at: datetime


class ManageUsersListSuccessResponse(BaseModel):
    """Paginated response for the manage-users listing endpoint."""

    success: bool = True
    message: str
    page: int
    per_page: int
    total_records: int
    total_pages: int
    data: list[ManageUserListItem]


class UpdateUserStatusRequest(BaseModel):
    """Request payload for changing a user's account status."""

    action: Literal["activate", "deactivate", "delete"]


class UpdateUserStatusSuccessResponse(BaseModel):
    """Response after updating a user's account status."""

    success: bool = True
    message: str
    user_id: int
    account_status: str


class UpdateManageUserRequest(BaseModel):
    """Request payload for updating a user's profile fields."""

    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    email: str = Field(..., description="User email address")
    mobile: str = Field(..., description="User mobile number")
    company: str | None = Field(default=None, description="Optional company name")
    website: str | None = Field(default=None, description="Optional website URL")
    language: str = Field(..., description="Preferred language")
    bio: str | None = Field(default=None, description="Optional user biography")
    role: str = Field(..., description="User role")


class UpdateManageUserSuccessResponse(BaseModel):
    """Response after updating a user's profile."""

    success: bool = True
    message: str
    data: ManageUserListItem
