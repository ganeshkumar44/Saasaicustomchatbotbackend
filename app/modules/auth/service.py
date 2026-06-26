from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.schema import (
    ForgotPasswordEmailRequest,
    ForgotPasswordEmailSuccessResponse,
    ForgotPasswordResetRequest,
    ForgotPasswordResetSuccessResponse,
    ForgotPasswordVerifyCodeRequest,
    ForgotPasswordVerifyCodeSuccessResponse,
    LoginRequest,
    LoginSuccessResponse,
    LoginUserData,
    MeSuccessResponse,
    MeUserData,
    SignupRequest,
    SignupResendVerificationRequest,
    SignupResendVerificationResponse,
    SignupSuccessResponse,
    SignOutSuccessResponse,
    SignupUserData,
    VerifyEmailRequest,
    VerifyEmailSuccessResponse,
)
from app.modules.auth.utils import (
    blacklist_token,
    create_access_token,
    generate_verification_code,
    get_token_identifier,
    get_verification_code_expiry,
    hash_password,
    is_code_expired,
    normalize_email,
    normalize_signup_fields,
    normalize_verification_code,
    send_forgot_password_email,
    send_verification_email,
    validate_email,
    validate_signin_request,
    validate_signup_request,
    validate_verification_code,
    verify_password,
)
from app.modules.user_details.utils import ensure_user_details_exists

logger = logging.getLogger(__name__)


class SignupValidationError(Exception):
    """Raised when signup payload fails field validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class VerificationValidationError(Exception):
    """Raised when verification payload fails field validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class SigninValidationError(Exception):
    """Raised when sign-in payload fails field validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class PasswordMismatchError(Exception):
    """Raised when password and confirm_password do not match."""


class EmailAlreadyRegisteredError(Exception):
    """Raised when the email is already associated with a verified account."""


class MobileAlreadyRegisteredError(Exception):
    """Raised when the mobile number is already associated with another account."""


class InvalidVerificationCodeError(Exception):
    """Raised when the verification code is missing or does not match."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.VERIFICATION_CODE_INVALID
        super().__init__(self.message)


class ExpiredVerificationCodeError(Exception):
    """Raised when the verification code has expired."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.VERIFICATION_CODE_EXPIRED
        super().__init__(self.message)


class EmailAlreadyVerifiedError(Exception):
    """Raised when the email address is already verified."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.USER_ALREADY_VERIFIED
        super().__init__(self.message)


class EmailNotFoundError(Exception):
    """Raised when no user exists for the provided email address."""


class SignupResendUserNotFoundError(Exception):
    """Raised when resend verification is requested for an unknown email."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.USER_NOT_FOUND
        super().__init__(self.message)


class VerificationCodeNotExpiredError(Exception):
    """Raised when an active verification code already exists."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.VERIFICATION_CODE_NOT_EXPIRED
        super().__init__(self.message)


class ForgotPasswordNotVerifiedError(Exception):
    """Raised when forgot-password code has not been verified yet."""


class LoginUserNotFoundError(Exception):
    """Raised when login email does not match any user."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.INVALID_CREDENTIALS
        super().__init__(self.message)


class LoginInvalidPasswordError(Exception):
    """Raised when the submitted login password is incorrect."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.INVALID_CREDENTIALS
        super().__init__(self.message)


class AccountDisabledError(Exception):
    """Raised when the user account is inactive."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.ACCOUNT_INACTIVE
        super().__init__(self.message)


class EmailNotVerifiedForLoginError(Exception):
    """Raised when the user attempts login before verifying email."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.ACCOUNT_NOT_VERIFIED
        super().__init__(self.message)


class SignoutError(Exception):
    """Raised when sign-out fails due to an unexpected error."""


def auth_service():
    return {
        "status": True,
        "message": "Auth Service Running",
    }


