import logging
import random
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import bcrypt
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core import messages
from app.core.config import get_settings
from app.core.email_templates import (
    build_forgot_password_email,
    build_signup_verification_email,
)
from app.core.dependencies import get_auth_context, get_current_user
from app.core.security import (
    InvalidTokenError,
    TokenBlacklistedError,
    TokenExpiredError,
    blacklist_token,
    create_access_token,
    decode_access_token,
    get_token_identifier,
    is_token_blacklisted,
)
from app.modules.auth.model import User

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 10

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 50
MOBILE_MIN_LENGTH = 8
MOBILE_MAX_LENGTH = 15
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 100

_NAME_PATTERN = re.compile(r"^[A-Za-z]+$")
_MOBILE_PATTERN = re.compile(rf"^\d{{{MOBILE_MIN_LENGTH},{MOBILE_MAX_LENGTH}}}$")
_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
)
_PASSWORD_UPPERCASE = re.compile(r"[A-Z]")
_PASSWORD_LOWERCASE = re.compile(r"[a-z]")
_PASSWORD_DIGIT = re.compile(r"\d")
_PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;/'`~]")
_VERIFICATION_CODE_LENGTH = 6
_VERIFICATION_CODE_PATTERN = re.compile(rf"^\d{{{_VERIFICATION_CODE_LENGTH}}}$")

USER_ROLE_SUPERADMIN = "superadmin"
USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"
SIGNUP_ROLE_ASSIGNMENT_LOCK_ID = 8347291

__all__ = [
    "InvalidTokenError",
    "TokenBlacklistedError",
    "TokenExpiredError",
    "apply_verification_migrations",
    "blacklist_token",
    "create_access_token",
    "decode_access_token",
    "generate_verification_code",
    "get_auth_context",
    "get_current_user",
    "get_token_identifier",
    "get_verification_code_expiry",
    "hash_password",
    "is_code_expired",
    "is_token_blacklisted",
    "normalize_email",
    "normalize_signup_fields",
    "normalize_verification_code",
    "resolve_initial_signup_role",
    "send_forgot_password_email",
    "send_verification_email",
    "validate_email",
    "validate_name",
    "validate_mobile",
    "validate_password",
    "validate_password_match",
    "validate_signin_password",
    "validate_signin_request",
    "validate_signup_request",
    "validate_verification_code",
    "verify_password",
]


def _get_smtp_settings() -> dict[str, str | int]:
    """Read SMTP configuration from application settings at send time."""
    settings = get_settings()
    return {
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "user": settings.SMTP_USER,
        "password": settings.SMTP_PASSWORD,
        "from_email": settings.SMTP_FROM,
    }


def hash_password(password: str) -> str:
    """Return a bcrypt hash for the given plain-text password."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def generate_verification_code() -> str:
    """Generate a random 6-digit numeric OTP."""
    return f"{random.randint(0, 999999):06d}"


def get_verification_code_expiry() -> datetime:
    """Return the UTC expiry timestamp for a newly generated OTP."""
    return datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)


def is_code_expired(expires_at: datetime | None) -> bool:
    """Return True when an OTP expiry timestamp is missing or in the past."""
    if not expires_at:
        return True

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at < datetime.now(timezone.utc)


def _send_email(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str | None = None,
) -> None:
    """Send a plain-text or multipart HTML email using configured SMTP settings."""
    smtp = _get_smtp_settings()
    smtp_user = str(smtp["user"])
    smtp_password = str(smtp["password"])

    if not smtp_user or not smtp_password:
        logger.error("SMTP credentials are not configured; email not sent to %s.", to_email)
        return

    from_email = str(smtp["from_email"])

    message = MIMEMultipart("alternative" if html_body else "mixed")
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(plain_body, "plain"))
    if html_body:
        message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(str(smtp["host"]), int(smtp["port"]), timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, message.as_string())
        logger.info("Email sent to %s with subject '%s'", to_email, subject)
    except smtplib.SMTPException:
        logger.exception("Failed to send email to %s", to_email)


def send_verification_email(first_name: str, to_email: str, verification_code: str) -> None:
    """Send the email verification OTP to the registered user."""
    subject, plain_body, html_body = build_signup_verification_email(
        first_name=first_name,
        verification_code=verification_code,
        expiry_minutes=OTP_EXPIRY_MINUTES,
    )
    _send_email(to_email, subject, plain_body, html_body)


def send_forgot_password_email(to_email: str, verification_code: str) -> None:
    """Send the forgot-password verification code to the user's email."""
    subject, plain_body, html_body = build_forgot_password_email(
        verification_code=verification_code,
        expiry_minutes=OTP_EXPIRY_MINUTES,
    )
    _send_email(to_email, subject, plain_body, html_body)


