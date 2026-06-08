from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.auth.schema import (
    ForgotPasswordEmailRequest,
    ForgotPasswordEmailSuccessResponse,
    ForgotPasswordResetRequest,
    ForgotPasswordResetSuccessResponse,
    ForgotPasswordVerifyCodeRequest,
    ForgotPasswordVerifyCodeSuccessResponse,
    SignupRequest,
    SignupSuccessResponse,
    SignupUserData,
    VerifyEmailRequest,
    VerifyEmailSuccessResponse,
)
from app.modules.auth.utils import (
    generate_verification_code,
    get_verification_code_expiry,
    hash_password,
    is_code_expired,
    send_forgot_password_email,
    send_verification_email,
)


class PasswordMismatchError(Exception):
    """Raised when password and confirm_password do not match."""


class EmailAlreadyRegisteredError(Exception):
    """Raised when the email is already associated with a verified account."""


class InvalidVerificationCodeError(Exception):
    """Raised when the verification code is missing or does not match."""


class ExpiredVerificationCodeError(Exception):
    """Raised when the verification code has expired."""


class EmailAlreadyVerifiedError(Exception):
    """Raised when the email address is already verified."""


class EmailNotFoundError(Exception):
    """Raised when no user exists for the provided email address."""


class ForgotPasswordNotVerifiedError(Exception):
    """Raised when forgot-password code has not been verified yet."""


def auth_service():
    return {
        "status": True,
        "message": "Auth Service Running",
    }


def _build_signup_response(user: User) -> SignupSuccessResponse:
    return SignupSuccessResponse(
        message="User registered successfully",
        data=SignupUserData(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name or None,
            email=user.email,
        ),
    )


def _assign_verification_details(user: User) -> str:
    """Generate and attach a fresh OTP to the user."""
    verification_code = generate_verification_code()
    user.verification_code = verification_code
    user.verification_code_expires_at = get_verification_code_expiry()
    user.is_email_verified = False
    return verification_code


def register_user(db: Session, payload: SignupRequest) -> SignupSuccessResponse:
    """Register a new user with hashed password and default role/settings."""
    if payload.password != payload.confirm_password:
        raise PasswordMismatchError()

    normalized_email = str(payload.email).lower()

    existing_user = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    verification_code = generate_verification_code()

    if existing_user:
        if existing_user.is_email_verified:
            raise EmailAlreadyRegisteredError()

        # Allow re-signup for unverified accounts: refresh details and resend OTP.
        existing_user.first_name = payload.first_name.strip()
        existing_user.last_name = (payload.last_name or "").strip()
        existing_user.mobile = payload.mobile
        existing_user.password_hash = hash_password(payload.password)
        verification_code = _assign_verification_details(existing_user)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise EmailAlreadyRegisteredError() from exc

        db.refresh(existing_user)
        send_verification_email(
            existing_user.first_name,
            existing_user.email,
            verification_code,
        )
        return _build_signup_response(existing_user)

    user = User(
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip(),
        email=normalized_email,
        mobile=payload.mobile,
        password_hash=hash_password(payload.password),
        role="user",
        is_email_verified=False,
        verification_code=verification_code,
        verification_code_expires_at=get_verification_code_expiry(),
        is_mobile_verified=False,
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegisteredError() from exc

    db.refresh(user)
    send_verification_email(user.first_name, user.email, verification_code)

    return _build_signup_response(user)


def verify_user_email(
    db: Session,
    payload: VerifyEmailRequest,
) -> VerifyEmailSuccessResponse:
    """Validate the submitted OTP and mark the user's email as verified."""
    user = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()

    if not user:
        raise InvalidVerificationCodeError()

    if user.is_email_verified:
        raise EmailAlreadyVerifiedError()

    submitted_code = payload.verification_code.strip()
    if not user.verification_code or user.verification_code != submitted_code:
        raise InvalidVerificationCodeError()

    if not user.verification_code_expires_at:
        raise InvalidVerificationCodeError()

    expires_at = user.verification_code_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise ExpiredVerificationCodeError()

    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None

    db.commit()

    return VerifyEmailSuccessResponse(message="Email verified successfully")


def request_forgot_password_code(
    db: Session,
    payload: ForgotPasswordEmailRequest,
) -> ForgotPasswordEmailSuccessResponse:
    """Generate and email a forgot-password verification code."""
    user = db.execute(
        select(User).where(User.email == str(payload.email).lower())
    ).scalar_one_or_none()

    if not user:
        raise EmailNotFoundError()

    verification_code = generate_verification_code()
    user.forgot_password_code = verification_code
    user.forgot_password_code_expires_at = get_verification_code_expiry()
    user.forgot_password_verified = False

    db.commit()
    send_forgot_password_email(user.email, verification_code)

    return ForgotPasswordEmailSuccessResponse(
        message="Verification code sent successfully",
    )


def verify_forgot_password_code(
    db: Session,
    payload: ForgotPasswordVerifyCodeRequest,
) -> ForgotPasswordVerifyCodeSuccessResponse:
    """Validate the forgot-password verification code sent to the user's email."""
    user = db.execute(
        select(User).where(User.email == str(payload.email).lower())
    ).scalar_one_or_none()

    if not user:
        raise InvalidVerificationCodeError()

    submitted_code = payload.verification_code.strip()
    if not user.forgot_password_code or user.forgot_password_code != submitted_code:
        raise InvalidVerificationCodeError()

    if is_code_expired(user.forgot_password_code_expires_at):
        raise ExpiredVerificationCodeError()

    user.forgot_password_verified = True
    db.commit()

    return ForgotPasswordVerifyCodeSuccessResponse(
        message="Verification code verified successfully",
    )


def reset_forgot_password(
    db: Session,
    payload: ForgotPasswordResetRequest,
) -> ForgotPasswordResetSuccessResponse:
    """Reset the user's password after forgot-password verification."""
    if payload.new_password != payload.confirm_password:
        raise PasswordMismatchError()

    user = db.execute(
        select(User).where(User.email == str(payload.email).lower())
    ).scalar_one_or_none()

    if not user:
        raise EmailNotFoundError()

    if not user.forgot_password_verified:
        raise ForgotPasswordNotVerifiedError()

    user.password_hash = hash_password(payload.new_password)
    user.forgot_password_code = None
    user.forgot_password_code_expires_at = None
    user.forgot_password_verified = False

    db.commit()

    return ForgotPasswordResetSuccessResponse(message="Password reset successfully")
