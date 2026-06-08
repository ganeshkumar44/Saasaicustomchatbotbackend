from pydantic import BaseModel, EmailStr, Field


class AuthResponse(BaseModel):
    status: bool
    message: str


class SignupRequest(BaseModel):
    first_name: str = Field(..., min_length=1, description="User's first name")
    last_name: str | None = Field(default=None, description="User's last name")
    email: EmailStr = Field(..., description="Unique email address")
    mobile: str | None = Field(default=None, description="User's mobile number")
    password: str = Field(..., min_length=1, description="Account password")
    confirm_password: str = Field(..., min_length=1, description="Password confirmation")


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
    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit verification code",
    )


class VerifyEmailSuccessResponse(BaseModel):
    success: bool = True
    message: str
