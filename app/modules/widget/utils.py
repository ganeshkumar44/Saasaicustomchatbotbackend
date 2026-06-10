"""
Widget module helper utilities.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.chatbot.model import ChatbotSettings
from app.modules.widget.schema import WidgetConfigResponse


def get_chatbot_settings_by_public_key(
    db: Session,
    public_key: str,
) -> ChatbotSettings | None:
    """Return chatbot settings for a published widget public key."""
    return db.execute(
        select(ChatbotSettings).where(ChatbotSettings.public_key == public_key)
    ).scalar_one_or_none()


def build_widget_config_response(settings: ChatbotSettings) -> WidgetConfigResponse:
    """Map chatbot settings to the public widget configuration response."""
    return WidgetConfigResponse(
        chat_title=settings.chat_title,
        welcome_message=settings.welcome_message,
        primary_color=settings.primary_color,
        text_color=settings.text_color,
        show_avatar=settings.show_avatar,
        typing_indicator=settings.typing_indicator,
        widget_position=settings.widget_position,
    )
