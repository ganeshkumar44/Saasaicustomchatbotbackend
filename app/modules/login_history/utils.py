"""Login history helper utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.login_history.model import (
    LOGIN_STATUS_FAILED,
    LOGIN_STATUS_SUCCESS,
    LoginHistory,
)

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100
USER_LOGIN_HISTORY_DAYS = 5

_UNKNOWN = "Unknown"


@dataclass(frozen=True)
class LoginClientInfo:
    """Client metadata captured from an HTTP request during authentication."""

    ip_address: str | None
    user_agent: str | None
    browser: str
    operating_system: str
    device_type: str


@dataclass(frozen=True)
class ParsedUserAgent:
    browser: str
    operating_system: str
    device_type: str


def get_client_ip(request: Request) -> str | None:
    """Return the client IP, honoring X-Forwarded-For when present."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    if request.client and request.client.host:
        return request.client.host

    return None


def detect_browser(user_agent: str | None) -> str:
    """Detect browser name from a User-Agent string."""
    if not user_agent:
        return _UNKNOWN

    ua = user_agent.lower()
    if "edg/" in ua or "edge/" in ua:
        return "Edge"
    if "opr/" in ua or "opera" in ua:
        return "Opera"
    if "firefox/" in ua:
        return "Firefox"
    if "chrome/" in ua or "crios/" in ua:
        return "Chrome"
    if "safari/" in ua:
        return "Safari"
    return _UNKNOWN


def detect_operating_system(user_agent: str | None) -> str:
    """Detect operating system from a User-Agent string."""
    if not user_agent:
        return _UNKNOWN

    ua = user_agent.lower()
    if "windows" in ua:
        return "Windows"
    if "mac os x" in ua or "macintosh" in ua:
        return "macOS"
    if "android" in ua:
        return "Android"
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        return "iOS"
    if "linux" in ua:
        return "Linux"
    return _UNKNOWN


def detect_device_type(user_agent: str | None) -> str:
    """Detect device type from a User-Agent string."""
    if not user_agent:
        return _UNKNOWN

    ua = user_agent.lower()
    if "ipad" in ua or "tablet" in ua:
        return "Tablet"
    if "mobile" in ua or "iphone" in ua or "android" in ua and "mobile" in ua:
        return "Mobile"
    if "macintosh" in ua or "windows" in ua or "linux" in ua:
        return "Desktop"
    return "Desktop"


def parse_user_agent(user_agent: str | None) -> ParsedUserAgent:
    """Parse browser, OS, and device type from a User-Agent string."""
    return ParsedUserAgent(
        browser=detect_browser(user_agent),
        operating_system=detect_operating_system(user_agent),
        device_type=detect_device_type(user_agent),
    )


def build_login_client_info(request: Request) -> LoginClientInfo:
    """Build client metadata from an incoming HTTP request."""
    user_agent = request.headers.get("User-Agent")
    parsed = parse_user_agent(user_agent)
    return LoginClientInfo(
        ip_address=get_client_ip(request),
        user_agent=user_agent,
        browser=parsed.browser,
        operating_system=parsed.operating_system,
        device_type=parsed.device_type,
    )


def normalize_pagination(page: int, per_page: int) -> tuple[int, int, int]:
    """Normalize pagination inputs and return page, per_page, offset."""
    normalized_page = max(page, DEFAULT_PAGE)
    normalized_per_page = min(max(per_page, 1), MAX_PER_PAGE)
    offset = (normalized_page - 1) * normalized_per_page
    return normalized_page, normalized_per_page, offset


def calculate_total_pages(total_records: int, per_page: int) -> int:
    """Return total pages for paginated responses."""
    if total_records <= 0:
        return 0
    return math.ceil(total_records / per_page)


def user_login_history_cutoff() -> datetime:
    """Return the earliest login timestamp visible to regular users."""
    return datetime.now(timezone.utc) - timedelta(days=USER_LOGIN_HISTORY_DAYS)


def _apply_manage_login_history_filters(
    query: Select,
    *,
    search: str | None,
    role: str | None,
    login_status: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select:
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
                LoginHistory.email.ilike(term),
            )
        )

    if role and role.strip():
        query = query.where(User.role == role.strip().lower())

    if login_status and login_status.strip():
        query = query.where(LoginHistory.login_status == login_status.strip().lower())

    if date_from is not None:
        query = query.where(LoginHistory.login_at >= date_from)

    if date_to is not None:
        query = query.where(LoginHistory.login_at <= date_to)

    return query


def build_user_login_history_query(
    user_id: int,
    *,
    cutoff: datetime,
) -> Select:
    """Build a query for a user's own login history."""
    return (
        select(LoginHistory)
        .where(
            LoginHistory.user_id == user_id,
            LoginHistory.login_at >= cutoff,
        )
        .order_by(LoginHistory.login_at.desc())
    )


def build_manage_login_history_query(
    *,
    search: str | None = None,
    role: str | None = None,
    login_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select:
    """Build a query for admin login history listing."""
    query = (
        select(
            LoginHistory,
            User.first_name,
            User.last_name,
            User.email.label("user_email"),
            User.role,
        )
        .outerjoin(User, User.id == LoginHistory.user_id)
        .order_by(LoginHistory.login_at.desc())
    )
    return _apply_manage_login_history_filters(
        query,
        search=search,
        role=role,
        login_status=login_status,
        date_from=date_from,
        date_to=date_to,
    )


def build_manage_login_history_count_query(
    *,
    search: str | None = None,
    role: str | None = None,
    login_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select:
    """Build a count query for admin login history listing."""
    query = (
        select(func.count(LoginHistory.id))
        .select_from(LoginHistory)
        .outerjoin(User, User.id == LoginHistory.user_id)
    )
    return _apply_manage_login_history_filters(
        query,
        search=search,
        role=role,
        login_status=login_status,
        date_from=date_from,
        date_to=date_to,
    )


def fetch_manage_login_history_page(
    db: Session,
    *,
    page: int,
    per_page: int,
    search: str | None = None,
    role: str | None = None,
    login_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list, int]:
    """Fetch paginated admin login history rows and total count."""
    normalized_page, normalized_per_page, offset = normalize_pagination(page, per_page)
    total_records = db.scalar(
        build_manage_login_history_count_query(
            search=search,
            role=role,
            login_status=login_status,
            date_from=date_from,
            date_to=date_to,
        )
    ) or 0
    rows = db.execute(
        build_manage_login_history_query(
            search=search,
            role=role,
            login_status=login_status,
            date_from=date_from,
            date_to=date_to,
        )
        .limit(normalized_per_page)
        .offset(offset)
    ).all()
    return rows, int(total_records)


def normalize_login_status_filter(value: str | None) -> str | None:
    """Validate optional login status filter values."""
    if not value or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized not in {LOGIN_STATUS_SUCCESS, LOGIN_STATUS_FAILED}:
        return None
    return normalized
