"""
Dashboard module helper utilities.
"""

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.auth.model import User
from app.modules.chat_messages.model import ChatMessage
from app.modules.chat_sessions.model import (
    SESSION_RESOLVED_RESOLVED,
    SESSION_RESOLVED_UNRESOLVED,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_CLOSED,
    ChatSession,
)
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot, ChatbotSettings
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
        .where(Chatbot.is_deleted.is_(False))
        .order_by(Chatbot.updated_at.desc())
    )

    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)

    return query


def fetch_chatbot_list_rows(db: Session, user: User) -> list:
    """Execute the dashboard chatbot list query and return result rows."""
    query = build_chatbot_list_query(user)
    return db.execute(query).all()


def compute_conversation_status(is_active: str, is_resolved: str) -> str:
    """Map session lifecycle fields to a single dashboard status label."""
    if is_active == SESSION_STATUS_ACTIVE:
        return SESSION_STATUS_ACTIVE
    if is_resolved == SESSION_RESOLVED_RESOLVED:
        return SESSION_RESOLVED_RESOLVED
    if is_resolved == SESSION_RESOLVED_UNRESOLVED:
        return SESSION_RESOLVED_UNRESOLVED
    return SESSION_STATUS_CLOSED


def build_recent_conversations_query(user: User) -> Select:
    """Build a query for the latest conversation message per eligible chat session."""
    latest_message_subquery = (
        select(
            ChatMessage.chat_session_id.label("chat_session_id"),
            func.max(ChatMessage.created_at).label("message_time"),
        )
        .group_by(ChatMessage.chat_session_id)
        .subquery()
    )

    visitor_display_name = func.coalesce(ChatSession.visitor_name, ChatSession.visitor_id)

    query = (
        select(
            ChatSession.id.label("chat_session_id"),
            Chatbot.id.label("chatbot_id"),
            Chatbot.chatbot_name,
            visitor_display_name.label("visitor_name"),
            ChatMessage.user_message.label("user_question"),
            ChatMessage.created_at.label("message_time"),
            ChatSession.is_active.label("session_status"),
            ChatSession.is_resolved.label("resolution_status"),
        )
        .join(
            latest_message_subquery,
            ChatSession.id == latest_message_subquery.c.chat_session_id,
        )
        .join(
            ChatMessage,
            and_(
                ChatMessage.chat_session_id == latest_message_subquery.c.chat_session_id,
                ChatMessage.created_at == latest_message_subquery.c.message_time,
            ),
        )
        .join(Chatbot, Chatbot.id == ChatSession.chatbot_id)
        .where(
            Chatbot.status != CHATBOT_STATUS_DRAFT,
            Chatbot.is_deleted.is_(False),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(5)
    )

    if not is_admin(user):
        query = query.where(Chatbot.user_id == user.id)

    return query


def fetch_recent_conversation_rows(db: Session, user: User) -> list:
    """Execute the recent conversations query and return result rows."""
    query = build_recent_conversations_query(user)
    return db.execute(query).all()
