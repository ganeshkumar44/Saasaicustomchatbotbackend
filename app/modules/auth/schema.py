from typing import Any

from pydantic import BaseModel, EmailStr, Field, model_validator


class AuthResponse(BaseModel):
    status: bool
    message: str


class SignupRequest(BaseModel):
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: str = Field(..., description="Unique email address")
    mobile: str = Field(..., description="User's mobile number")
    password: str = Field(..., description="Account password")
    confirm_password: str = Field(..., description="Password confirmation")

    @model_validator(mode="before")
    @classmethod
    def normalize_signup_input(cls, data: Any) -> Any:
        """Trim whitespace and lowercase the email before field validation."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        for key in ("first_name", "last_name", "mobile"):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = value.strip()

        email = normalized.get("email")
        if isinstance(email, str):
            normalized["email"] = email.strip().lower()

        return normalized


class SignupUserData(BaseModel):
    id: int
    first_name: str
    last_name: str | None
    email: str


class SignupSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: SignupUserData


class VerifyEmailRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    verification_code: str = Field(..., description="6-digit verification code")

    @model_validator(mode="before")
    @classmethod
    def normalize_verify_email_input(cls, data: Any) -> Any:
        """Trim whitespace from email and verification code before validation."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        verification_code = normalized.get("verification_code")
        if isinstance(verification_code, str):
            normalized["verification_code"] = verification_code.strip()

        email = normalized.get("email")
        if isinstance(email, str):
            normalized["email"] = email.strip().lower()

        return normalized


class VerifyEmailSuccessResponse(BaseModel):
    success: bool = True
    message: str


class SignupResendVerificationRequest(BaseModel):
    email: str = Field(..., description="Registered email address")

    @model_validator(mode="before")
    @classmethod
    def normalize_resend_verification_input(cls, data: Any) -> Any:
        """Trim whitespace and lowercase the email before validation."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        email = normalized.get("email")
        if isinstance(email, str):
            normalized["email"] = email.strip().lower()

        return normalized


class SignupResendVerificationResponse(BaseModel):
    success: bool = True
    message: str


class ForgotPasswordEmailRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")


class ForgotPasswordEmailSuccessResponse(BaseModel):
    success: bool = True
    message: str


class ForgotPasswordVerifyCodeRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit forgot-password verification code",
    )


class ForgotPasswordVerifyCodeSuccessResponse(BaseModel):
    success: bool = True
    message: str


class ForgotPasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    new_password: str = Field(..., min_length=1, description="New account password")
    confirm_password: str = Field(..., min_length=1, description="New password confirmation")


class ForgotPasswordResetSuccessResponse(BaseModel):
    success: bool = True
    message: str


class LoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")

    @model_validator(mode="before")
    @classmethod
    def normalize_signin_input(cls, data: Any) -> Any:
        """Trim whitespace and lowercase the email before validation."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        email = normalized.get("email")
        if isinstance(email, str):
            normalized["email"] = email.strip().lower()

        return normalized


class LoginUserData(BaseModel):
    id: int
    first_name: str
    last_name: str | None
    email: str
    role: str
    is_email_verified: bool


class LoginSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: LoginUserData
    access_token: str
    token_type: str = "Bearer"


class MeUserData(BaseModel):
    id: int
    first_name: str
    last_name: str | None
    email: str
    role: str


class MeSuccessResponse(BaseModel):
    success: bool = True
    data: MeUserData
