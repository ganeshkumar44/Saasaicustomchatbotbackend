"""
Chatbot analysis business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chatbot_analysis.schema import (
    ChatbotAnalyticsItem,
    ChatbotAnalyticsSuccessResponse,
)
from app.modules.chatbot_analysis.utils import fetch_chatbot_analytics_rows
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
