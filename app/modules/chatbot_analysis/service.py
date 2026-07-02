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
    calculate_merged_average_response_time,
    calculate_merged_resolution_rate,
    fetch_chatbot_analytics_rows,
    fetch_merged_chatbot_analytics_row,
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
            resolution_rate=row.resolution_rate,
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
    logger.info(
        "Fetching merged chatbot analytics for user_id=%s role=%s admin=%s",
        user.id,
        user.role,
        is_admin(user),
    )

    row = fetch_merged_chatbot_analytics_row(db, user)
    total_chatbots = int(row.total_chatbots or 0)

    if total_chatbots == 0:
        data = MergedChatbotAnalyticsData(**build_empty_merged_analytics())
        return MergedChatbotAnalyticsSuccessResponse(
            message=messages.NO_CHATBOT_ANALYTICS,
            data=data,
        )

    resolved_conversations = int(row.resolved_conversations or 0)
    unresolved_conversations = int(row.unresolved_conversations or 0)
    total_bot_messages = int(row.total_bot_messages or 0)

    data = MergedChatbotAnalyticsData(
        total_chatbots=total_chatbots,
        total_conversations=int(row.total_conversations or 0),
        total_visitors=int(row.total_visitors or 0),
        resolved_conversations=resolved_conversations,
        unresolved_conversations=unresolved_conversations,
        resolution_rate=calculate_merged_resolution_rate(
            resolved_conversations,
            unresolved_conversations,
        ),
        average_response_time=calculate_merged_average_response_time(
            Decimal(str(row.weighted_response_time_sum or 0)),
            total_bot_messages,
        ),
        total_messages=int(row.total_messages or 0),
        total_user_messages=int(row.total_user_messages or 0),
        total_bot_messages=total_bot_messages,
    )

    logger.info(
        "Merged chatbot analytics fetched for user_id=%s total_chatbots=%s",
        user.id,
        data.total_chatbots,
    )

    return MergedChatbotAnalyticsSuccessResponse(
        message=messages.MERGED_CHATBOT_ANALYTICS_SUCCESS,
        data=data,
    )
