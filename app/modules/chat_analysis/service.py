"""
Chat analysis business logic.

Analytics calculations will be implemented in a future phase.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.chat_analysis.model import ChatAnalysis
from app.modules.chat_analysis.utils import (
    build_default_chat_analysis,
    get_chat_analysis_by_chatbot_id,
)

logger = logging.getLogger(__name__)


def ensure_chat_analysis_for_chatbot(db: Session, chatbot_id: int) -> ChatAnalysis:
    """
    Ensure a chatbot has an analytics record.

    Creates a default record when missing. Safe to call multiple times.
    Does not commit the session.
    """
    existing = get_chat_analysis_by_chatbot_id(db, chatbot_id)
    if existing is not None:
        return existing

    analysis = build_default_chat_analysis(chatbot_id)
    db.add(analysis)
    logger.info("Prepared default chat_analysis record for chatbot_id=%s", chatbot_id)
    return analysis
