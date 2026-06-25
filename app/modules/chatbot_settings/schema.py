from datetime import datetime

from pydantic import BaseModel


class ChatbotDetailsData(BaseModel):
    """Complete chatbot configuration merged from chatbots and chatbot_settings."""

    # chatbots table
    id: int
    user_id: int
    chatbot_name: str | None
    description: str | None
    personality: str | None
    ai_model: str | None
    language: str | None
    status: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # chatbot_settings table
    settings_id: int
    public_key: str
    embed_code: str
    allowed_domains: str
    typing_indicator: bool
    primary_color: str
    text_color: str
    widget_position: str
    show_avatar: bool
    chat_title: str
    welcome_message: str
    input_placeholder: str
    settings_created_at: datetime
    settings_updated_at: datetime


class ChatbotDetailsSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: ChatbotDetailsData
