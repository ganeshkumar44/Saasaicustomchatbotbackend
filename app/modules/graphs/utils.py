"""
Graphs module helper utilities.
"""

import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
    ChatSession,
)
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.graphs.schema import (
    ChartDataPoint,
    ResolutionChartDataPoint,
    ResponseTimeChartDataPoint,
)
from app.modules.user_details.utils import is_admin

_TWO_PLACES = Decimal("0.01")

ALLOWED_DATE_RANGES = frozenset({"7d", "30d", "3m", "6m", "1y"})
DEFAULT_DATE_RANGE = "7d"

RANGE_DAY_COUNTS = {
    "7d": 7,
    "30d": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}


class InvalidDateRangeError(Exception):
    """Raised when an unsupported chart date range is requested."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_date_range(value: str) -> str:
    """Validate and return a supported chart date range."""
    normalized = value.strip().lower() if value else DEFAULT_DATE_RANGE
    if normalized not in ALLOWED_DATE_RANGES:
        raise InvalidDateRangeError(messages.INVALID_DATE_RANGE)
    return normalized


def get_period_bounds(range_key: str) -> tuple[datetime, datetime]:
    """Return inclusive UTC bounds for the selected chart range."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=RANGE_DAY_COUNTS[range_key])
    return period_start, now


def _truncate_to_date(value: datetime | date) -> date:
    """Normalize a datetime or date value to a date."""
    if isinstance(value, datetime):
        return value.date()
    return value


def _month_start(value: date) -> date:
    """Return the first day of the month for a given date."""
    return date(value.year, value.month, 1)


