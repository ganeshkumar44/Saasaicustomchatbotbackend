"""
Manage Users module helper utilities.
"""

import math

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core import messages
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.chatbot.model import (
    CHATBOT_STATUS_DRAFT,
    CHATBOT_STATUS_PUBLISHED,
    Chatbot,
)
from app.modules.theme.model import DEFAULT_THEME, Theme
from app.modules.user_details.model import UserDetails
from app.modules.user_details.utils import (
    ADMIN_ROLE,
    is_admin,
    validate_update_user_details_request,
)

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100

ACCOUNT_STATUS_ACTIVE = "active"
ACCOUNT_STATUS_DEACTIVATED = "deactivated"
ACCOUNT_STATUS_DELETED = "deleted"

ALLOWED_USER_ROLES = frozenset({ADMIN_ROLE, "user"})
ALLOWED_STATUS_ACTIONS = frozenset({"activate", "deactivate", "delete"})


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to administrator accounts."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "message": messages.UNAUTHORIZED_ACTION,
            },
        )
    return current_user


def resolve_account_status(user: User) -> str:
    """Return the display account status for a user record."""
    return resolve_account_status_from_flags(user.is_deleted, user.is_active)


def resolve_account_status_from_flags(is_deleted: bool, is_active: bool) -> str:
    """Return account status from persisted user flags."""
    if is_deleted:
        return ACCOUNT_STATUS_DELETED
    if not is_active:
        return ACCOUNT_STATUS_DEACTIVATED
    return ACCOUNT_STATUS_ACTIVE


def build_full_name(first_name: str | None, last_name: str | None) -> str:
    """Build a display full name from first and last name fields."""
    return f"{first_name or ''} {last_name or ''}".strip()


def normalize_pagination(page: int, per_page: int) -> tuple[int, int, int]:
    """Validate pagination inputs and return page, per_page, and offset."""
    normalized_page = page if page and page > 0 else DEFAULT_PAGE
    normalized_per_page = per_page if per_page and per_page > 0 else DEFAULT_PER_PAGE
    normalized_per_page = min(normalized_per_page, MAX_PER_PAGE)
    offset = (normalized_page - 1) * normalized_per_page
    return normalized_page, normalized_per_page, offset


def calculate_total_pages(total_records: int, per_page: int) -> int:
    """Return the total number of pages for a paginated result set."""
    if total_records <= 0:
        return 0
    return math.ceil(total_records / per_page)


def validate_role(role: str | None) -> str | None:
    """Validate a user role value. Returns an error message when invalid."""
    if role is None or not role.strip():
        return messages.INVALID_USER_ROLE

    if role.strip().lower() not in ALLOWED_USER_ROLES:
        return messages.INVALID_USER_ROLE

    return None


def validate_status_action(action: str | None) -> str | None:
    """Validate a manage-user status action. Returns an error message when invalid."""
    if action is None or not action.strip():
        return messages.INVALID_USER_STATUS_ACTION

    if action.strip().lower() not in ALLOWED_STATUS_ACTIONS:
        return messages.INVALID_USER_STATUS_ACTION

    return None


def validate_manage_user_update_request(
    *,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    mobile: str | None,
    company: str | None,
    website: str | None,
    language: str | None,
    bio: str | None,
    role: str | None,
) -> str | None:
    """Validate manage-user profile update fields, reusing existing validators."""
    profile_error = validate_update_user_details_request(
        first_name=first_name,
        last_name=last_name,
        email=email,
        mobile=mobile,
        company=company,
        website=website,
        language=language,
        bio=bio,
    )
    if profile_error:
        return profile_error

    return validate_role(role)


def _chatbot_count_subquery():
    """Count chatbots owned by each user."""
    return (
        select(
            Chatbot.user_id.label("user_id"),
            func.count(Chatbot.id).label("total_chatbots"),
        )
        .group_by(Chatbot.user_id)
        .subquery()
    )


