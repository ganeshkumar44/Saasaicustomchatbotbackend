"""
Chatbot analysis business logic.
"""

import logging

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chatbot_analysis.schema import (
    ChatbotAnalyticsItem,
    ChatbotAnalyticsSuccessResponse,
    MergedChatbotAnalyticsData,
    MergedChatbotAnalyticsSuccessResponse,
)
from app.modules.chatbot_analysis.utils import (
    build_empty_merged_analytics,
    build_metric_comparison,
    calculate_merged_average_response_time,
    calculate_merged_resolution_rate,
    fetch_chatbot_analytics_rows,
    fetch_merged_chatbot_analytics_row,
    fetch_merged_period_comparison_metrics,
    get_merged_analytics_period_bounds,
)
from app.modules.user_details.utils import is_admin

logger = logging.getLogger(__name__)


def get_chatbot_analytics_details(
    db: Session,
    user: User,
) -> ChatbotAnalyticsSuccessResponse:
    """Return chatbot analytics for the analytics dashboard."""
    logger.info(
        "Fetching chatbot analytics for user_id=%s role=%s admin=%s",
        user.id,
        user.role,
        is_admin(user),
    )

    rows = fetch_chatbot_analytics_rows(db, user)
    items = [
        ChatbotAnalyticsItem(
            chatbot_id=row.chatbot_id,
            chatbot_name=row.chatbot_name,
            status=row.status,
            ai_model=row.ai_model,
            total_conversations=int(row.total_conversations),
            total_visitors=int(row.total_visitors),
            resolved_conversations=int(row.resolved_conversations),
            unresolved_conversations=int(row.unresolved_conversations),
            resolution_rate=calculate_merged_resolution_rate(
                int(row.resolved_conversations),
                int(row.unresolved_conversations),
            ),
            average_response_time=row.average_response_time,
            total_messages=int(row.total_messages),
            total_user_messages=int(row.total_user_messages),
            total_bot_messages=int(row.total_bot_messages),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]

    message = (
        messages.CHATBOT_ANALYTICS_SUCCESS
        if items
        else messages.NO_CHATBOT_ANALYTICS
    )

    logger.info(
        "Chatbot analytics fetched for user_id=%s total_chatbots=%s",
        user.id,
        len(items),
    )

    return ChatbotAnalyticsSuccessResponse(
        message=message,
        total_chatbots=len(items),
        data=items,
    )


def get_merged_chatbot_analytics_details(
    db: Session,
    user: User,
) -> MergedChatbotAnalyticsSuccessResponse:
    """Return merged chatbot analytics for the dashboard overview page."""
    current_start, current_end, previous_start, previous_end = (
        get_merged_analytics_period_bounds()
    )
    logger.info(
        "Fetching merged chatbot analytics for user_id=%s role=%s admin=%s "
        "current_period=%s to %s previous_period=%s to %s",
        user.id,
        user.role,
        is_admin(user),
        current_start.isoformat(),
        current_end.isoformat(),
        previous_start.isoformat(),
        previous_end.isoformat(),
    )

    row = fetch_merged_chatbot_analytics_row(db, user)
    total_chatbots = int(row.total_chatbots or 0)

    if total_chatbots == 0:
        data = MergedChatbotAnalyticsData(**build_empty_merged_analytics())
        return MergedChatbotAnalyticsSuccessResponse(
            message=messages.NO_CHATBOT_ANALYTICS,
            data=data,
        )

    period_metrics = fetch_merged_period_comparison_metrics(db, user)
    current_period = period_metrics.current
    previous_period = period_metrics.previous

    current_resolution_rate = calculate_merged_resolution_rate(
        current_period.resolved_conversations,
        current_period.unresolved_conversations,
    )
    previous_resolution_rate = calculate_merged_resolution_rate(
        previous_period.resolved_conversations,
        previous_period.unresolved_conversations,
    )

    conversations_change, conversations_trend = build_metric_comparison(
        current_period.total_conversations,
        previous_period.total_conversations,
    )
    visitors_change, visitors_trend = build_metric_comparison(
        current_period.total_visitors,
        previous_period.total_visitors,
    )
    resolution_rate_change, resolution_rate_trend = build_metric_comparison(
        current_resolution_rate,
        previous_resolution_rate,
    )
    response_time_change, response_time_trend = build_metric_comparison(
        current_period.average_response_time,
        previous_period.average_response_time,
    )

    resolved_conversations = int(row.resolved_conversations or 0)
    unresolved_conversations = int(row.unresolved_conversations or 0)
    total_bot_messages = int(row.total_bot_messages or 0)

    data = MergedChatbotAnalyticsData(
        total_chatbots=total_chatbots,
        total_conversations=current_period.total_conversations,
        total_conversations_change=conversations_change,
        total_conversations_trend=conversations_trend,
        total_visitors=current_period.total_visitors,
        total_visitors_change=visitors_change,
        total_visitors_trend=visitors_trend,
        resolved_conversations=resolved_conversations,
        unresolved_conversations=unresolved_conversations,
        resolution_rate=current_resolution_rate,
        resolution_rate_change=resolution_rate_change,
        resolution_rate_trend=resolution_rate_trend,
        average_response_time=current_period.average_response_time,
        average_response_time_change=response_time_change,
        average_response_time_trend=response_time_trend,
        total_messages=int(row.total_messages or 0),
        total_user_messages=int(row.total_user_messages or 0),
        total_bot_messages=total_bot_messages,
    )

    logger.info(
        "Merged chatbot analytics fetched for user_id=%s total_chatbots=%s "
        "current_conversations=%s previous_conversations=%s "
        "current_visitors=%s previous_visitors=%s",
        user.id,
        data.total_chatbots,
        current_period.total_conversations,
        previous_period.total_conversations,
        current_period.total_visitors,
        previous_period.total_visitors,
    )

    return MergedChatbotAnalyticsSuccessResponse(
        message=messages.MERGED_CHATBOT_ANALYTICS_SUCCESS,
        data=data,
    )