def _add_months(value: date, months: int) -> date:
    """Shift a date to the first day of a month offset."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _week_index(period_start: date, bucket_date: date) -> int:
    """Return a 1-based week index relative to the chart period start."""
    return ((bucket_date - period_start).days // 7) + 1


def _build_bucket_key(range_key: str, period_start: date, bucket_value: datetime | date) -> str:
    """Build a stable bucket key for merging SQL aggregates with chart labels."""
    bucket_date = _truncate_to_date(bucket_value)

    if range_key in {"7d", "30d"}:
        return bucket_date.isoformat()

    if range_key == "3m":
        return f"week_{_week_index(period_start, bucket_date)}"

    month_start = _month_start(bucket_date)
    return f"{month_start.year:04d}-{month_start.month:02d}"


def generate_chart_label_specs(
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list[tuple[str, str]]:
    """Return ordered bucket keys and display labels for a chart range."""
    end_date = _truncate_to_date(period_end)
    specs: list[tuple[str, str]] = []

    if range_key == "7d":
        start_date = end_date - timedelta(days=RANGE_DAY_COUNTS["7d"] - 1)
        for offset in range(RANGE_DAY_COUNTS["7d"]):
            current = start_date + timedelta(days=offset)
            specs.append((current.isoformat(), current.strftime("%a")))
        return specs

    if range_key == "30d":
        start_date = end_date - timedelta(days=RANGE_DAY_COUNTS["30d"] - 1)
        for offset in range(RANGE_DAY_COUNTS["30d"]):
            current = start_date + timedelta(days=offset)
            specs.append((current.isoformat(), current.strftime("%d %b")))
        return specs

    if range_key == "3m":
        period_start_date = _truncate_to_date(period_start)
        total_weeks = (RANGE_DAY_COUNTS["3m"] + 6) // 7
        for week_number in range(1, total_weeks + 1):
            specs.append((f"week_{week_number}", f"Week {week_number}"))
        return specs

    month_count = 6 if range_key == "6m" else 12
    month_cursor = _month_start(end_date)
    month_starts = [_add_months(month_cursor, -offset) for offset in range(month_count - 1, -1, -1)]

    for month_start in month_starts:
        bucket_key = f"{month_start.year:04d}-{month_start.month:02d}"
        specs.append((bucket_key, calendar.month_abbr[month_start.month]))

    return specs


def _get_bucket_expression(range_key: str):
    """Return the SQL expression used to bucket chat session timestamps."""
    if range_key in {"7d", "30d"}:
        return func.date_trunc("day", ChatSession.created_at)
    if range_key == "3m":
        return func.date_trunc("week", ChatSession.created_at)
    return func.date_trunc("month", ChatSession.created_at)


def _apply_eligible_chatbot_session_filters(
    query,
    user: User,
    period_start: datetime,
    period_end: datetime,
):
    """Restrict chart queries to eligible chatbots and the requested period."""
    query = (
        query.select_from(ChatSession)
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
        .where(Chatbot.status != CHATBOT_STATUS_DRAFT)
        .where(Chatbot.is_deleted.is_(False))
        .where(ChatSession.created_at >= period_start)
        .where(ChatSession.created_at <= period_end)
    )
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query


def fetch_conversation_chart_rows(
    db: Session,
    user: User,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list:
    """Aggregate conversation counts from chat sessions for the chart period."""
    bucket_expression = _get_bucket_expression(range_key).label("bucket")
    query = select(
        bucket_expression,
        func.count(ChatSession.id).label("value"),
    ).group_by(bucket_expression).order_by(bucket_expression)

    query = _apply_eligible_chatbot_session_filters(
        query,
        user,
        period_start,
        period_end,
    )
    return db.execute(query).all()


def fetch_unique_visitor_chart_rows(
    db: Session,
    user: User,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list:
    """Aggregate unique visitor counts from chat sessions for the chart period."""
    bucket_expression = _get_bucket_expression(range_key).label("bucket")
    visitor_identifier = func.coalesce(ChatSession.visitor_id, ChatSession.session_id)
    query = select(
        bucket_expression,
        func.count(func.distinct(visitor_identifier)).label("value"),
    ).group_by(bucket_expression).order_by(bucket_expression)

    query = _apply_eligible_chatbot_session_filters(
        query,
        user,
        period_start,
        period_end,
    )
    return db.execute(query).all()


def build_chart_data_points(
    rows: list,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list[ChartDataPoint]:
    """Map aggregated SQL rows to ordered chart data points with zero-filled gaps."""
    period_start_date = _truncate_to_date(period_start)
    aggregated: dict[str, int] = {}

    for row in rows:
        if row.bucket is None:
            continue
        bucket_key = _build_bucket_key(range_key, period_start_date, row.bucket)
        aggregated[bucket_key] = aggregated.get(bucket_key, 0) + int(row.value or 0)

    label_specs = generate_chart_label_specs(range_key, period_start, period_end)
    return [
        ChartDataPoint(
            label=label,
            value=aggregated.get(bucket_key, 0),
        )
        for bucket_key, label in label_specs
    ]


# ---------------------------------------------------------------------------
# Resolution chart helpers
# ---------------------------------------------------------------------------

RESPONSE_TIME_HOUR_BUCKETS: list[tuple[int, str]] = [
    (0, "00:00"),
    (4, "04:00"),
    (8, "08:00"),
    (12, "12:00"),
    (16, "16:00"),
    (20, "20:00"),
]


def _get_resolution_bucket_expression(range_key: str):
    """Return the SQL expression used to bucket resolution chart timestamps."""
    if range_key in {"7d", "30d"}:
        return func.date_trunc("day", ChatSession.last_activity)
    if range_key == "3m":
        return func.date_trunc("week", ChatSession.last_activity)
    return func.date_trunc("month", ChatSession.last_activity)


def _apply_eligible_chatbot_resolution_filters(
    query,
    user: User,
    period_start: datetime,
    period_end: datetime,
):
    """Restrict resolution chart queries to eligible chatbots and the requested period."""
    query = (
        query.select_from(ChatSession)
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
        .where(Chatbot.status != CHATBOT_STATUS_DRAFT)
        .where(Chatbot.is_deleted.is_(False))
        .where(
            ChatSession.is_resolved.in_(
                (SESSION_RESOLVED_RESOLVED, SESSION_RESOLVED_UNRESOLVED)
            )
        )
        .where(ChatSession.last_activity >= period_start)
        .where(ChatSession.last_activity <= period_end)
    )
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query


def fetch_resolution_chart_rows(
    db: Session,
    user: User,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list:
    """Aggregate resolved and unresolved session counts for the chart period."""
    bucket_expression = _get_resolution_bucket_expression(range_key).label("bucket")
    query = (
        select(
            bucket_expression,
            func.sum(
                case(
                    (ChatSession.is_resolved == SESSION_RESOLVED_RESOLVED, 1),
                    else_=0,
                )
            ).label("resolved"),
            func.sum(
                case(
                    (ChatSession.is_resolved == SESSION_RESOLVED_UNRESOLVED, 1),
                    else_=0,
                )
            ).label("unresolved"),
        )
        .group_by(bucket_expression)
        .order_by(bucket_expression)
    )

    query = _apply_eligible_chatbot_resolution_filters(
        query,
        user,
        period_start,
        period_end,
    )
    return db.execute(query).all()


def build_resolution_chart_data_points(
    rows: list,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list[ResolutionChartDataPoint]:
    """Map resolution SQL rows to ordered chart data points with zero-filled gaps."""
    period_start_date = _truncate_to_date(period_start)
    aggregated: dict[str, dict[str, int]] = {}

    for row in rows:
        if row.bucket is None:
            continue
        bucket_key = _build_bucket_key(range_key, period_start_date, row.bucket)
        bucket_totals = aggregated.setdefault(
            bucket_key,
            {"resolved": 0, "unresolved": 0},
        )
        bucket_totals["resolved"] += int(row.resolved or 0)
        bucket_totals["unresolved"] += int(row.unresolved or 0)

    if not aggregated:
        return []

    label_specs = generate_chart_label_specs(range_key, period_start, period_end)
    return [
        ResolutionChartDataPoint(
            label=label,
            resolved=aggregated.get(bucket_key, {}).get("resolved", 0),
            unresolved=aggregated.get(bucket_key, {}).get("unresolved", 0),
        )
        for bucket_key, label in label_specs
    ]


# ---------------------------------------------------------------------------
# Response time chart helpers
# ---------------------------------------------------------------------------


def _get_message_bucket_expression(range_key: str):
    """Return the SQL expression used to bucket chat message timestamps."""
    if range_key == "30d":
        return func.date_trunc("day", ChatMessage.created_at)
    if range_key == "3m":
        return func.date_trunc("week", ChatMessage.created_at)
    if range_key in {"6m", "1y"}:
        return func.date_trunc("month", ChatMessage.created_at)
    return None


def _get_response_time_hour_bucket_expression():
    """Return a 4-hour bucket expression for the 7-day response time chart."""
    hour = func.extract("hour", ChatMessage.created_at)
    return cast(func.floor(hour / 4) * 4, Integer)


def _apply_eligible_chatbot_message_filters(
    query,
    user: User,
    period_start: datetime,
    period_end: datetime,
):
    """Restrict response time chart queries to eligible chatbots and the requested period."""
    query = (
        query.select_from(ChatMessage)
        .join(Chatbot, Chatbot.id == ChatMessage.chatbot_id)
        .where(Chatbot.status != CHATBOT_STATUS_DRAFT)
        .where(Chatbot.is_deleted.is_(False))
        .where(ChatMessage.created_at >= period_start)
        .where(ChatMessage.created_at <= period_end)
        .where(ChatMessage.response_time.is_not(None))
    )
    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)
    return query


def fetch_response_time_chart_rows(
    db: Session,
    user: User,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list:
    """Aggregate average response times from chat messages for the chart period."""
    if range_key == "7d":
        bucket_expression = _get_response_time_hour_bucket_expression().label("bucket")
    else:
        bucket_expression = _get_message_bucket_expression(range_key).label("bucket")

    query = (
        select(
            bucket_expression,
            func.avg(ChatMessage.response_time).label("value"),
        )
        .group_by(bucket_expression)
        .order_by(bucket_expression)
    )

    query = _apply_eligible_chatbot_message_filters(
        query,
        user,
        period_start,
        period_end,
    )
    return db.execute(query).all()


def _normalize_response_time(value) -> Decimal:
    """Convert a SQL average response time value to a 2-decimal Decimal."""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def build_response_time_chart_data_points(
    rows: list,
    range_key: str,
    period_start: datetime,
    period_end: datetime,
) -> list[ResponseTimeChartDataPoint]:
    """Map response time SQL rows to ordered chart data points with zero-filled gaps."""
    if range_key == "7d":
        aggregated: dict[int, Decimal] = {}
        for row in rows:
            if row.bucket is None:
                continue
            bucket_key = int(row.bucket)
            aggregated[bucket_key] = _normalize_response_time(row.value)

        if not aggregated:
            return []

        return [
            ResponseTimeChartDataPoint(
                label=label,
                value=aggregated.get(bucket_hour, Decimal("0.00")),
            )
            for bucket_hour, label in RESPONSE_TIME_HOUR_BUCKETS
        ]

    period_start_date = _truncate_to_date(period_start)
    aggregated_dates: dict[str, Decimal] = {}

    for row in rows:
        if row.bucket is None:
            continue
        bucket_key = _build_bucket_key(range_key, period_start_date, row.bucket)
        aggregated_dates[bucket_key] = _normalize_response_time(row.value)

    if not aggregated_dates:
        return []

    label_specs = generate_chart_label_specs(range_key, period_start, period_end)
    return [
        ResponseTimeChartDataPoint(
            label=label,
            value=aggregated_dates.get(bucket_key, Decimal("0.00")),
        )
        for bucket_key, label in label_specs
    ]
