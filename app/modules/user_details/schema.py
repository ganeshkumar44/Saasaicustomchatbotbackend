from datetime import datetime
from typing import Annotated

from fastapi import UploadFile
from pydantic import BaseModel, Field, WithJsonSchema

# Swagger UI renders multipart file fields as "Choose File" when format is binary.
SwaggerUploadFile = Annotated[
    UploadFile,
    WithJsonSchema({"type": "string", "format": "binary"}),
]


class UserDetailsData(BaseModel):
    """Merged profile data from users and user_details tables."""

    id: int
    first_name: str
    last_name: str
    email: str
    mobile: str | None
    role: str
    is_email_verified: bool
    is_mobile_verified: bool
    is_active: bool
    profile_image: str | None
    company: str | None
    website: str | None
    language: str
    bio: str | None
    created_at: datetime
    updated_at: datetime
    profile_created_at: datetime
    profile_updated_at: datetime


class UserDetailsSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: UserDetailsData


class UpdatePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current account password")
    new_password: str = Field(..., description="New account password")
    confirm_new_password: str = Field(..., description="Confirmation of new password")


class UpdatePasswordSuccessResponse(BaseModel):
    success: bool = True
    message: str


class UpdateUserDetailsRequest(BaseModel):
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    email: str = Field(..., description="User email address")
    mobile: str = Field(..., description="User mobile number")
    company: str | None = Field(default=None, description="Optional company name")
    website: str | None = Field(default=None, description="Optional website URL")
    language: str = Field(..., description="Preferred language")
    bio: str | None = Field(default=None, description="Optional user biography")


class UpdateUserDetailsSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: UserDetailsData | None = None


class DeleteAccountRequest(BaseModel):
    user_id: int | None = Field(
        default=None,
        description="Target user ID (admin only; defaults to the authenticated user)",
    )


class DeleteAccountSuccessResponse(BaseModel):
    success: bool = True
    message: str


class DeactivateAccountRequest(BaseModel):
    user_id: int | None = Field(
        default=None,
        description="Target user ID (admin only; defaults to the authenticated user)",
    )


class DeactivateAccountSuccessResponse(BaseModel):
    success: bool = True
    message: str


class ActivateAccountRequest(BaseModel):
    user_id: int = Field(..., description="Target user ID to activate")


class ActivateAccountSuccessResponse(BaseModel):
    success: bool = True
    message: str
