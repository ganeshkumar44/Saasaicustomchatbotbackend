"""
Chat analysis helper utilities.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.modules.chat_analysis.model import ChatAnalysis
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
    ChatSession,
)
from app.modules.chatbot.model import Chatbot
from app.modules.widget.model import WidgetVisitor

logger = logging.getLogger(__name__)


def build_default_chat_analysis(chatbot_id: int) -> ChatAnalysis:
    """Build a default analytics record for a chatbot."""
    return ChatAnalysis(
        chatbot_id=chatbot_id,
        total_conversations=0,
        total_visitors=0,
        resolved_conversations=0,
        unresolved_conversations=0,
        resolution_rate=Decimal("0.00"),
        average_response_time=Decimal("0.00"),
        total_messages=0,
        total_user_messages=0,
        total_bot_messages=0,
    )


def build_chat_analysis_response(analysis: ChatAnalysis):
    """Map a chat analysis ORM record to a Pydantic response."""
    from app.modules.chat_analysis.schema import ChatAnalysisResponse

    return ChatAnalysisResponse(
        id=analysis.id,
        chatbot_id=analysis.chatbot_id,
        total_conversations=analysis.total_conversations,
        total_visitors=analysis.total_visitors,
        resolved_conversations=analysis.resolved_conversations,
        unresolved_conversations=analysis.unresolved_conversations,
        resolution_rate=analysis.resolution_rate,
        average_response_time=analysis.average_response_time,
        total_messages=analysis.total_messages,
        total_user_messages=analysis.total_user_messages,
        total_bot_messages=analysis.total_bot_messages,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


def _recalculate_resolution_rate(
    resolved_conversations: int,
    unresolved_conversations: int,
) -> Decimal:
    """Calculate resolution rate from resolved and unresolved conversation counts."""
    total_feedback = resolved_conversations + unresolved_conversations
    if total_feedback <= 0:
        return Decimal("0.00")

    rate = (
        Decimal(resolved_conversations)
        / Decimal(total_feedback)
        * Decimal("100")
    )
    return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def reconcile_chat_analysis_counts(db_engine: Engine) -> int:
    """
    Reconcile cached chat_analysis counters from source tables.

    Fixes inflated conversation and visitor totals caused by prior analytics logic.
    Returns the number of records updated.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    updated_count = 0

    try:
        analyses = db.scalars(select(ChatAnalysis)).all()
        for analysis in analyses:
            chatbot_id = analysis.chatbot_id
            conversations = (
                db.scalar(
                    select(func.count())
                    .select_from(ChatSession)
                    .where(ChatSession.chatbot_id == chatbot_id)
                )
                or 0
            )
            visitors = (
                db.scalar(
                    select(func.count())
                    .select_from(WidgetVisitor)
                    .where(WidgetVisitor.chatbot_id == chatbot_id)
                )
                or 0
            )
            resolved = (
                db.scalar(
                    select(func.count())
                    .select_from(ChatSession)
                    .where(
                        ChatSession.chatbot_id == chatbot_id,
                        ChatSession.is_resolved == SESSION_RESOLVED_RESOLVED,
                    )
                )
                or 0
            )
            unresolved = (
                db.scalar(
                    select(func.count())
                    .select_from(ChatSession)
                    .where(
                        ChatSession.chatbot_id == chatbot_id,
                        ChatSession.is_resolved == SESSION_RESOLVED_UNRESOLVED,
                    )
                )
                or 0
            )

            resolution_rate = _recalculate_resolution_rate(resolved, unresolved)
            if (
                analysis.total_conversations != conversations
                or analysis.total_visitors != visitors
                or analysis.resolved_conversations != resolved
                or analysis.unresolved_conversations != unresolved
                or analysis.resolution_rate != resolution_rate
            ):
                analysis.total_conversations = conversations
                analysis.total_visitors = visitors
                analysis.resolved_conversations = resolved
                analysis.unresolved_conversations = unresolved
                analysis.resolution_rate = resolution_rate
                updated_count += 1

        if updated_count:
            db.commit()
            logger.info("Reconciled %s chat_analysis records from source tables", updated_count)
        else:
            logger.info("Chat analysis reconciliation complete; no updates required")
    except Exception:
        db.rollback()
        logger.exception("Failed to reconcile chat_analysis records")
        raise
    finally:
        db.close()

    return updated_count


def sync_existing_chat_analysis(db_engine: Engine) -> int:
    """
    Create missing chat_analysis records for existing chatbots.

    Safe to run multiple times; skips chatbots that already have analytics.
    Returns the number of records created.
    """
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = session_factory()
    created_count = 0

    try:
        missing_chatbot_ids = db.execute(
            select(Chatbot.id)
            .outerjoin(ChatAnalysis, Chatbot.id == ChatAnalysis.chatbot_id)
            .where(ChatAnalysis.id.is_(None))
        ).scalars().all()

        for chatbot_id in missing_chatbot_ids:
            db.add(build_default_chat_analysis(chatbot_id))
            created_count += 1

        if created_count:
            db.commit()
            logger.info("Synchronized %s missing chat_analysis records", created_count)
        else:
            logger.info("Chat analysis synchronization complete; no missing records")
    except Exception:
        db.rollback()
        logger.exception("Failed to synchronize existing chat_analysis records")
        raise
    finally:
        db.close()

    reconcile_chat_analysis_counts(db_engine)
    return created_count


def get_chat_analysis_by_chatbot_id(
    db: Session,
    chatbot_id: int,
) -> ChatAnalysis | None:
    """Return the analytics record for a chatbot, if one exists."""
    return db.execute(
        select(ChatAnalysis).where(ChatAnalysis.chatbot_id == chatbot_id)
    ).scalar_one_or_none()