def _is_blank(value: str | None) -> bool:
    """Return True when a value is None or contains only whitespace."""
    return value is None or not value.strip()


def validate_name(
    value: str | None,
    *,
    required_message: str,
    too_short_message: str,
    too_long_message: str,
    invalid_message: str,
) -> str | None:
    """
    Validate a person's name.

    Returns the first validation error message, or None when the value is valid.
    """
    if _is_blank(value):
        return required_message

    trimmed = value.strip()
    if len(trimmed) < NAME_MIN_LENGTH:
        return too_short_message
    if len(trimmed) > NAME_MAX_LENGTH:
        return too_long_message
    if not _NAME_PATTERN.fullmatch(trimmed):
        return invalid_message

    return None


def validate_email(value: str | None) -> str | None:
    """
    Validate an email address format.

    Returns the first validation error message, or None when the value is valid.
    """
    if _is_blank(value):
        return messages.EMAIL_REQUIRED

    trimmed = value.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(trimmed):
        return messages.INVALID_EMAIL

    return None


def normalize_email(value: str) -> str:
    """Return a trimmed, lowercased email address ready for lookup or persistence."""
    return value.strip().lower()


def validate_mobile(value: str | None) -> str | None:
    """
    Validate a mobile number.

    Returns the first validation error message, or None when the value is valid.
    """
    if _is_blank(value):
        return messages.MOBILE_REQUIRED

    trimmed = value.strip()
    if not _MOBILE_PATTERN.fullmatch(trimmed):
        return messages.INVALID_MOBILE

    return None


def validate_password(value: str | None) -> str | None:
    """
    Validate a password against length and complexity rules.

    Returns the first validation error message, or None when the value is valid.
    """
    if _is_blank(value):
        return messages.PASSWORD_REQUIRED

    if len(value) < PASSWORD_MIN_LENGTH:
        return messages.PASSWORD_TOO_SHORT
    if len(value) > PASSWORD_MAX_LENGTH:
        return messages.PASSWORD_TOO_LONG
    if (
        not _PASSWORD_UPPERCASE.search(value)
        or not _PASSWORD_LOWERCASE.search(value)
        or not _PASSWORD_DIGIT.search(value)
        or not _PASSWORD_SPECIAL.search(value)
    ):
        return messages.PASSWORD_POLICY_FAILED

    return None


def validate_password_match(password: str, confirm_password: str | None) -> str | None:
    """
    Validate that password and confirm_password match.

    Returns the first validation error message, or None when the values match.
    """
    if _is_blank(confirm_password):
        return messages.CONFIRM_PASSWORD_REQUIRED
    if password != confirm_password:
        return messages.PASSWORD_MISMATCH

    return None


def validate_signin_password(value: str | None) -> str | None:
    """
    Validate that a sign-in password is present and not whitespace-only.

    Returns the first validation error message, or None when the value is valid.
    Does not enforce password complexity rules.
    """
    if _is_blank(value):
        return messages.PASSWORD_REQUIRED

    return None


def validate_signin_request(
    *,
    email: str | None,
    password: str | None,
) -> str | None:
    """
    Run all sign-in field validations in order.

    Returns the first validation error message, or None when all fields are valid.
    Reusable for future authentication APIs.
    """
    email_error = validate_email(email)
    if email_error:
        return email_error

    return validate_signin_password(password)


