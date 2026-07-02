"""
Chat History module business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chat_history.schema import (
    ChatHistoryDetailData,
    ChatHistoryDetailSuccessResponse,
    ChatHistoryMessageItem,
    ChatSessionListItem,
    ChatSessionListSuccessResponse,
)
from app.modules.chat_history.utils import (
    calculate_total_pages,
    fetch_accessible_chat_session_row,
    fetch_chat_session_messages,
    fetch_chat_sessions_page,
    map_session_status,
    normalize_pagination,
)
from app.modules.user_details.utils import is_admin

logger = logging.getLogger(__name__)


class ChatSessionNotFoundError(Exception):
    """Raised when a chat session does not exist or is not accessible."""


def get_chat_sessions(
    db: Session,
    user: User,
    *,
    page: int,
    per_page: int,
) -> ChatSessionListSuccessResponse:
    """Return a paginated list of chat sessions for the chat history page."""
    normalized_page, normalized_per_page, _ = normalize_pagination(page, per_page)

    logger.info(
        "Fetching chat session list user_id=%s admin=%s page=%s per_page=%s",
        user.id,
        is_admin(user),
        normalized_page,
        normalized_per_page,
    )

    rows, total_records = fetch_chat_sessions_page(
        db,
        user,
        page=normalized_page,
        per_page=normalized_per_page,
    )
    total_pages = calculate_total_pages(total_records, normalized_per_page)

    items = [
        ChatSessionListItem(
            chat_session_id=row.chat_session_id,
            chatbot_id=row.chatbot_id,
            chatbot_name=row.chatbot_name,
            visitor_name=row.visitor_name,
            visitor_email=row.visitor_email,
            first_message=row.first_message,
            total_messages=int(row.total_messages),
            session_started_at=row.session_started_at,
            last_activity=row.last_activity,
            status=map_session_status(row.is_active, row.is_resolved),
        )
        for row in rows
    ]

    message = messages.CHAT_SESSION_LIST_SUCCESS

    logger.info(
        "Chat session list fetched user_id=%s total_records=%s returned=%s",
        user.id,
        total_records,
        len(items),
    )

    return ChatSessionListSuccessResponse(
        message=message,
        page=normalized_page,
        per_page=normalized_per_page,
        total_records=total_records,
        total_pages=total_pages,
        data=items,
    )


def get_chat_session_history(
    db: Session,
    user: User,
    chat_session_id: int,
) -> ChatHistoryDetailSuccessResponse:
    """Return the complete conversation history for a single chat session."""
    logger.info(
        "Fetching chat session history user_id=%s admin=%s chat_session_id=%s",
        user.id,
        is_admin(user),
        chat_session_id,
    )

    session_row = fetch_accessible_chat_session_row(db, user, chat_session_id)
    if session_row is None:
        logger.warning(
            "Chat session not found or inaccessible user_id=%s chat_session_id=%s",
            user.id,
            chat_session_id,
        )
        raise ChatSessionNotFoundError()

    message_rows = fetch_chat_session_messages(db, chat_session_id)
    messages_data = [
        ChatHistoryMessageItem(
            user_message=row.user_message,
            bot_response=row.bot_response,
            response_time=row.response_time,
            created_at=row.created_at,
        )
        for row in message_rows
    ]

    data = ChatHistoryDetailData(
        chat_session_id=session_row.chat_session_id,
        chatbot_id=session_row.chatbot_id,
        chatbot_name=session_row.chatbot_name,
        visitor_name=session_row.visitor_name,
        visitor_email=session_row.visitor_email,
        session_started_at=session_row.session_started_at,
        status=map_session_status(session_row.is_active, session_row.is_resolved),
        messages=messages_data,
    )

    logger.info(
        "Chat session history fetched user_id=%s chat_session_id=%s messages=%s",
        user.id,
        chat_session_id,
        len(messages_data),
    )

    return ChatHistoryDetailSuccessResponse(
        message=messages.CHAT_HISTORY_SUCCESS,
        data=data,
    )
