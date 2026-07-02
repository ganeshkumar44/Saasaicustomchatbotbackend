"""
Chatbot analysis helper utilities.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.chat_analysis.model import ChatAnalysis
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.user_details.utils import is_admin


def build_chatbot_analytics_query(user: User) -> Select:
    """
    Build a query joining chatbots with chat_analysis for dashboard reporting.

    Administrators see all non-draft chatbots; normal users see only their own.
    """
    query = (
        select(
            Chatbot.id.label("chatbot_id"),
            Chatbot.chatbot_name,
            Chatbot.status,
            Chatbot.ai_model,
            ChatAnalysis.total_conversations,
            ChatAnalysis.total_visitors,
            ChatAnalysis.resolved_conversations,
            ChatAnalysis.unresolved_conversations,
            ChatAnalysis.resolution_rate,
            ChatAnalysis.average_response_time,
            ChatAnalysis.total_messages,
            ChatAnalysis.total_user_messages,
            ChatAnalysis.total_bot_messages,
            ChatAnalysis.created_at,
            ChatAnalysis.updated_at,
        )
        .join(ChatAnalysis, ChatAnalysis.chatbot_id == Chatbot.id)
        .where(Chatbot.status != CHATBOT_STATUS_DRAFT)
        .order_by(Chatbot.updated_at.desc())
    )

    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)

    return query


def fetch_chatbot_analytics_rows(db: Session, user: User) -> list:
    """Execute the chatbot analytics query and return result rows."""
    query = build_chatbot_analytics_query(user)
    return db.execute(query).all()
