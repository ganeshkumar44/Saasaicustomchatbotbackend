"""Login history business logic."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.login_history.model import (
    LOGIN_STATUS_FAILED,
    LOGIN_STATUS_SUCCESS,
    LoginHistory,
)
from app.modules.login_history.utils import (
    LoginClientInfo,
    build_user_login_history_query,
    calculate_total_pages,
    fetch_manage_login_history_page,
    normalize_pagination,
    user_login_history_cutoff,
)

logger = logging.getLogger(__name__)


def _apply_client_info(
    record: LoginHistory,
    client_info: LoginClientInfo | None,
) -> None:
    if client_info is None:
        return

    record.ip_address = client_info.ip_address
    record.browser = client_info.browser
    record.operating_system = client_info.operating_system
    record.device_type = client_info.device_type
    record.user_agent = client_info.user_agent


def create_login_history(
    db: Session,
    *,
    user_id: int | None,
    email: str | None,
    login_status: str,
    client_info: LoginClientInfo | None = None,
    jwt_id: str | None = None,
) -> LoginHistory | None:
    """Persist a login history record without interrupting authentication."""
    try:
        session_id = str(uuid.uuid4())
        record = LoginHistory(
            user_id=user_id,
            email=email.strip().lower() if email else None,
            login_status=login_status,
            session_id=session_id,
            jwt_id=jwt_id,
            is_active=login_status == LOGIN_STATUS_SUCCESS,
            login_at=datetime.now(timezone.utc),
        )
        _apply_client_info(record, client_info)
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(
            "Login history recorded status=%s user_id=%s email=%s session_id=%s",
            login_status,
            user_id,
            record.email,
            session_id,
        )
        return record
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to record login history status=%s user_id=%s email=%s",
            login_status,
            user_id,
            email,
        )
        return None


def create_success_login_history(
    db: Session,
    *,
    user_id: int,
    email: str,
    jwt_id: str | None,
    client_info: LoginClientInfo | None = None,
) -> LoginHistory | None:
    """Record a successful sign-in."""
    return create_login_history(
        db,
        user_id=user_id,
        email=email,
        login_status=LOGIN_STATUS_SUCCESS,
        client_info=client_info,
        jwt_id=jwt_id,
    )


def create_failed_login_history(
    db: Session,
    *,
    email: str,
    client_info: LoginClientInfo | None = None,
) -> LoginHistory | None:
    """Record a failed sign-in attempt without linking to a user account."""
    return create_login_history(
        db,
        user_id=None,
        email=email,
        login_status=LOGIN_STATUS_FAILED,
        client_info=client_info,
    )


def update_logout_history(
    db: Session,
    *,
    user_id: int,
    jwt_id: str,
) -> None:
    """Mark the active login history row as signed out for the current JWT."""
    try:
        record = db.execute(
            select(LoginHistory)
            .where(
                LoginHistory.user_id == user_id,
                LoginHistory.jwt_id == jwt_id,
                LoginHistory.is_active.is_(True),
                LoginHistory.login_status == LOGIN_STATUS_SUCCESS,
            )
            .order_by(LoginHistory.login_at.desc())
        ).scalar_one_or_none()

        if record is None:
            record = db.execute(
                select(LoginHistory)
                .where(
                    LoginHistory.user_id == user_id,
                    LoginHistory.is_active.is_(True),
                    LoginHistory.login_status == LOGIN_STATUS_SUCCESS,
                )
                .order_by(LoginHistory.login_at.desc())
            ).scalar_one_or_none()

        if record is None:
            logger.info(
                "No active login history found for logout user_id=%s jwt_id=%s",
                user_id,
                jwt_id,
            )
            return

        now = datetime.now(timezone.utc)
        record.logout_at = now
        record.is_active = False
        record.updated_at = now
        db.commit()
        logger.info(
            "Login history logout recorded user_id=%s login_history_id=%s jwt_id=%s",
            user_id,
            record.id,
            jwt_id,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to update logout history user_id=%s jwt_id=%s",
            user_id,
            jwt_id,
        )


def _serialize_user_login_history_item(
    record: LoginHistory,
    *,
    current_jwt_id: str | None,
) -> dict:
    is_current_session = bool(
        current_jwt_id
        and record.jwt_id == current_jwt_id
        and record.is_active
        and record.login_status == LOGIN_STATUS_SUCCESS
    )
    return {
        "id": record.id,
        "login_at": record.login_at,
        "logout_at": record.logout_at,
        "browser": record.browser,
        "operating_system": record.operating_system,
        "device_type": record.device_type,
        "ip_address": record.ip_address,
        "country": record.country,
        "city": record.city,
        "login_status": record.login_status,
        "is_current_session": is_current_session,
    }


def get_user_login_history(
    db: Session,
    user: User,
    *,
    current_jwt_id: str | None = None,
) -> dict:
    """Return the authenticated user's login history for the last five days."""
    cutoff = user_login_history_cutoff()
    records = db.scalars(
        build_user_login_history_query(user.id, cutoff=cutoff)
    ).all()

    items = [
        _serialize_user_login_history_item(record, current_jwt_id=current_jwt_id)
        for record in records
    ]
    message = (
        messages.LOGIN_HISTORY_NOT_FOUND
        if not items
        else messages.LOGIN_HISTORY_RETRIEVED_SUCCESS
    )
    return {
        "success": True,
        "message": message,
        "data": items,
    }


def get_manage_login_history(
    db: Session,
    admin_user: User,
    *,
    page: int,
    per_page: int,
    search: str | None = None,
    role: str | None = None,
    login_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Return paginated login history for all users (admin/superadmin)."""
    normalized_page, normalized_per_page, _ = normalize_pagination(page, per_page)
    rows, total_records = fetch_manage_login_history_page(
        db,
        page=normalized_page,
        per_page=normalized_per_page,
        search=search,
        role=role,
        login_status=login_status,
        date_from=date_from,
        date_to=date_to,
    )

    items = []
    for row in rows:
        record = row[0]
        first_name = row.first_name
        last_name = row.last_name
        user_email = row.user_email
        user_role = row.role
        full_name = " ".join(
            part for part in [first_name, last_name] if part and str(part).strip()
        ).strip()
        display_email = user_email or record.email
        items.append(
            {
                "id": record.id,
                "user_id": record.user_id,
                "user_name": full_name or None,
                "email": display_email,
                "role": user_role,
                "login_at": record.login_at,
                "logout_at": record.logout_at,
                "browser": record.browser,
                "operating_system": record.operating_system,
                "device_type": record.device_type,
                "ip_address": record.ip_address,
                "country": record.country,
                "city": record.city,
                "login_status": record.login_status,
                "is_current_session": record.is_active
                and record.login_status == LOGIN_STATUS_SUCCESS,
            }
        )

    message = (
        messages.LOGIN_HISTORY_NOT_FOUND
        if not items and total_records == 0
        else messages.LOGIN_HISTORY_RETRIEVED_SUCCESS
    )

    logger.info(
        "Manage login history fetched admin_user_id=%s total_records=%s returned=%s",
        admin_user.id,
        total_records,
        len(items),
    )

    return {
        "success": True,
        "message": message,
        "page": normalized_page,
        "per_page": normalized_per_page,
        "total_records": total_records,
        "total_pages": calculate_total_pages(total_records, normalized_per_page),
        "data": items,
    }
