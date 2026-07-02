"""
Dashboard module helper utilities.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_sessions.model import ChatSession
from app.modules.chatbot.model import Chatbot, ChatbotSettings
from app.modules.knowledgebase.model import KnowledgebaseDocument
from app.modules.user_details.utils import is_admin

CHATBOT_OWNER_SELF = "Self"


def format_chatbot_owner_name(
    owner_user_id: int,
    current_user: User,
    owner_first_name: str,
    owner_last_name: str,
) -> str | None:
    """Return owner display name for admins; hidden for normal users."""
    if not is_admin(current_user):
        return None

    if owner_user_id == current_user.id:
        return CHATBOT_OWNER_SELF

    return f"{owner_first_name} {owner_last_name}".strip()


def build_chatbot_list_query(user: User) -> Select:
    """
    Build an aggregated chatbot list query with conversation and document counts.

    Administrators see all chatbots; normal users see only their own.
    """
    session_counts = (
        select(
            ChatSession.chatbot_id.label("chatbot_id"),
            func.count(ChatSession.id).label("total_conversations"),
        )
        .group_by(ChatSession.chatbot_id)
        .subquery()
    )

    message_counts = (
        select(
            ChatSession.chatbot_id.label("chatbot_id"),
            func.count(ChatMessage.id).label("total_messages"),
        )
        .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .group_by(ChatSession.chatbot_id)
        .subquery()
    )

    document_counts = (
        select(
            KnowledgebaseDocument.chatbot_id.label("chatbot_id"),
            func.count(KnowledgebaseDocument.id).label("total_uploaded_documents"),
        )
        .group_by(KnowledgebaseDocument.chatbot_id)
        .subquery()
    )

    query = (
        select(
            Chatbot.id.label("chatbot_id"),
            Chatbot.user_id.label("owner_user_id"),
            Chatbot.chatbot_name,
            Chatbot.description,
            Chatbot.ai_model,
            Chatbot.language,
            Chatbot.status,
            ChatbotSettings.public_key,
            User.first_name.label("owner_first_name"),
            User.last_name.label("owner_last_name"),
            func.coalesce(session_counts.c.total_conversations, 0).label(
                "total_conversations"
            ),
            func.coalesce(message_counts.c.total_messages, 0).label("total_messages"),
            func.coalesce(document_counts.c.total_uploaded_documents, 0).label(
                "total_uploaded_documents"
            ),
            Chatbot.created_at,
            Chatbot.updated_at,
        )
        .join(User, User.id == Chatbot.user_id)
        .outerjoin(ChatbotSettings, ChatbotSettings.chatbot_id == Chatbot.id)
        .outerjoin(session_counts, session_counts.c.chatbot_id == Chatbot.id)
        .outerjoin(message_counts, message_counts.c.chatbot_id == Chatbot.id)
        .outerjoin(document_counts, document_counts.c.chatbot_id == Chatbot.id)
        .order_by(Chatbot.updated_at.desc())
    )

    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)

    return query


def fetch_chatbot_list_rows(db: Session, user: User) -> list:
    """Execute the dashboard chatbot list query and return result rows."""
    query = build_chatbot_list_query(user)
    return db.execute(query).all()
