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
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


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
