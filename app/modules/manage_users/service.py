"""
Manage Users module business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import normalize_email
from app.modules.chatbot.model import Chatbot
from app.modules.manage_users.schema import (
    ManageUserListItem,
    ManageUsersListSuccessResponse,
    UpdateManageUserRequest,
    UpdateManageUserSuccessResponse,
    UpdateUserStatusRequest,
    UpdateUserStatusSuccessResponse,
)
from app.modules.manage_users.utils import (
    build_full_name,
    calculate_total_pages,
    fetch_manage_users_page,
    normalize_pagination,
    resolve_account_status,
    resolve_account_status_from_flags,
    validate_manage_user_update_request,
    validate_status_action,
)
from app.modules.user_details.utils import (
    email_belongs_to_other_user,
    ensure_user_details_exists,
    mobile_belongs_to_other_user,
)

logger = logging.getLogger(__name__)


class ManageUsersValidationError(Exception):
    """Raised when a manage-users payload fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UserNotFoundError(Exception):
    """Raised when the requested user does not exist."""


class SelfActionNotAllowedError(Exception):
    """Raised when an administrator attempts to deactivate or delete their own account."""


class EmailAlreadyInUseError(Exception):
    """Raised when the email is already registered to another user."""


class MobileAlreadyInUseError(Exception):
    """Raised when the mobile number is already registered to another user."""


class AccountAlreadyActiveError(Exception):
    """Raised when attempting to activate an already active account."""


class AccountAlreadyDeactivatedError(Exception):
    """Raised when attempting to deactivate an already inactive account."""


class AccountAlreadyDeletedError(Exception):
    """Raised when attempting to delete an already deleted account."""


def _get_target_user(db: Session, user_id: int) -> User:
    """Return the target user or raise when the account does not exist."""
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    return user


