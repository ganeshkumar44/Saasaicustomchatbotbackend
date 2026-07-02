"""
Chatbot analysis helper utilities.
"""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.chat_analysis.model import ChatAnalysis
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
    ChatSession,
)
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.user_details.utils import is_admin
from app.modules.widget.model import WidgetVisitor

_TWO_PLACES = Decimal("0.01")


def _apply_eligible_chatbot_filters(query: Select, user: User) -> Select:
    """Apply non-draft chatbot filters and role-based ownership restrictions."""
    query = query.where(Chatbot.status != CHATBOT_STATUS_DRAFT)
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query


def _chat_session_count_subquery():
    """Count chat sessions per chatbot from the source table."""
    return (
        select(func.count(ChatSession.id))
        .where(ChatSession.chatbot_id == Chatbot.id)
        .correlate(Chatbot)
        .scalar_subquery()
    )


def _widget_visitor_count_subquery():
    """Count unique widget visitors per chatbot from the source table."""
    return (
        select(func.count(WidgetVisitor.id))
        .where(WidgetVisitor.chatbot_id == Chatbot.id)
        .correlate(Chatbot)
        .scalar_subquery()
    )


def _resolved_session_count_subquery():
    """Count resolved chat sessions per chatbot from the source table."""
    return (
        select(func.count(ChatSession.id))
        .where(
            ChatSession.chatbot_id == Chatbot.id,
            ChatSession.is_resolved == SESSION_RESOLVED_RESOLVED,
        )
        .correlate(Chatbot)
        .scalar_subquery()
    )


def _unresolved_session_count_subquery():
    """Count unresolved chat sessions per chatbot from the source table."""
    return (
        select(func.count(ChatSession.id))
        .where(
            ChatSession.chatbot_id == Chatbot.id,
            ChatSession.is_resolved == SESSION_RESOLVED_UNRESOLVED,
        )
        .correlate(Chatbot)
        .scalar_subquery()
    )


def build_chatbot_analytics_query(user: User) -> Select:
    """
    Build a query joining chatbots with chat_analysis for dashboard reporting.

    Conversation and visitor counts are read from source tables to avoid
    inflated values in cached chat_analysis counters.
    Administrators see all non-draft chatbots; normal users see only their own.
    """
    session_count = _chat_session_count_subquery()
    visitor_count = _widget_visitor_count_subquery()
    resolved_count = _resolved_session_count_subquery()
    unresolved_count = _unresolved_session_count_subquery()

    query = (
        select(
            Chatbot.id.label("chatbot_id"),
            Chatbot.chatbot_name,
            Chatbot.status,
            Chatbot.ai_model,
            func.coalesce(session_count, 0).label("total_conversations"),
            func.coalesce(visitor_count, 0).label("total_visitors"),
            func.coalesce(resolved_count, 0).label("resolved_conversations"),
            func.coalesce(unresolved_count, 0).label("unresolved_conversations"),
            ChatAnalysis.average_response_time,
            ChatAnalysis.total_messages,
            ChatAnalysis.total_user_messages,
            ChatAnalysis.total_bot_messages,
            ChatAnalysis.created_at,
            ChatAnalysis.updated_at,
        )
        .join(ChatAnalysis, ChatAnalysis.chatbot_id == Chatbot.id)
        .order_by(Chatbot.updated_at.desc())
    )
    return _apply_eligible_chatbot_filters(query, user)


def build_merged_chatbot_analytics_query(user: User) -> Select:
    """Build an aggregate query for merged chatbot analytics overview."""
    session_count = _chat_session_count_subquery()
    visitor_count = _widget_visitor_count_subquery()
    resolved_count = _resolved_session_count_subquery()
    unresolved_count = _unresolved_session_count_subquery()

    query = select(
        func.count(Chatbot.id).label("total_chatbots"),
        func.coalesce(func.sum(session_count), 0).label("total_conversations"),
        func.coalesce(func.sum(visitor_count), 0).label("total_visitors"),
        func.coalesce(func.sum(resolved_count), 0).label("resolved_conversations"),
        func.coalesce(func.sum(unresolved_count), 0).label("unresolved_conversations"),
        func.coalesce(func.sum(ChatAnalysis.total_messages), 0).label("total_messages"),
        func.coalesce(func.sum(ChatAnalysis.total_user_messages), 0).label(
            "total_user_messages"
        ),
        func.coalesce(func.sum(ChatAnalysis.total_bot_messages), 0).label(
            "total_bot_messages"
        ),
        func.coalesce(
            func.sum(
                ChatAnalysis.average_response_time * ChatAnalysis.total_bot_messages
            ),
            0,
        ).label("weighted_response_time_sum"),
    ).join(ChatAnalysis, ChatAnalysis.chatbot_id == Chatbot.id)
    return _apply_eligible_chatbot_filters(query, user)


def fetch_chatbot_analytics_rows(db: Session, user: User) -> list:
    """Execute the chatbot analytics query and return result rows."""
    query = build_chatbot_analytics_query(user)
    return db.execute(query).all()


def fetch_merged_chatbot_analytics_row(db: Session, user: User):
    """Execute the merged chatbot analytics aggregate query."""
    query = build_merged_chatbot_analytics_query(user)
    return db.execute(query).one()


def build_empty_merged_analytics() -> dict[str, int | Decimal]:
    """Return default merged analytics values when no eligible chatbots exist."""
    return {
        "total_chatbots": 0,
        "total_conversations": 0,
        "total_visitors": 0,
        "resolved_conversations": 0,
        "unresolved_conversations": 0,
        "resolution_rate": Decimal("0.00"),
        "average_response_time": Decimal("0.00"),
        "total_messages": 0,
        "total_user_messages": 0,
        "total_bot_messages": 0,
    }


def calculate_merged_resolution_rate(
    resolved_conversations: int,
    unresolved_conversations: int,
) -> Decimal:
    """Calculate merged resolution rate from aggregated conversation totals."""
    total_feedback = resolved_conversations + unresolved_conversations
    if total_feedback <= 0:
        return Decimal("0.00")

    rate = (
        Decimal(resolved_conversations)
        / Decimal(total_feedback)
        * Decimal("100")
    )
    return rate.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_merged_average_response_time(
    weighted_response_time_sum: Decimal,
    total_bot_messages: int,
) -> Decimal:
    """Calculate weighted average response time from aggregated bot message totals."""
    if total_bot_messages <= 0:
        return Decimal("0.00")

    average = weighted_response_time_sum / Decimal(total_bot_messages)
    return average.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
