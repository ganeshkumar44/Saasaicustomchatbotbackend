"""
Chatbot Settings module helper utilities.
"""

import logging

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import Chatbot, ChatbotSettings
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError
from app.modules.chatbot_settings.schema import ChatbotDetailsData

logger = logging.getLogger(__name__)


def get_owned_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot owned by the authenticated user or raise a domain error."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        logger.warning("Chatbot not found for chatbot_id=%s user_id=%s", chatbot_id, user.id)
        raise ChatbotNotFoundError()

    if chatbot.user_id != user.id:
        logger.warning(
            "Unauthorized chatbot access attempt chatbot_id=%s owner_id=%s user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )
        raise ChatbotPermissionError()

    return chatbot


def get_chatbot_settings_record(chatbot: Chatbot) -> ChatbotSettings | None:
    """Return the chatbot_settings row for a chatbot, if one exists."""
    return chatbot.settings


def build_chatbot_details_data(
    chatbot: Chatbot,
    settings: ChatbotSettings,
) -> ChatbotDetailsData:
    """Merge chatbot and settings records into a single response payload."""
    return ChatbotDetailsData(
        id=chatbot.id,
        user_id=chatbot.user_id,
        chatbot_name=chatbot.chatbot_name,
        description=chatbot.description,
        personality=chatbot.personality,
        ai_model=chatbot.ai_model,
        language=chatbot.language,
        status=chatbot.status,
        published_at=chatbot.published_at,
        created_at=chatbot.created_at,
        updated_at=chatbot.updated_at,
        settings_id=settings.id,
        public_key=settings.public_key,
        embed_code=settings.embed_code,
        allowed_domains=settings.allowed_domains,
        typing_indicator=settings.typing_indicator,
        primary_color=settings.primary_color,
        text_color=settings.text_color,
        widget_position=settings.widget_position,
        show_avatar=settings.show_avatar,
        chat_title=settings.chat_title,
        welcome_message=settings.welcome_message,
        input_placeholder=settings.input_placeholder,
        settings_created_at=settings.created_at,
        settings_updated_at=settings.updated_at,
    )