def _build_manage_user_list_item(user: User, details, total_chatbots: int = 0) -> ManageUserListItem:
    """Map user and profile records to the manage-users list item shape."""
    return ManageUserListItem(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=build_full_name(user.first_name, user.last_name),
        email=user.email,
        mobile=user.mobile,
        company=details.company if details else None,
        website=details.website if details else None,
        language=details.language if details else None,
        profile_image=details.profile_image if details else None,
        role=user.role,
        account_status=resolve_account_status(user),
        email_verified=user.is_email_verified,
        mobile_verified=user.is_mobile_verified,
        total_chatbots=int(total_chatbots),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _build_manage_user_list_item_from_row(row) -> ManageUserListItem:
    """Map a manage-users query row to the API list item shape."""
    return ManageUserListItem(
        user_id=row.user_id,
        first_name=row.first_name,
        last_name=row.last_name,
        full_name=build_full_name(row.first_name, row.last_name),
        email=row.email,
        mobile=row.mobile,
        company=row.company,
        website=row.website,
        language=row.language,
        profile_image=row.profile_image,
        role=row.role,
        account_status=resolve_account_status_from_flags(row.is_deleted, row.is_active),
        email_verified=row.is_email_verified,
        mobile_verified=row.is_mobile_verified,
        total_chatbots=int(row.total_chatbots or 0),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_users(
    db: Session,
    admin_user: User,
    *,
    page: int,
    per_page: int,
    search: str | None = None,
) -> ManageUsersListSuccessResponse:
    """Return a paginated list of all users for administrator management."""
    normalized_page, normalized_per_page, _ = normalize_pagination(page, per_page)

    logger.info(
        "Fetching manage-users list admin_user_id=%s page=%s per_page=%s search=%s",
        admin_user.id,
        normalized_page,
        normalized_per_page,
        search,
    )

    rows, total_records = fetch_manage_users_page(
        db,
        page=normalized_page,
        per_page=normalized_per_page,
        search=search,
    )
    total_pages = calculate_total_pages(total_records, normalized_per_page)

    items = [_build_manage_user_list_item_from_row(row) for row in rows]

    logger.info(
        "Manage-users list fetched admin_user_id=%s total_records=%s returned=%s",
        admin_user.id,
        total_records,
        len(items),
    )

    return ManageUsersListSuccessResponse(
        message=messages.USERS_RETRIEVED_SUCCESS,
        page=normalized_page,
        per_page=normalized_per_page,
        total_records=total_records,
        total_pages=total_pages,
        data=items,
    )


def update_user_status(
    db: Session,
    admin_user: User,
    user_id: int,
    payload: UpdateUserStatusRequest,
) -> UpdateUserStatusSuccessResponse:
    """Activate, deactivate, or soft-delete a user account."""
    action = payload.action.strip().lower()
    validation_error = validate_status_action(action)
    if validation_error:
        raise ManageUsersValidationError(validation_error)

    logger.info(
        "Manage-user status update requested admin_user_id=%s target_user_id=%s action=%s",
        admin_user.id,
        user_id,
        action,
    )

    if admin_user.id == user_id and action in {"deactivate", "delete"}:
        raise SelfActionNotAllowedError()

    target_user = _get_target_user(db, user_id)
    now = datetime.now(timezone.utc)

    if action == "activate":
        if target_user.is_deleted:
            target_user.is_deleted = False
            target_user.deleted_at = None
        elif target_user.is_active and not target_user.is_deleted:
            raise AccountAlreadyActiveError()

        target_user.is_active = True
        target_user.updated_at = now
        success_message = messages.USER_ACTIVATED_SUCCESS

    elif action == "deactivate":
        if target_user.is_deleted:
            raise AccountAlreadyDeletedError()

        if not target_user.is_active:
            raise AccountAlreadyDeactivatedError()

        target_user.is_active = False
        target_user.updated_at = now
        success_message = messages.USER_DEACTIVATED_SUCCESS

    else:
        if target_user.is_deleted:
            raise AccountAlreadyDeletedError()

        target_user.is_deleted = True
        target_user.deleted_at = now
        target_user.is_active = False
        target_user.updated_at = now
        success_message = messages.USER_DELETED_SUCCESS

    db.commit()
    db.refresh(target_user)

    logger.info(
        "Manage-user status updated admin_user_id=%s target_user_id=%s action=%s status=%s",
        admin_user.id,
        user_id,
        action,
        resolve_account_status(target_user),
    )

    return UpdateUserStatusSuccessResponse(
        message=success_message,
        user_id=target_user.id,
        account_status=resolve_account_status(target_user),
    )


def update_user(
    db: Session,
    admin_user: User,
    user_id: int,
    payload: UpdateManageUserRequest,
) -> UpdateManageUserSuccessResponse:
    """Update any user's profile fields as an administrator."""
    logger.info(
        "Manage-user update requested admin_user_id=%s target_user_id=%s",
        admin_user.id,
        user_id,
    )

    validation_error = validate_manage_user_update_request(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        mobile=payload.mobile,
        company=payload.company,
        website=payload.website,
        language=payload.language,
        bio=payload.bio,
        role=payload.role,
    )
    if validation_error:
        raise ManageUsersValidationError(validation_error)

    target_user = _get_target_user(db, user_id)
    normalized_email = normalize_email(payload.email)
    trimmed_mobile = payload.mobile.strip()

    if email_belongs_to_other_user(db, normalized_email, exclude_user_id=target_user.id):
        raise EmailAlreadyInUseError()

    if mobile_belongs_to_other_user(db, trimmed_mobile, exclude_user_id=target_user.id):
        raise MobileAlreadyInUseError()

    details = ensure_user_details_exists(db, target_user.id)
    now = datetime.now(timezone.utc)

    target_user.first_name = payload.first_name.strip()
    target_user.last_name = payload.last_name.strip()
    target_user.email = normalized_email
    target_user.mobile = trimmed_mobile
    target_user.role = payload.role.strip().lower()
    target_user.updated_at = now

    details.company = (
        payload.company.strip() if payload.company and payload.company.strip() else None
    )
    details.website = (
        payload.website.strip() if payload.website and payload.website.strip() else None
    )
    details.language = payload.language.strip()
    details.bio = payload.bio.strip() if payload.bio and payload.bio.strip() else None
    details.updated_at = now

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception(
            "Failed to update manage-user profile target_user_id=%s",
            target_user.id,
        )
        raise EmailAlreadyInUseError() from exc

    db.refresh(target_user)
    db.refresh(details)

    total_chatbots = db.scalar(
        select(func.count(Chatbot.id)).where(Chatbot.user_id == target_user.id)
    ) or 0

    logger.info(
        "Manage-user profile updated admin_user_id=%s target_user_id=%s",
        admin_user.id,
        target_user.id,
    )

    return UpdateManageUserSuccessResponse(
        message=messages.USER_UPDATED_SUCCESS,
        data=_build_manage_user_list_item(target_user, details, total_chatbots),
    )
