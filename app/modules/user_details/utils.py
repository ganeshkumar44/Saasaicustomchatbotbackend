"""
User Details module helper utilities.
"""

import logging
import re
from urllib.parse import urlparse

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import (
    normalize_email,
    validate_email,
    validate_mobile,
    validate_name,
    validate_password,
    validate_password_match,
    validate_signin_password,
)
from app.modules.user_details.model import DEFAULT_LANGUAGE, UserDetails

logger = logging.getLogger(__name__)

COMPANY_MAX_LENGTH = 150
BIO_MAX_LENGTH = 1000
ADMIN_ROLE = "admin"
_WEBSITE_PATTERN = re.compile(
    r"^https?://"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}(?:/.*)?$",
    re.IGNORECASE,
)


def build_default_user_details(user_id: int) -> UserDetails:
    """Build a new user_details row with default profile values."""
    return UserDetails(
        user_id=user_id,
        profile_image=None,
        company=None,
        website=None,
        language=DEFAULT_LANGUAGE,
        bio=None,
    )


def get_user_details_by_user_id(db: Session, user_id: int) -> UserDetails | None:
    """Return the user_details row for a user, if one exists."""
    return db.execute(
        select(UserDetails).where(UserDetails.user_id == user_id)
    ).scalar_one_or_none()


def ensure_user_details_exists(db: Session, user_id: int) -> UserDetails:
    """
    Return existing user_details for a user or create one with default values.

    Safe to call multiple times; never creates duplicate records.
    """
    existing = get_user_details_by_user_id(db, user_id)
    if existing is not None:
        return existing

    details = build_default_user_details(user_id)
    db.add(details)
    db.commit()
    db.refresh(details)

    logger.info("Created default user_details for user_id=%s", user_id)
    return details


def apply_user_account_migrations(db_engine: Engine) -> None:
    """Add soft-delete columns to an existing users table when missing."""
    inspector = inspect(db_engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "is_deleted" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "deleted_at" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE"
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def sync_existing_user_details(db_engine: Engine) -> int:
    """
    Create missing user_details records for existing users.

    Safe to run multiple times; skips users who already have a profile record.
    Returns the number of records created.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created_count = 0

    try:
        missing_user_ids = db.execute(
            select(User.id)
            .outerjoin(UserDetails, User.id == UserDetails.user_id)
            .where(UserDetails.id.is_(None))
        ).scalars().all()

        for user_id in missing_user_ids:
            db.add(build_default_user_details(user_id))
            created_count += 1

        if created_count:
            db.commit()
            logger.info("Synchronized %s missing user_details records", created_count)
        else:
            logger.info("User details synchronization complete; no missing records")
    except Exception:
        db.rollback()
        logger.exception("Failed to synchronize existing user_details records")
        raise
    finally:
        db.close()

    return created_count


def is_admin(user: User) -> bool:
    """Return True when the user has administrator privileges."""
    return user.role == ADMIN_ROLE


def can_manage_account(actor: User, target_user_id: int) -> bool:
    """Return True when the actor may manage the target account."""
    return is_admin(actor) or actor.id == target_user_id


def _is_blank(value: str | None) -> bool:
    """Return True when a value is None or contains only whitespace."""
    return value is None or not value.strip()


def validate_website(value: str | None) -> str | None:
    """Validate an optional website URL."""
    if _is_blank(value):
        return None

    trimmed = value.strip()
    parsed = urlparse(trimmed)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return messages.INVALID_WEBSITE
    if not _WEBSITE_PATTERN.fullmatch(trimmed):
        return messages.INVALID_WEBSITE

    return None


def validate_language(value: str | None) -> str | None:
    """Validate that the language is supported."""
    if _is_blank(value):
        return messages.INVALID_LANGUAGE

    if value.strip() != DEFAULT_LANGUAGE:
        return messages.INVALID_LANGUAGE

    return None


def validate_company(value: str | None) -> str | None:
    """Validate an optional company name."""
    if _is_blank(value):
        return None

    if len(value.strip()) > COMPANY_MAX_LENGTH:
        return messages.COMPANY_TOO_LONG

    return None


def validate_bio(value: str | None) -> str | None:
    """Validate an optional biography."""
    if _is_blank(value):
        return None

    if len(value.strip()) > BIO_MAX_LENGTH:
        return messages.BIO_TOO_LONG

    return None


def validate_update_password_request(
    *,
    current_password: str | None,
    new_password: str | None,
    confirm_new_password: str | None,
) -> str | None:
    """Validate change-password payload fields in order."""
    current_error = validate_signin_password(current_password)
    if current_error:
        return messages.CURRENT_PASSWORD_REQUIRED

    if _is_blank(new_password):
        return messages.NEW_PASSWORD_REQUIRED

    password_error = validate_password(new_password)
    if password_error:
        return password_error

    if _is_blank(confirm_new_password):
        return messages.CONFIRM_NEW_PASSWORD_REQUIRED

    return validate_password_match(new_password, confirm_new_password)


def validate_update_user_details_request(
    *,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    mobile: str | None,
    company: str | None,
    website: str | None,
    language: str | None,
    bio: str | None,
) -> str | None:
    """Validate update-user-details payload fields in order."""
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
        validate_company(company),
        validate_website(website),
        validate_language(language),
        validate_bio(bio),
    )

    for error in validators:
        if error:
            return error

    return None


def email_belongs_to_other_user(
    db: Session,
    email: str,
    *,
    exclude_user_id: int,
) -> bool:
    """Return True when the email belongs to a different user."""
    normalized_email = normalize_email(email)
    existing = db.execute(
        select(User.id).where(
            User.email == normalized_email,
            User.id != exclude_user_id,
        )
    ).scalar_one_or_none()
    return existing is not None


def mobile_belongs_to_other_user(
    db: Session,
    mobile: str,
    *,
    exclude_user_id: int,
) -> bool:
    """Return True when the mobile number belongs to a different user."""
    trimmed_mobile = mobile.strip()
    existing = db.execute(
        select(User.id).where(
            User.mobile == trimmed_mobile,
            User.id != exclude_user_id,
        )
    ).scalar_one_or_none()
    return existing is not None