def validate_verification_code(value: str | None) -> str | None:
    """
    Validate a numeric OTP verification code.

    Rules:
    - Required, non-empty after trim
    - Exactly 6 digits
    - Numbers only (no letters or special characters)

    Returns the first validation error message, or None when the value is valid.
    Reusable for signup verification, forgot-password verification, and future OTP APIs.
    """
    if value is None:
        return messages.VERIFICATION_CODE_REQUIRED

    trimmed = value.strip()
    if not trimmed:
        return messages.VERIFICATION_CODE_REQUIRED
    if not _VERIFICATION_CODE_PATTERN.fullmatch(trimmed):
        return messages.VERIFICATION_CODE_INVALID_FORMAT

    return None


def normalize_verification_code(value: str) -> str:
    """Return a trimmed verification code ready for comparison or persistence."""
    return value.strip()


def validate_signup_request(
    *,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    mobile: str | None,
    password: str | None,
    confirm_password: str | None,
) -> str | None:
    """
    Run all signup field validations in order.

    Returns the first validation error message, or None when all fields are valid.
    """
    validators = (
        validate_name(
            first_name,
            required_message=messages.FIRST_NAME_REQUIRED,
            too_short_message=messages.FIRST_NAME_TOO_SHORT,
            too_long_message=messages.FIRST_NAME_TOO_LONG,
            invalid_message=messages.FIRST_NAME_INVALID,
        ),
        validate_name(
            last_name,
            required_message=messages.LAST_NAME_REQUIRED,
            too_short_message=messages.LAST_NAME_TOO_SHORT,
            too_long_message=messages.LAST_NAME_TOO_LONG,
            invalid_message=messages.LAST_NAME_INVALID,
        ),
        validate_email(email),
        validate_mobile(mobile),
        validate_password(password),
    )

    for error in validators:
        if error:
            return error

    if password is None:
        return messages.PASSWORD_REQUIRED

    return validate_password_match(password, confirm_password)


def normalize_signup_fields(
    *,
    first_name: str,
    last_name: str,
    email: str,
    mobile: str,
) -> dict[str, str]:
    """Return trimmed and normalized signup field values ready for persistence."""
    return {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.strip().lower(),
        "mobile": mobile.strip(),
    }


def resolve_initial_signup_role(db: Session) -> str:
    """
    Determine the role for a newly registered user.

    The first non-deleted user becomes SuperAdmin; all later users are normal
    users. A PostgreSQL advisory transaction lock prevents concurrent signups on
    a fresh installation from creating more than one SuperAdmin.
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": SIGNUP_ROLE_ASSIGNMENT_LOCK_ID},
    )

    existing_user_count = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.is_deleted.is_(False))
    ) or 0

    if existing_user_count == 0:
        logger.info("Assigning SuperAdmin role to first registered user")
        return USER_ROLE_SUPERADMIN

    return USER_ROLE_USER


def apply_verification_migrations(db_engine: Engine) -> None:
    """
    Add verification columns to an existing users table.

    create_all() only creates new tables; it does not alter existing ones.
    """
    inspector = inspect(db_engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "verification_code" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN verification_code VARCHAR(6)"
        )
    if "verification_code_expires_at" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN verification_code_expires_at "
            "TIMESTAMP WITH TIME ZONE"
        )
    if "forgot_password_code" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN forgot_password_code VARCHAR(6)"
        )
    if "forgot_password_code_expires_at" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN forgot_password_code_expires_at "
            "TIMESTAMP WITH TIME ZONE"
        )
    if "forgot_password_verified" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN forgot_password_verified "
            "BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "last_login" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN last_login TIMESTAMP WITH TIME ZONE"
        )

    # Allow the same mobile number across different accounts.
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("users")
    }
    if "users_mobile_key" in unique_constraints:
        statements.append("ALTER TABLE users DROP CONSTRAINT users_mobile_key")

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
