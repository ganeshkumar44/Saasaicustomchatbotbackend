"""
Graphs module business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT
from app.modules.chatbot_analysis.service import ChatbotAnalyticsNotAvailableError
from app.modules.chatbot_settings.utils import get_owned_chatbot
from app.modules.graphs.schema import (
    ChartSuccessResponse,
    ResolutionChartSuccessResponse,
    ResponseTimeChartSuccessResponse,
)
from app.modules.graphs.utils import (
    build_chart_data_points,
    build_resolution_chart_data_points,
    build_response_time_chart_data_points,
    fetch_conversation_chart_rows,
    fetch_resolution_chart_rows,
    fetch_response_time_chart_rows,
    fetch_unique_visitor_chart_rows,
    get_period_bounds,
    validate_date_range,
)
from app.modules.user_details.utils import is_admin

logger = logging.getLogger(__name__)


def _resolve_scoped_chatbot_id(
    db: Session,
    user: User,
    chatbot_id: int | None,
) -> int | None:
    """Validate chatbot access when a scoped chart is requested."""
    if chatbot_id is None:
        return None

    chatbot = get_owned_chatbot(db, user, chatbot_id)
    if chatbot.status == CHATBOT_STATUS_DRAFT:
        raise ChatbotAnalyticsNotAvailableError(
            "Analytics are not available for draft chatbots."
        )
    return chatbot.id


def get_conversations_chart(
    db: Session,
    user: User,
    date_range: str,
    *,
    chatbot_id: int | None = None,
) -> ChartSuccessResponse:
    """Return conversation counts grouped by the selected chart period."""
    range_key = validate_date_range(date_range)
    period_start, period_end = get_period_bounds(range_key)
    scoped_chatbot_id = _resolve_scoped_chatbot_id(db, user, chatbot_id)

    logger.info(
        "Fetching conversations chart user_id=%s admin=%s range=%s chatbot_id=%s",
        user.id,
        is_admin(user),
        range_key,
        scoped_chatbot_id,
    )

    rows = fetch_conversation_chart_rows(
        db,
        user,
        range_key,
        period_start,
        period_end,
        chatbot_id=scoped_chatbot_id,
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
    *,
    chatbot_id: int | None = None,
) -> ChartSuccessResponse:
    """Return unique visitor counts grouped by the selected chart period."""
    range_key = validate_date_range(date_range)
    period_start, period_end = get_period_bounds(range_key)
    scoped_chatbot_id = _resolve_scoped_chatbot_id(db, user, chatbot_id)

    logger.info(
        "Fetching users chart user_id=%s admin=%s range=%s chatbot_id=%s",
        user.id,
        is_admin(user),
        range_key,
        scoped_chatbot_id,
    )

    rows = fetch_unique_visitor_chart_rows(
        db,
        user,
        range_key,
        period_start,
        period_end,
        chatbot_id=scoped_chatbot_id,
    )
    data = build_chart_data_points(rows, range_key, period_start, period_end)

    logger.info(
        "Users chart fetched user_id=%s range=%s points=%s",
        user.id,
        range_key,
        len(data),
    )

    return ChartSuccessResponse(range=range_key, data=data)


def get_resolution_chart(
    db: Session,
    user: User,
    date_range: str,
    *,
    chatbot_id: int | None = None,
) -> ResolutionChartSuccessResponse:
    """Return resolved vs unresolved session counts grouped by the selected period."""
    range_key = validate_date_range(date_range)
    period_start, period_end = get_period_bounds(range_key)
    scoped_chatbot_id = _resolve_scoped_chatbot_id(db, user, chatbot_id)

    logger.info(
        "Fetching resolution chart user_id=%s admin=%s range=%s chatbot_id=%s",
        user.id,
        is_admin(user),
        range_key,
        scoped_chatbot_id,
    )

    rows = fetch_resolution_chart_rows(
        db,
        user,
        range_key,
        period_start,
        period_end,
        chatbot_id=scoped_chatbot_id,
    )
    data = build_resolution_chart_data_points(
        rows,
        range_key,
        period_start,
        period_end,
    )

    logger.info(
        "Resolution chart fetched user_id=%s range=%s points=%s",
        user.id,
        range_key,
        len(data),
    )

    return ResolutionChartSuccessResponse(range=range_key, data=data)


def get_response_time_chart(
    db: Session,
    user: User,
    date_range: str,
    *,
    chatbot_id: int | None = None,
) -> ResponseTimeChartSuccessResponse:
    """Return average AI response times grouped by the selected period."""
    range_key = validate_date_range(date_range)
    period_start, period_end = get_period_bounds(range_key)
    scoped_chatbot_id = _resolve_scoped_chatbot_id(db, user, chatbot_id)

    logger.info(
        "Fetching response time chart user_id=%s admin=%s range=%s chatbot_id=%s",
        user.id,
        is_admin(user),
        range_key,
        scoped_chatbot_id,
    )

    rows = fetch_response_time_chart_rows(
        db,
        user,
        range_key,
        period_start,
        period_end,
        chatbot_id=scoped_chatbot_id,
    )
    data = build_response_time_chart_data_points(
        rows,
        range_key,
        period_start,
        period_end,
    )

    logger.info(
        "Response time chart fetched user_id=%s range=%s points=%s",
        user.id,
        range_key,
        len(data),
    )

    return ResponseTimeChartSuccessResponse(range=range_key, data=data)
