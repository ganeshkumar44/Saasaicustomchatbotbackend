"""
Graphs module business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.graphs.schema import ChartSuccessResponse
from app.modules.graphs.utils import (
    build_chart_data_points,
    fetch_conversation_chart_rows,
    fetch_unique_visitor_chart_rows,
    get_period_bounds,
    validate_date_range,
)
from app.modules.user_details.utils import is_admin

logger = logging.getLogger(__name__)


def get_conversations_chart(
    db: Session,
    user: User,
    date_range: str,
) -> ChartSuccessResponse:
    """Return conversation counts grouped by the selected chart period."""
    range_key = validate_date_range(date_range)
    period_start, period_end = get_period_bounds(range_key)

    logger.info(
        "Fetching conversations chart user_id=%s admin=%s range=%s",
        user.id,
        is_admin(user),
        range_key,
    )

    rows = fetch_conversation_chart_rows(
        db,
        user,
        range_key,
        period_start,
        period_end,
    )
    data = build_chart_data_points(rows, range_key, period_start, period_end)

    logger.info(
        "Conversations chart fetched user_id=%s range=%s points=%s",
        user.id,
        range_key,
        len(data),
    )

    return ChartSuccessResponse(range=range_key, data=data)


def get_users_chart(
    db: Session,
    user: User,
    date_range: str,
) -> ChartSuccessResponse:
    """Return unique visitor counts grouped by the selected chart period."""
    range_key = validate_date_range(date_range)
    period_start, period_end = get_period_bounds(range_key)

    logger.info(
        "Fetching users chart user_id=%s admin=%s range=%s",
        user.id,
        is_admin(user),
        range_key,
    )

    rows = fetch_unique_visitor_chart_rows(
        db,
        user,
        range_key,
        period_start,
        period_end,
    )
    data = build_chart_data_points(rows, range_key, period_start, period_end)

    logger.info(
        "Users chart fetched user_id=%s range=%s points=%s",
        user.id,
        range_key,
        len(data),
    )

    return ChartSuccessResponse(range=range_key, data=data)
