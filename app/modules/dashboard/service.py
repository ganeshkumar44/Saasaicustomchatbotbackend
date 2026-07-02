"""
Dashboard module business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.dashboard.schema import (
    ChatbotListItem,
    ChatbotListSuccessResponse,
    RecentConversationItem,
    RecentConversationsSuccessResponse,
)
from app.modules.dashboard.utils import (
    compute_conversation_status,
    fetch_chatbot_list_rows,
    fetch_recent_conversation_rows,
    format_chatbot_owner_name,
)
from app.modules.user_details.utils import is_admin

logger = logging.getLogger(__name__)


def get_chatbot_list(db: Session, user: User) -> ChatbotListSuccessResponse:
    """Return the dashboard chatbot list for the authenticated user."""
    logger.info(
        "Fetching chatbot list for user_id=%s role=%s admin=%s",
        user.id,
        user.role,
        is_admin(user),
    )

    rows = fetch_chatbot_list_rows(db, user)
    items = [
        ChatbotListItem(
            chatbot_id=row.chatbot_id,
            chatbot_name=row.chatbot_name,
            description=row.description,
            ai_model=row.ai_model,
            language=row.language,
            status=row.status,
            public_key=row.public_key,
            total_conversations=int(row.total_conversations),
            total_messages=int(row.total_messages),
            total_uploaded_documents=int(row.total_uploaded_documents),
            created_at=row.created_at,
            updated_at=row.updated_at,
            owner_name=format_chatbot_owner_name(
                row.owner_user_id,
                user,
                row.owner_first_name,
                row.owner_last_name,
            ),
        )
        for row in rows
    ]

    message = messages.CHATBOT_LIST_SUCCESS if items else messages.NO_CHATBOTS_FOUND

    logger.info(
        "Chatbot list fetched for user_id=%s total_chatbots=%s",
        user.id,
        len(items),
    )

    return ChatbotListSuccessResponse(
        message=message,
        total_chatbots=len(items),
        data=items,
    )


def get_recent_conversations(db: Session, user: User) -> RecentConversationsSuccessResponse:
    """Return the latest conversations for the dashboard recent conversations section."""
    logger.info(
        "Fetching recent conversations for user_id=%s role=%s admin=%s",
        user.id,
        user.role,
        is_admin(user),
    )

    rows = fetch_recent_conversation_rows(db, user)
    items = [
        RecentConversationItem(
            chat_session_id=row.chat_session_id,
            chatbot_id=row.chatbot_id,
            chatbot_name=row.chatbot_name,
            visitor_name=row.visitor_name,
            user_question=row.user_question,
            message_time=row.message_time,
            status=compute_conversation_status(
                row.session_status,
                row.resolution_status,
            ),
        )
        for row in rows
    ]

    message = (
        messages.RECENT_CONVERSATIONS_SUCCESS
        if items
        else messages.NO_RECENT_CONVERSATIONS
    )

    logger.info(
        "Recent conversations fetched for user_id=%s total=%s",
        user.id,
        len(items),
    )

    return RecentConversationsSuccessResponse(message=message, data=items)
