"""
Chat analysis business logic.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.chat_analysis.model import ChatAnalysis
from app.modules.chat_analysis.utils import (
    build_default_chat_analysis,
    get_chat_analysis_by_chatbot_id,
)
from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
)

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")


def _touch_analysis(analysis: ChatAnalysis) -> None:
    """Update the analytics record timestamp."""
    analysis.updated_at = datetime.now(timezone.utc)


def _get_or_create_analysis(db: Session, chatbot_id: int) -> ChatAnalysis:
    """Return the analytics record for a chatbot, creating defaults when missing."""
    analysis = get_chat_analysis_by_chatbot_id(db, chatbot_id)
    if analysis is not None:
        return analysis

    analysis = build_default_chat_analysis(chatbot_id)
    db.add(analysis)
    db.flush()
    logger.info("Created missing chat_analysis record for chatbot_id=%s", chatbot_id)
    return analysis


def _recalculate_average_response_time(db: Session, analysis: ChatAnalysis) -> None:
    """Recalculate average response time from non-null chat message values."""
    average = db.execute(
        select(func.avg(ChatMessage.response_time)).where(
            ChatMessage.chatbot_id == analysis.chatbot_id,
            ChatMessage.response_time.is_not(None),
        )
    ).scalar_one_or_none()

    if average is None:
        analysis.average_response_time = Decimal("0.00")
        return

    analysis.average_response_time = Decimal(str(average)).quantize(
        _TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _recalculate_resolution_rate(analysis: ChatAnalysis) -> None:
    """Recalculate resolution rate from resolved and unresolved conversation counts."""
    total_feedback = (
        analysis.resolved_conversations + analysis.unresolved_conversations
    )
    if total_feedback <= 0:
        analysis.resolution_rate = Decimal("0.00")
        return

    rate = (
        Decimal(analysis.resolved_conversations)
        / Decimal(total_feedback)
        * Decimal("100")
    )
    analysis.resolution_rate = rate.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def ensure_chat_analysis_for_chatbot(db: Session, chatbot_id: int) -> ChatAnalysis:
    """
    Ensure a chatbot has an analytics record.

    Creates a default record when missing. Safe to call multiple times.
    Does not commit the session.
    """
    return _get_or_create_analysis(db, chatbot_id)


def record_new_chat_session(db: Session, chatbot_id: int, *, commit: bool = True) -> None:
    """Increment conversation counter for a newly created chat session."""
    analysis = _get_or_create_analysis(db, chatbot_id)
    analysis.total_conversations = max(0, analysis.total_conversations + 1)
    _touch_analysis(analysis)

    if commit:
        db.commit()

    logger.info(
        "Recorded new chat session analytics chatbot_id=%s total_conversations=%s",
        chatbot_id,
        analysis.total_conversations,
    )


def record_new_visitor(db: Session, chatbot_id: int, *, commit: bool = True) -> None:
    """Increment visitor counter when a new widget visitor profile is created."""
    analysis = _get_or_create_analysis(db, chatbot_id)
    analysis.total_visitors = max(0, analysis.total_visitors + 1)
    _touch_analysis(analysis)

    if commit:
        db.commit()

    logger.info(
        "Recorded new visitor analytics chatbot_id=%s total_visitors=%s",
        chatbot_id,
        analysis.total_visitors,
    )


def record_chat_exchange(db: Session, chatbot_id: int, *, commit: bool = True) -> None:
    """
    Increment message counters and recalculate average response time.

    Called after a user message and bot response are successfully saved together.
    """
    analysis = _get_or_create_analysis(db, chatbot_id)
    analysis.total_messages = max(0, analysis.total_messages + 2)
    analysis.total_user_messages = max(0, analysis.total_user_messages + 1)
    analysis.total_bot_messages = max(0, analysis.total_bot_messages + 1)
    _recalculate_average_response_time(db, analysis)
    _touch_analysis(analysis)

    if commit:
        db.commit()

    logger.info(
        "Recorded chat exchange analytics chatbot_id=%s total_messages=%s "
        "average_response_time=%s",
        chatbot_id,
        analysis.total_messages,
        analysis.average_response_time,
    )


def record_chat_resolution(
    db: Session,
    chatbot_id: int,
    is_resolved: str,
    *,
    commit: bool = False,
) -> None:
    """Increment resolved or unresolved counters and recalculate resolution rate."""
    if is_resolved not in (SESSION_RESOLVED_RESOLVED, SESSION_RESOLVED_UNRESOLVED):
        return

    analysis = _get_or_create_analysis(db, chatbot_id)

    if is_resolved == SESSION_RESOLVED_RESOLVED:
        analysis.resolved_conversations = max(
            0,
            analysis.resolved_conversations + 1,
        )
    else:
        analysis.unresolved_conversations = max(
            0,
            analysis.unresolved_conversations + 1,
        )

    _recalculate_resolution_rate(analysis)
    _touch_analysis(analysis)

    if commit:
        db.commit()

    logger.info(
        "Recorded chat resolution analytics chatbot_id=%s is_resolved=%s "
        "resolved_conversations=%s unresolved_conversations=%s resolution_rate=%s",
        chatbot_id,
        is_resolved,
        analysis.resolved_conversations,
        analysis.unresolved_conversations,
        analysis.resolution_rate,
    )
