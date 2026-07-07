"""
User Details module helper utilities.
"""

import logging
import os
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import messages
from app.modules.auth.model import User
from fastapi import Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.modules.auth.utils import (
    USER_ROLE_ADMIN,
    USER_ROLE_SUPERADMIN,
    USER_ROLE_USER,
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
ADMIN_ROLE = USER_ROLE_ADMIN
ADMIN_PRIVILEGED_ROLES = frozenset({USER_ROLE_SUPERADMIN, USER_ROLE_ADMIN})
ALL_USER_ROLES = frozenset({USER_ROLE_SUPERADMIN, USER_ROLE_ADMIN, USER_ROLE_USER})
ASSIGNABLE_USER_ROLES = frozenset({USER_ROLE_ADMIN, USER_ROLE_USER})
PROFILE_IMAGE_PREFIX = "profile-images/"
MAX_PROFILE_IMAGE_SIZE_BYTES = 1 * 1024 * 1024
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PROFILE_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
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


def is_superadmin(user: User) -> bool:
    """Return True when the user has SuperAdmin privileges."""
    return user.role == USER_ROLE_SUPERADMIN


def is_admin(user: User) -> bool:
    """Return True when the user has administrator-level privileges (Admin or SuperAdmin)."""
    return user.role in ADMIN_PRIVILEGED_ROLES


def can_admin_manage_user(actor: User, target: User) -> bool:
    """Return True when an admin-level actor may manage another user's account."""
    if actor.id == target.id:
        return True
    if not is_admin(actor):
        return False
    if is_superadmin(target) and not is_superadmin(actor):
        return False
    return True


def can_manage_account(
    actor: User,
    target_user_id: int,
    *,
    target_user: User | None = None,
) -> bool:
    """Return True when the actor may manage the target account."""
    if actor.id == target_user_id:
        return True
    if not is_admin(actor):
        return False
    if target_user is not None and is_superadmin(target_user) and not is_superadmin(actor):
        return False
    return True


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to Admin or SuperAdmin accounts."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "message": messages.UNAUTHORIZED_ACTION,
            },
        )
    return current_user


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to SuperAdmin accounts only."""
    if not is_superadmin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "message": messages.SUPERADMIN_REQUIRED,
            },
        )
    return current_user


# Alias documenting that Admin and SuperAdmin share admin-level route access.
require_admin_or_superadmin = require_admin_user


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


def _get_aws_setting(name: str) -> str:
    """Read an AWS configuration value from the environment."""
    return os.getenv(name, "").strip()


def get_s3_client():
    """Create a configured boto3 S3 client using environment variables."""
    return boto3.client(
        "s3",
        aws_access_key_id=_get_aws_setting("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_get_aws_setting("AWS_SECRET_ACCESS_KEY"),
        region_name=_get_aws_setting("AWS_REGION"),
    )


def validate_profile_image_size(file_size: int) -> str | None:
    """Return an error message when a profile image exceeds the allowed size."""
    if file_size <= 0:
        return messages.INVALID_IMAGE_TYPE
    if file_size > MAX_PROFILE_IMAGE_SIZE_BYTES:
        return messages.IMAGE_SIZE_EXCEEDED
    return None


def validate_profile_image_upload(
    *,
    filename: str | None,
    content_type: str | None,
    file_size: int,
) -> str | None:
    """Validate profile image type and size. Returns an error message when invalid."""
    if not filename or not filename.strip():
        return messages.INVALID_IMAGE_TYPE

    extension = Path(filename.strip()).suffix.lower()
    if extension not in ALLOWED_PROFILE_IMAGE_EXTENSIONS:
        return messages.INVALID_IMAGE_TYPE

    size_error = validate_profile_image_size(file_size)
    if size_error:
        return size_error

    if content_type:
        normalized_content_type = content_type.split(";", 1)[0].strip().lower()
        if normalized_content_type not in ALLOWED_PROFILE_IMAGE_CONTENT_TYPES:
            return messages.INVALID_IMAGE_TYPE

    return None


def build_profile_image_object_key(user_id: int, filename: str) -> str:
    """Build a unique S3 object key for a profile image upload."""
    extension = Path(filename).suffix.lower()
    if extension == ".jpeg":
        extension = ".jpg"
    timestamp = int(time.time())
    return f"{PROFILE_IMAGE_PREFIX}user_{user_id}_{timestamp}{extension}"


def build_profile_image_public_url(object_key: str) -> str:
    """Build the public S3 URL for a stored profile image object."""
    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    region = _get_aws_setting("AWS_REGION")
    return f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"


def upload_profile_image_to_s3(
    *,
    content: bytes,
    object_key: str,
    content_type: str,
) -> str:
    """Upload a profile image to S3 and return its public URL."""
    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("AWS_BUCKET_NAME is not configured")

    client = get_s3_client()
    upload_content_type = content_type.split(";", 1)[0].strip().lower() or "image/jpeg"

    try:
        client.upload_fileobj(
            BytesIO(content),
            bucket_name,
            object_key,
            ExtraArgs={"ContentType": upload_content_type},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Failed to upload profile image to S3 object_key=%s", object_key)
        raise RuntimeError(messages.PROFILE_IMAGE_UPLOAD_FAILED) from exc

    return build_profile_image_public_url(object_key)


def extract_profile_image_object_key(image_url: str | None) -> str | None:
    """Extract the S3 object key from a stored profile image URL."""
    if not image_url or not image_url.strip():
        return None

    parsed = urlparse(image_url.strip())
    object_key = parsed.path.lstrip("/")
    if not object_key.startswith(PROFILE_IMAGE_PREFIX):
        return None

    return object_key


def delete_profile_image_from_s3(image_url: str | None) -> None:
    """Delete a profile image object from S3 when possible."""
    object_key = extract_profile_image_object_key(image_url)
    if object_key is None:
        return

    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        logger.warning("Skipping profile image delete; AWS_BUCKET_NAME is not configured")
        return

    try:
        get_s3_client().delete_object(Bucket=bucket_name, Key=object_key)
        logger.info("Deleted old profile image from S3 object_key=%s", object_key)
    except (BotoCoreError, ClientError):
        logger.exception(
            "Failed to delete old profile image from S3 object_key=%s",
            object_key,
        )


def delete_profile_image_from_s3_strict(image_url: str | None) -> None:
    """
    Delete a profile image from S3 and raise when deletion is required but fails.

    No-op when the URL does not resolve to a managed S3 object key.
    """
    object_key = extract_profile_image_object_key(image_url)
    if object_key is None:
        return

    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        raise RuntimeError(messages.PROFILE_IMAGE_DELETE_FAILED)

    try:
        get_s3_client().delete_object(Bucket=bucket_name, Key=object_key)
        logger.info("Deleted profile image from S3 object_key=%s", object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception(
            "Failed to delete profile image from S3 object_key=%s",
            object_key,
        )
        raise RuntimeError(messages.PROFILE_IMAGE_DELETE_FAILED) from exc
