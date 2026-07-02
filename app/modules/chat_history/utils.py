"""
Chat History module helper utilities.
"""

import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_sessions.model import ChatSession
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.dashboard.utils import compute_conversation_status
from app.modules.user_details.utils import is_admin

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100


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


def _apply_eligible_chatbot_filters(query: Select, user: User) -> Select:
    """Restrict chat history queries to non-draft chatbots and role-based access."""
    query = query.where(Chatbot.status != CHATBOT_STATUS_DRAFT)
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query


def _message_counts_subquery():
    """Aggregate total messages per chat session."""
    return (
        select(
            ChatMessage.chat_session_id.label("chat_session_id"),
            func.count(ChatMessage.id).label("total_messages"),
        )
        .group_by(ChatMessage.chat_session_id)
        .subquery()
    )


def _first_message_subquery():
    """Select the first user message per chat session ordered by creation time."""
    ranked_messages = (
        select(
            ChatMessage.chat_session_id.label("chat_session_id"),
            ChatMessage.user_message.label("user_message"),
            func.row_number()
            .over(
                partition_by=ChatMessage.chat_session_id,
                order_by=(ChatMessage.created_at.asc(), ChatMessage.id.asc()),
            )
            .label("row_num"),
        )
    ).subquery()

    return (
        select(
            ranked_messages.c.chat_session_id,
            ranked_messages.c.user_message,
        )
        .where(ranked_messages.c.row_num == 1)
        .subquery()
    )


def build_chat_sessions_list_query(user: User) -> Select:
    """Build the base query for paginated chat session listing."""
    message_counts = _message_counts_subquery()
    first_messages = _first_message_subquery()

    query = (
        select(
            ChatSession.id.label("chat_session_id"),
            Chatbot.id.label("chatbot_id"),
            Chatbot.chatbot_name,
            ChatSession.visitor_id.label("visitor_name"),
            ChatSession.visitor_email,
            first_messages.c.user_message.label("first_message"),
            func.coalesce(message_counts.c.total_messages, 0).label("total_messages"),
            ChatSession.started_at.label("session_started_at"),
            ChatSession.last_activity,
            ChatSession.is_active,
            ChatSession.is_resolved,
        )
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
        .outerjoin(message_counts, message_counts.c.chat_session_id == ChatSession.id)
        .outerjoin(first_messages, first_messages.c.chat_session_id == ChatSession.id)
        .order_by(ChatSession.started_at.desc())
    )
    return _apply_eligible_chatbot_filters(query, user)


def build_chat_sessions_count_query(user: User) -> Select:
    """Build a count query for eligible chat sessions."""
    query = (
        select(func.count(ChatSession.id))
        .select_from(ChatSession)
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
    )
    return _apply_eligible_chatbot_filters(query, user)


def fetch_chat_sessions_page(
    db: Session,
    user: User,
    *,
    page: int,
    per_page: int,
) -> tuple[list, int]:
    """Fetch a paginated page of chat session list rows and the total record count."""
    normalized_page, normalized_per_page, offset = normalize_pagination(page, per_page)

    total_records = db.scalar(build_chat_sessions_count_query(user)) or 0
    rows = db.execute(
        build_chat_sessions_list_query(user)
        .limit(normalized_per_page)
        .offset(offset)
    ).all()

    return rows, int(total_records)


def fetch_accessible_chat_session_row(
    db: Session,
    user: User,
    chat_session_id: int,
):
    """Return a chat session row when the user can access it; otherwise None."""
    query = (
        select(
            ChatSession.id.label("chat_session_id"),
            Chatbot.id.label("chatbot_id"),
            Chatbot.chatbot_name,
            ChatSession.visitor_id.label("visitor_name"),
            ChatSession.visitor_email,
            ChatSession.started_at.label("session_started_at"),
            ChatSession.is_active,
            ChatSession.is_resolved,
        )
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
        .where(ChatSession.id == chat_session_id)
    )
    query = _apply_eligible_chatbot_filters(query, user)
    return db.execute(query).one_or_none()


def fetch_chat_session_messages(
    db: Session,
    chat_session_id: int,
) -> list:
    """Return all messages for a chat session in chronological order."""
    query = (
        select(
            ChatMessage.user_message,
            ChatMessage.bot_response,
            ChatMessage.response_time,
            ChatMessage.created_at,
        )
        .where(ChatMessage.chat_session_id == chat_session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    return db.execute(query).all()


def map_session_status(is_active: str, is_resolved: str) -> str:
    """Map session lifecycle fields to a single chat history status label."""
    return compute_conversation_status(is_active, is_resolved)
