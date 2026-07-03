"""
Chatbot analysis helper utilities.
"""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.chat_analysis.model import ChatAnalysis
from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
    ChatSession,
)
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.user_details.utils import is_admin
from app.modules.widget.model import WidgetVisitor

_TWO_PLACES = Decimal("0.01")
PERIOD_DAYS = 30
AnalyticsTrend = Literal["up", "down", "neutral"]


class PeriodAnalyticsMetrics(NamedTuple):
    """Aggregated dashboard metrics for a single 30-day window."""

    total_conversations: int
    total_visitors: int
    resolved_conversations: int
    unresolved_conversations: int
    average_response_time: Decimal


class PeriodComparisonMetrics(NamedTuple):
    """Current and previous 30-day dashboard metrics."""

    current: PeriodAnalyticsMetrics
    previous: PeriodAnalyticsMetrics


def get_merged_analytics_period_bounds(
    reference: datetime | None = None,
) -> tuple[datetime, datetime, datetime, datetime]:
    """
    Return UTC bounds for current and previous 30-day dashboard periods.

    The current period covers the last 30 calendar days ending today (inclusive).
    The previous period is the 30 days immediately before the current period.
    """
    now = reference or datetime.now(timezone.utc)
    end_date = now.date()
    current_start_date = end_date - timedelta(days=PERIOD_DAYS - 1)
    previous_end_date = current_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=PERIOD_DAYS - 1)

    current_start = datetime.combine(current_start_date, time.min, tzinfo=timezone.utc)
    current_end = now
    previous_start = datetime.combine(previous_start_date, time.min, tzinfo=timezone.utc)
    previous_end = datetime.combine(
        previous_end_date,
        time.max.replace(microsecond=0),
        tzinfo=timezone.utc,
    )
    return current_start, current_end, previous_start, previous_end


def _apply_eligible_chatbot_filters(query: Select, user: User) -> Select:
    """Apply non-draft, non-deleted chatbot filters and role-based ownership restrictions."""
    query = query.where(
        Chatbot.status != CHATBOT_STATUS_DRAFT,
        Chatbot.is_deleted.is_(False),
    )
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


def _merged_session_count_subquery(
    user: User,
    period_start: datetime,
    period_end: datetime,
    *,
    resolution_status: str | None = None,
):
    """Count chat sessions in a period for eligible chatbots."""
    query = (
        select(func.count(ChatSession.id))
        .select_from(ChatSession)
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
        .where(
            Chatbot.status != CHATBOT_STATUS_DRAFT,
            Chatbot.is_deleted.is_(False),
            ChatSession.created_at >= period_start,
            ChatSession.created_at <= period_end,
        )
    )
    if resolution_status is not None:
        query = query.where(ChatSession.is_resolved == resolution_status)
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query.scalar_subquery()


def _merged_visitor_count_subquery(
    user: User,
    period_start: datetime,
    period_end: datetime,
):
    """Count widget visitors created in a period for eligible chatbots."""
    query = (
        select(func.count(WidgetVisitor.id))
        .select_from(WidgetVisitor)
        .join(Chatbot, Chatbot.id == WidgetVisitor.chatbot_id)
        .where(
            Chatbot.status != CHATBOT_STATUS_DRAFT,
            Chatbot.is_deleted.is_(False),
            WidgetVisitor.created_at >= period_start,
            WidgetVisitor.created_at <= period_end,
        )
    )
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query.scalar_subquery()


def _merged_average_response_time_subquery(
    user: User,
    period_start: datetime,
    period_end: datetime,
):
    """Average bot response time in a period for eligible chatbots."""
    query = (
        select(func.avg(ChatMessage.response_time))
        .select_from(ChatMessage)
        .join(Chatbot, Chatbot.id == ChatMessage.chatbot_id)
        .where(
            Chatbot.status != CHATBOT_STATUS_DRAFT,
            Chatbot.is_deleted.is_(False),
            ChatMessage.created_at >= period_start,
            ChatMessage.created_at <= period_end,
            ChatMessage.response_time.is_not(None),
        )
    )
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query.scalar_subquery()


def _normalize_average_response_time(value) -> Decimal:
    """Convert a SQL average response time value to a 2-decimal Decimal."""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _build_period_metrics(
    *,
    total_conversations,
    total_visitors,
    resolved_conversations,
    unresolved_conversations,
    average_response_time,
) -> PeriodAnalyticsMetrics:
    """Map SQL aggregate values to period analytics metrics."""
    return PeriodAnalyticsMetrics(
        total_conversations=int(total_conversations or 0),
        total_visitors=int(total_visitors or 0),
        resolved_conversations=int(resolved_conversations or 0),
        unresolved_conversations=int(unresolved_conversations or 0),
        average_response_time=_normalize_average_response_time(average_response_time),
    )


