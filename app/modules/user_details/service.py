"""
User Details module business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import hash_password, normalize_email, verify_password
from app.modules.user_details.schema import (
    ActivateAccountRequest,
    ActivateAccountSuccessResponse,
    DeactivateAccountRequest,
    DeactivateAccountSuccessResponse,
    DeleteAccountRequest,
    DeleteAccountSuccessResponse,
    UpdatePasswordRequest,
    UpdatePasswordSuccessResponse,
    UpdateUserDetailsRequest,
    UpdateUserDetailsSuccessResponse,
    UserDetailsData,
    UserDetailsSuccessResponse,
)
from app.modules.user_details.model import UserDetails
from app.modules.user_details.utils import (
    can_manage_account,
    email_belongs_to_other_user,
    ensure_user_details_exists,
    is_admin,
    mobile_belongs_to_other_user,
    validate_update_password_request,
    validate_update_user_details_request,
)

logger = logging.getLogger(__name__)


class UserDetailsValidationError(Exception):
    """Raised when user details payload fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class CurrentPasswordInvalidError(Exception):
    """Raised when the submitted current password is incorrect."""


class NewPasswordSameAsCurrentError(Exception):
    """Raised when the new password matches the current password."""


class EmailAlreadyInUseError(Exception):
    """Raised when the email is already registered to another user."""


class MobileAlreadyInUseError(Exception):
    """Raised when the mobile number is already registered to another user."""


class TargetUserNotFoundError(Exception):
    """Raised when the requested account does not exist."""


class UnauthorizedAccountActionError(Exception):
    """Raised when the actor cannot manage the target account."""


class AdminAccessRequiredError(Exception):
    """Raised when a non-admin attempts an administrator-only action."""


class AccountAlreadyActiveError(Exception):
    """Raised when attempting to activate an already active account."""


class AccountAlreadyDeactivatedError(Exception):
    """Raised when attempting to deactivate an already inactive account."""


class AccountAlreadyDeletedError(Exception):
    """Raised when attempting to delete an already deleted account."""


def build_merged_user_details(user: User, details: UserDetails) -> UserDetailsData:
    """Merge users and user_details records into a single response payload."""
    return UserDetailsData(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        mobile=user.mobile,
        role=user.role,
        is_email_verified=user.is_email_verified,
        is_mobile_verified=user.is_mobile_verified,
        is_active=user.is_active,
        profile_image=details.profile_image,
        company=details.company,
        website=details.website,
        language=details.language,
        bio=details.bio,
        created_at=user.created_at,
        updated_at=user.updated_at,
        profile_created_at=details.created_at,
        profile_updated_at=details.updated_at,
    )


def get_user_details(db: Session, user: User) -> UserDetailsSuccessResponse:
    """Return the authenticated user's merged profile details."""
    logger.info("Fetching user details for user_id=%s", user.id)

    details = ensure_user_details_exists(db, user.id)

    logger.info("User details fetched successfully for user_id=%s", user.id)

    return UserDetailsSuccessResponse(
        message=messages.USER_DETAILS_FETCH_SUCCESS,
        data=build_merged_user_details(user, details),
    )