def _build_signup_response(user: User) -> SignupSuccessResponse:
    return SignupSuccessResponse(
        message=messages.USER_CREATED_SUCCESSFULLY,
        data=SignupUserData(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name or None,
            email=user.email,
        ),
    )


def _validate_signup_payload(payload: SignupRequest) -> None:
    """Validate signup fields and raise SignupValidationError on failure."""
    validation_error = validate_signup_request(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        mobile=payload.mobile,
        password=payload.password,
        confirm_password=payload.confirm_password,
    )
    if validation_error:
        raise SignupValidationError(validation_error)


def _mobile_belongs_to_other_user(
    db: Session,
    mobile: str,
    *,
    exclude_user_id: int | None = None,
) -> bool:
    """Return True when the mobile number belongs to a different user."""
    query = select(User).where(User.mobile == mobile)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)

    return db.execute(query).scalar_one_or_none() is not None


def _validate_verification_code_field(verification_code: str) -> str:
    """Validate verification code format and return the normalized value."""
    validation_error = validate_verification_code(verification_code)
    if validation_error:
        raise VerificationValidationError(validation_error)

    return normalize_verification_code(verification_code)


def _validate_email_field(email: str) -> str:
    """Validate email format and return the normalized value."""
    validation_error = validate_email(email)
    if validation_error:
        raise VerificationValidationError(validation_error)

    return normalize_email(email)


def _validate_signin_payload(payload: LoginRequest) -> str:
    """Validate sign-in fields and return the normalized email."""
    validation_error = validate_signin_request(
        email=payload.email,
        password=payload.password,
    )
    if validation_error:
        raise SigninValidationError(validation_error)

    return normalize_email(payload.email)


def _assign_verification_details(user: User) -> str:
    """Generate and attach a fresh OTP to the user."""
    verification_code = generate_verification_code()
    user.verification_code = verification_code
    user.verification_code_expires_at = get_verification_code_expiry()
    user.is_email_verified = False
    return verification_code


