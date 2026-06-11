"""
Widget module business logic.
"""

from sqlalchemy.orm import Session

from app.modules.chatbot.model import CHATBOT_STATUS_PUBLISHED, Chatbot
from app.modules.widget.schema import (
    PublicChatRequest,
    PublicChatResponse,
    WidgetConfigSuccessResponse,
)
from app.modules.widget.utils import (
    build_widget_config_response,
    get_chatbot_settings_by_public_key,
)

TEMPORARY_CHAT_ANSWER = "Widget API is working successfully"


class WidgetConfigNotFoundError(Exception):
    """Raised when no chatbot settings exist for the given public key."""


class ChatbotNotFoundError(Exception):
    """Raised when no chatbot exists for the given public key."""


class ChatbotNotPublishedError(Exception):
    """Raised when the chatbot is not in published status."""


class MessageRequiredError(Exception):
    """Raised when the chat message is missing or empty."""


def get_widget_config(db: Session, public_key: str) -> WidgetConfigSuccessResponse:
    """Return public widget configuration for the given public key."""
    settings = get_chatbot_settings_by_public_key(db, public_key)
    if settings is None:
        raise WidgetConfigNotFoundError

    return WidgetConfigSuccessResponse(
        data=build_widget_config_response(settings),
    )


def process_public_chat(
    db: Session,
    payload: PublicChatRequest,
) -> PublicChatResponse:
    """Accept a visitor message and return a temporary hardcoded response."""
    if not payload.public_key or not payload.public_key.strip():
        raise ChatbotNotFoundError()

    if not payload.message or not payload.message.strip():
        raise MessageRequiredError()

    settings = get_chatbot_settings_by_public_key(db, payload.public_key.strip())
    if settings is None:
        raise ChatbotNotFoundError()

    chatbot = db.get(Chatbot, settings.chatbot_id)
    if chatbot is None or chatbot.status != CHATBOT_STATUS_PUBLISHED:
        raise ChatbotNotPublishedError()

    return PublicChatResponse(answer=TEMPORARY_CHAT_ANSWER)