def update_password(
    db: Session,
    user: User,
    payload: UpdatePasswordRequest,
) -> UpdatePasswordSuccessResponse:
    """Change the authenticated user's password after validating the current one."""
    logger.info("Password update requested for user_id=%s", user.id)

    validation_error = validate_update_password_request(
        current_password=payload.current_password,
        new_password=payload.new_password,
        confirm_new_password=payload.confirm_new_password,
    )
    if validation_error:
        raise UserDetailsValidationError(validation_error)

    if not verify_password(payload.current_password, user.password_hash):
        logger.warning("Password update failed; invalid current password user_id=%s", user.id)
        raise CurrentPasswordInvalidError()

    if verify_password(payload.new_password, user.password_hash):
        logger.warning(
            "Password update failed; new password matches current password user_id=%s",
            user.id,
        )
        raise NewPasswordSameAsCurrentError()

    user.password_hash = hash_password(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Password updated successfully for user_id=%s", user.id)

    return UpdatePasswordSuccessResponse(message=messages.PASSWORD_UPDATED_SUCCESS)


def update_user_details(
    db: Session,
    user: User,
    payload: UpdateUserDetailsRequest,
) -> UpdateUserDetailsSuccessResponse:
    """Update the authenticated user's profile fields across users and user_details."""
    logger.info("User details update requested for user_id=%s", user.id)

    validation_error = validate_update_user_details_request(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        mobile=payload.mobile,
        company=payload.company,
        website=payload.website,
        language=payload.language,
        bio=payload.bio,
    )
    if validation_error:
        raise UserDetailsValidationError(validation_error)

    normalized_email = normalize_email(payload.email)
    trimmed_mobile = payload.mobile.strip()

    if email_belongs_to_other_user(db, normalized_email, exclude_user_id=user.id):
        raise EmailAlreadyInUseError()

    if mobile_belongs_to_other_user(db, trimmed_mobile, exclude_user_id=user.id):
        raise MobileAlreadyInUseError()

    details = ensure_user_details_exists(db, user.id)

    user.first_name = payload.first_name.strip()
    user.last_name = payload.last_name.strip()
    user.email = normalized_email
    user.mobile = trimmed_mobile
    user.updated_at = datetime.now(timezone.utc)

    details.company = payload.company.strip() if payload.company and payload.company.strip() else None
    details.website = payload.website.strip() if payload.website and payload.website.strip() else None
    details.language = payload.language.strip()
    details.bio = payload.bio.strip() if payload.bio and payload.bio.strip() else None
    details.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Failed to update user details for user_id=%s", user.id)
        raise EmailAlreadyInUseError() from exc

    db.refresh(user)
    db.refresh(details)

    logger.info("User details updated successfully for user_id=%s", user.id)

    return UpdateUserDetailsSuccessResponse(message=messages.USER_DETAILS_UPDATED)


def _get_target_user(db: Session, user_id: int) -> User:
    """Return the target user or raise when the account does not exist."""
    user = db.get(User, user_id)
    if user is None:
        raise TargetUserNotFoundError()
    return user


def _resolve_target_user_id(actor: User, requested_user_id: int | None) -> int:
    """Return the effective target user ID for account management actions."""
    return requested_user_id if requested_user_id is not None else actor.id


def delete_account(
    db: Session,
    actor: User,
    payload: DeleteAccountRequest | None = None,
) -> DeleteAccountSuccessResponse:
    """Soft-delete a user account."""
    target_user_id = _resolve_target_user_id(
        actor,
        payload.user_id if payload else None,
    )

    logger.info(
        "Account delete requested target_user_id=%s actor_user_id=%s",
        target_user_id,
        actor.id,
    )

    if not can_manage_account(actor, target_user_id):
        logger.warning(
            "Unauthorized account delete attempt target_user_id=%s actor_user_id=%s",
            target_user_id,
            actor.id,
        )
        raise UnauthorizedAccountActionError()

    target_user = _get_target_user(db, target_user_id)

    if target_user.is_deleted:
        raise AccountAlreadyDeletedError()

    now = datetime.now(timezone.utc)
    target_user.is_deleted = True
    target_user.deleted_at = now
    target_user.is_active = False
    target_user.updated_at = now
    db.commit()

    logger.info(
        "Account deleted successfully target_user_id=%s actor_user_id=%s",
        target_user_id,
        actor.id,
    )

    return DeleteAccountSuccessResponse(message=messages.DELETE_SUCCESS)


def deactivate_account(
    db: Session,
    actor: User,
    payload: DeactivateAccountRequest | None = None,
) -> DeactivateAccountSuccessResponse:
    """Deactivate a user account."""
    target_user_id = _resolve_target_user_id(
        actor,
        payload.user_id if payload else None,
    )

    logger.info(
        "Account deactivate requested target_user_id=%s actor_user_id=%s",
        target_user_id,
        actor.id,
    )

    if not can_manage_account(actor, target_user_id):
        logger.warning(
            "Unauthorized account deactivate attempt target_user_id=%s actor_user_id=%s",
            target_user_id,
            actor.id,
        )
        raise UnauthorizedAccountActionError()

    target_user = _get_target_user(db, target_user_id)

    if target_user.is_deleted:
        raise AccountAlreadyDeletedError()

    if not target_user.is_active:
        raise AccountAlreadyDeactivatedError()

    now = datetime.now(timezone.utc)
    target_user.is_active = False
    target_user.updated_at = now
    db.commit()

    logger.info(
        "Account deactivated successfully target_user_id=%s actor_user_id=%s",
        target_user_id,
        actor.id,
    )

    return DeactivateAccountSuccessResponse(message=messages.DEACTIVATE_SUCCESS)


def activate_account(
    db: Session,
    actor: User,
    payload: ActivateAccountRequest,
) -> ActivateAccountSuccessResponse:
    """Activate a user account (administrator only)."""
    logger.info(
        "Account activate requested target_user_id=%s actor_user_id=%s",
        payload.user_id,
        actor.id,
    )

    if not is_admin(actor):
        logger.warning(
            "Non-admin account activate attempt target_user_id=%s actor_user_id=%s",
            payload.user_id,
            actor.id,
        )
        raise AdminAccessRequiredError()

    target_user = _get_target_user(db, payload.user_id)

    if target_user.is_deleted:
        target_user.is_deleted = False
        target_user.deleted_at = None
    elif target_user.is_active:
        raise AccountAlreadyActiveError()

    now = datetime.now(timezone.utc)
    target_user.is_active = True
    target_user.updated_at = now
    db.commit()

    logger.info(
        "Account activated successfully target_user_id=%s actor_user_id=%s",
        payload.user_id,
        actor.id,
    )

    return ActivateAccountSuccessResponse(message=messages.ACTIVATE_SUCCESS)
