"""
Chatbot Settings module business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chatbot_settings.schema import ChatbotDetailsSuccessResponse
from app.modules.chatbot_settings.utils import (
    build_chatbot_details_data,
    get_chatbot_settings_record,
    get_owned_chatbot,
)

logger = logging.getLogger(__name__)


class ChatbotSettingsNotFoundError(Exception):
    """Raised when no chatbot_settings record exists for the chatbot."""


def get_chatbot_details(
    db: Session,
    user: User,
    chatbot_id: int,
) -> ChatbotDetailsSuccessResponse:
    """Fetch and return complete chatbot configuration for the settings page."""
    logger.info(
        "Fetching chatbot details for chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    chatbot = get_owned_chatbot(db, user, chatbot_id)

    settings = get_chatbot_settings_record(chatbot)
    if settings is None:
        logger.warning(
            "Chatbot settings not found for chatbot_id=%s user_id=%s",
            chatbot_id,
            user.id,
        )
        raise ChatbotSettingsNotFoundError()

    logger.info(
        "Chatbot details fetched successfully for chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    return ChatbotDetailsSuccessResponse(
        message=messages.CHATBOT_DETAILS_FETCH_SUCCESS,
        data=build_chatbot_details_data(chatbot, settings),
    )