def build_merged_period_comparison_query(
    user: User,
    current_start: datetime,
    current_end: datetime,
    previous_start: datetime,
    previous_end: datetime,
) -> Select:
    """Build one aggregate query for current and previous 30-day dashboard metrics."""
    return select(
        _merged_session_count_subquery(user, current_start, current_end).label(
            "current_total_conversations"
        ),
        _merged_visitor_count_subquery(user, current_start, current_end).label(
            "current_total_visitors"
        ),
        _merged_session_count_subquery(
            user,
            current_start,
            current_end,
            resolution_status=SESSION_RESOLVED_RESOLVED,
        ).label("current_resolved_conversations"),
        _merged_session_count_subquery(
            user,
            current_start,
            current_end,
            resolution_status=SESSION_RESOLVED_UNRESOLVED,
        ).label("current_unresolved_conversations"),
        _merged_average_response_time_subquery(user, current_start, current_end).label(
            "current_average_response_time"
        ),
        _merged_session_count_subquery(user, previous_start, previous_end).label(
            "previous_total_conversations"
        ),
        _merged_visitor_count_subquery(user, previous_start, previous_end).label(
            "previous_total_visitors"
        ),
        _merged_session_count_subquery(
            user,
            previous_start,
            previous_end,
            resolution_status=SESSION_RESOLVED_RESOLVED,
        ).label("previous_resolved_conversations"),
        _merged_session_count_subquery(
            user,
            previous_start,
            previous_end,
            resolution_status=SESSION_RESOLVED_UNRESOLVED,
        ).label("previous_unresolved_conversations"),
        _merged_average_response_time_subquery(user, previous_start, previous_end).label(
            "previous_average_response_time"
        ),
    )


def fetch_merged_period_comparison_metrics(
    db: Session,
    user: User,
    reference: datetime | None = None,
) -> PeriodComparisonMetrics:
    """Fetch current and previous 30-day merged analytics in a single query."""
    current_start, current_end, previous_start, previous_end = (
        get_merged_analytics_period_bounds(reference)
    )
    row = db.execute(
        build_merged_period_comparison_query(
            user,
            current_start,
            current_end,
            previous_start,
            previous_end,
        )
    ).one()

    current = _build_period_metrics(
        total_conversations=row.current_total_conversations,
        total_visitors=row.current_total_visitors,
        resolved_conversations=row.current_resolved_conversations,
        unresolved_conversations=row.current_unresolved_conversations,
        average_response_time=row.current_average_response_time,
    )
    previous = _build_period_metrics(
        total_conversations=row.previous_total_conversations,
        total_visitors=row.previous_total_visitors,
        resolved_conversations=row.previous_resolved_conversations,
        unresolved_conversations=row.previous_unresolved_conversations,
        average_response_time=row.previous_average_response_time,
    )
    return PeriodComparisonMetrics(current=current, previous=previous)


def calculate_percentage_change(
    current: Decimal | int | float,
    previous: Decimal | int | float,
) -> Decimal:
    """
    Calculate percentage change between current and previous values.

    When the previous value is zero, returns 100.00 if current is positive,
    otherwise 0.00. Never divides by zero.
    """
    current_value = Decimal(str(current))
    previous_value = Decimal(str(previous))

    if previous_value == 0:
        if current_value > 0:
            return Decimal("100.00")
        return Decimal("0.00")

    change = ((current_value - previous_value) / previous_value) * Decimal("100")
    return change.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_trend(
    current: Decimal | int | float,
    previous: Decimal | int | float,
) -> AnalyticsTrend:
    """Return the trend direction comparing current and previous values."""
    current_value = Decimal(str(current))
    previous_value = Decimal(str(previous))

    if current_value > previous_value:
        return "up"
    if current_value < previous_value:
        return "down"
    return "neutral"


def build_metric_comparison(
    current: Decimal | int | float,
    previous: Decimal | int | float,
) -> tuple[Decimal, AnalyticsTrend]:
    """Return percentage change and trend for a metric comparison."""
    return (
        calculate_percentage_change(current, previous),
        calculate_trend(current, previous),
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


def build_empty_merged_analytics() -> dict[str, int | Decimal | AnalyticsTrend]:
    """Return default merged analytics values when no eligible chatbots exist."""
    return {
        "total_chatbots": 0,
        "total_conversations": 0,
        "total_conversations_change": Decimal("0.00"),
        "total_conversations_trend": "neutral",
        "total_visitors": 0,
        "total_visitors_change": Decimal("0.00"),
        "total_visitors_trend": "neutral",
        "resolved_conversations": 0,
        "unresolved_conversations": 0,
        "resolution_rate": Decimal("0.00"),
        "resolution_rate_change": Decimal("0.00"),
        "resolution_rate_trend": "neutral",
        "average_response_time": Decimal("0.00"),
        "average_response_time_change": Decimal("0.00"),
        "average_response_time_trend": "neutral",
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