def _chatbot_stats_subquery():
    """Aggregate published, draft, and deleted chatbot counts per user."""
    return (
        select(
            Chatbot.user_id.label("user_id"),
            func.count(Chatbot.id).label("total_chatbots"),
            func.count(Chatbot.id)
            .filter(Chatbot.is_deleted.is_(True))
            .label("total_deleted_chatbots"),
            func.count(Chatbot.id)
            .filter(
                Chatbot.is_deleted.is_(False),
                Chatbot.status == CHATBOT_STATUS_PUBLISHED,
            )
            .label("total_published_chatbots"),
            func.count(Chatbot.id)
            .filter(
                Chatbot.is_deleted.is_(False),
                Chatbot.status == CHATBOT_STATUS_DRAFT,
            )
            .label("total_draft_chatbots"),
        )
        .group_by(Chatbot.user_id)
        .subquery()
    )


def build_manage_user_detail_query(user_id: int) -> Select:
    """Build a query returning complete manage-user profile and chatbot statistics."""
    chatbot_stats = _chatbot_stats_subquery()

    return (
        select(
            User.id.label("user_id"),
            User.first_name,
            User.last_name,
            User.email,
            User.mobile,
            User.role,
            User.is_email_verified,
            User.is_mobile_verified,
            User.is_active,
            User.is_deleted,
            User.created_at,
            User.updated_at,
            UserDetails.profile_image,
            UserDetails.company,
            UserDetails.website,
            UserDetails.language,
            UserDetails.bio,
            func.coalesce(Theme.theme, DEFAULT_THEME).label("theme"),
            func.coalesce(chatbot_stats.c.total_chatbots, 0).label("total_chatbots"),
            func.coalesce(chatbot_stats.c.total_published_chatbots, 0).label(
                "total_published_chatbots"
            ),
            func.coalesce(chatbot_stats.c.total_draft_chatbots, 0).label(
                "total_draft_chatbots"
            ),
            func.coalesce(chatbot_stats.c.total_deleted_chatbots, 0).label(
                "total_deleted_chatbots"
            ),
        )
        .outerjoin(UserDetails, UserDetails.user_id == User.id)
        .outerjoin(Theme, Theme.user_id == User.id)
        .outerjoin(chatbot_stats, chatbot_stats.c.user_id == User.id)
        .where(User.id == user_id)
    )


def fetch_manage_user_detail_row(db: Session, user_id: int):
    """Return a single manage-user detail row or None when the user does not exist."""
    return db.execute(build_manage_user_detail_query(user_id)).one_or_none()


def _apply_search_filter(query: Select, search: str | None) -> Select:
    """Apply optional case-insensitive search across user profile fields."""
    if not search or not search.strip():
        return query

    term = f"%{search.strip()}%"
    return query.where(
        or_(
            User.first_name.ilike(term),
            User.last_name.ilike(term),
            User.email.ilike(term),
            User.mobile.ilike(term),
            UserDetails.company.ilike(term),
        )
    )


def build_manage_users_list_query(search: str | None = None) -> Select:
    """Build the base query for listing all users with profile and chatbot counts."""
    chatbot_counts = _chatbot_count_subquery()

    query = (
        select(
            User.id.label("user_id"),
            User.first_name,
            User.last_name,
            User.email,
            User.mobile,
            User.role,
            User.is_email_verified,
            User.is_mobile_verified,
            User.is_active,
            User.is_deleted,
            User.created_at,
            User.updated_at,
            UserDetails.company,
            UserDetails.website,
            UserDetails.language,
            UserDetails.profile_image,
            func.coalesce(chatbot_counts.c.total_chatbots, 0).label("total_chatbots"),
        )
        .outerjoin(UserDetails, UserDetails.user_id == User.id)
        .outerjoin(chatbot_counts, chatbot_counts.c.user_id == User.id)
        .order_by(User.created_at.desc())
    )
    return _apply_search_filter(query, search)


def build_manage_users_count_query(search: str | None = None) -> Select:
    """Build a count query for the manage-users listing."""
    query = (
        select(func.count(User.id))
        .select_from(User)
        .outerjoin(UserDetails, UserDetails.user_id == User.id)
    )
    return _apply_search_filter(query, search)


def fetch_manage_users_page(
    db: Session,
    *,
    page: int,
    per_page: int,
    search: str | None = None,
) -> tuple[list, int]:
    """Fetch a paginated page of manage-user rows and the total record count."""
    normalized_page, normalized_per_page, offset = normalize_pagination(page, per_page)

    total_records = db.scalar(build_manage_users_count_query(search)) or 0
    rows = db.execute(
        build_manage_users_list_query(search)
        .limit(normalized_per_page)
        .offset(offset)
    ).all()

    return rows, int(total_records)
