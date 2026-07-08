"""Login history API schemas."""

from datetime import datetime

from pydantic import BaseModel


class UserLoginHistoryItem(BaseModel):
    id: int
    login_at: datetime
    logout_at: datetime | None
    browser: str | None
    operating_system: str | None
    device_type: str | None
    ip_address: str | None
    country: str | None
    city: str | None
    login_status: str
    is_current_session: bool


class UserLoginHistorySuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: list[UserLoginHistoryItem]


class ManageLoginHistoryItem(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None
    email: str | None
    role: str | None
    login_at: datetime
    logout_at: datetime | None
    browser: str | None
    operating_system: str | None
    device_type: str | None
    ip_address: str | None
    country: str | None
    city: str | None
    login_status: str
    is_current_session: bool


class ManageLoginHistorySuccessResponse(BaseModel):
    success: bool = True
    message: str
    page: int
    per_page: int
    total_records: int
    total_pages: int
    data: list[ManageLoginHistoryItem]