def register_user(db: Session, payload: SignupRequest) -> SignupSuccessResponse:
    """Register a new user with hashed password and default role/settings."""
    _validate_signup_payload(payload)

    normalized = normalize_signup_fields(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        mobile=payload.mobile,
    )

    existing_user = db.execute(
        select(User).where(User.email == normalized["email"])
    ).scalar_one_or_none()

    if _mobile_belongs_to_other_user(
        db,
        normalized["mobile"],
        exclude_user_id=existing_user.id if existing_user else None,
    ):
        raise MobileAlreadyRegisteredError()

    verification_code = generate_verification_code()

    if existing_user:
        if existing_user.is_email_verified:
            raise EmailAlreadyRegisteredError()

        # Allow re-signup for unverified accounts: refresh details and resend OTP.
        existing_user.first_name = normalized["first_name"]
        existing_user.last_name = normalized["last_name"]
        existing_user.mobile = normalized["mobile"]
        existing_user.password_hash = hash_password(payload.password)
        verification_code = _assign_verification_details(existing_user)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise EmailAlreadyRegisteredError() from exc

        db.refresh(existing_user)
        ensure_user_details_exists(db, existing_user.id)
        send_verification_email(
            existing_user.first_name,
            existing_user.email,
            verification_code,
        )
        return _build_signup_response(existing_user)

    user = User(
        first_name=normalized["first_name"],
        last_name=normalized["last_name"],
        email=normalized["email"],
        mobile=normalized["mobile"],
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
    ensure_user_details_exists(db, user.id)
    send_verification_email(user.first_name, user.email, verification_code)

    return _build_signup_response(user)


def verify_user_email(
    db: Session,
    payload: VerifyEmailRequest,
) -> VerifyEmailSuccessResponse:
    """Validate the submitted OTP and mark the user's email as verified."""
    submitted_code = _validate_verification_code_field(payload.verification_code)
    normalized_email = str(payload.email).lower()

    user = db.execute(
        select(User).where(User.verification_code == submitted_code)
    ).scalar_one_or_none()

    if not user or user.email != normalized_email:
        raise InvalidVerificationCodeError()

    if is_code_expired(user.verification_code_expires_at):
        raise ExpiredVerificationCodeError()

    if user.is_email_verified:
        raise EmailAlreadyVerifiedError()

    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None

    db.commit()

    return VerifyEmailSuccessResponse(message=messages.VERIFICATION_SUCCESS)


def resend_signup_verification(
    db: Session,
    payload: SignupResendVerificationRequest,
) -> SignupResendVerificationResponse:
    """Resend a signup verification code when email verification is still pending."""
    normalized_email = _validate_email_field(payload.email)

    user = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if not user:
        logger.info(
            "Signup verification resend requested for unknown email: %s",
            normalized_email,
        )
        raise SignupResendUserNotFoundError()

    if user.is_email_verified or user.is_mobile_verified:
        logger.info(
            "Signup verification resend skipped; account already verified: %s",
            normalized_email,
        )
        raise EmailAlreadyVerifiedError(messages.ACCOUNT_ALREADY_VERIFIED)

    if user.verification_code and not is_code_expired(user.verification_code_expires_at):
        logger.info(
            "Signup verification resend skipped; active code exists for: %s",
            normalized_email,
        )
        raise VerificationCodeNotExpiredError()

    verification_code = _assign_verification_details(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user.first_name, user.email, verification_code)
    logger.info("Signup verification code resent to: %s", normalized_email)

    return SignupResendVerificationResponse(
        message=messages.VERIFICATION_CODE_RESENT,
    )


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


def login_user(db: Session, payload: LoginRequest) -> LoginSuccessResponse:
    """Authenticate a user and return a JWT access token."""
    normalized_email = _validate_signin_payload(payload)

    user = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if not user:
        logger.info("Login failed for unknown email: %s", normalized_email)
        raise LoginUserNotFoundError()

    if not verify_password(payload.password, user.password_hash):
        logger.info("Login failed due to invalid password for: %s", normalized_email)
        raise LoginInvalidPasswordError()

    if not user.is_email_verified:
        logger.info("Login failed; account not verified: %s", normalized_email)
        raise EmailNotVerifiedForLoginError()

    if user.is_deleted:
        logger.info("Login failed; account deleted: %s", normalized_email)
        raise LoginUserNotFoundError()

    if not user.is_active:
        logger.info("Login failed; account deactivated: %s", normalized_email)
        raise AccountDisabledError(messages.ACCOUNT_DEACTIVATED)

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    logger.info("Login successful for: %s", normalized_email)

    return LoginSuccessResponse(
        message=messages.LOGIN_SUCCESS,
        data=LoginUserData(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name or None,
            email=user.email,
            role=user.role,
            is_email_verified=user.is_email_verified,
        ),
        access_token=access_token,
    )


def get_current_user_profile(user: User) -> MeSuccessResponse:
    """Return the authenticated user's basic profile."""
    return MeSuccessResponse(
        data=MeUserData(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name or None,
            email=user.email,
            role=user.role,
        ),
    )


def signout_user(
    db: Session,
    user: User,
    token: str,
    payload: dict,
) -> SignOutSuccessResponse:
    """Invalidate the current access token by adding its identifier to the blacklist."""
    logger.info("Sign-out requested for user_id=%s", user.id)

    jti = get_token_identifier(payload, token)
    exp = payload.get("exp")
    if exp is None:
        logger.error("Sign-out failed; token missing exp claim for user_id=%s", user.id)
        raise SignoutError()

    expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)

    try:
        blacklist_token(db, user.id, jti, expires_at)
    except Exception:
        logger.exception(
            "Failed to blacklist token for user_id=%s jti=%s",
            user.id,
            jti,
        )
        raise SignoutError() from None

    logger.info("Sign-out successful for user_id=%s jti=%s", user.id, jti)
    return SignOutSuccessResponse(message=messages.SIGNOUT_SUCCESS)
