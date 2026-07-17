"""Pydantic schemas for public contact submissions."""

from pydantic import BaseModel, EmailStr, Field


class CreateContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    company: str = Field(..., min_length=1, max_length=150)
    phone_number: str | None = Field(default=None, max_length=20)
    subject: str = Field(..., min_length=1, max_length=150)
    message: str = Field(..., min_length=10, max_length=2000)
    # Honeypot field — bots fill this; humans leave it empty.
    website: str | None = Field(default=None, max_length=200)


class CreateContactSuccessResponse(BaseModel):
    success: bool = True
    message: str
