from datetime import datetime

from pydantic import BaseModel


class WidgetConfigResponse(BaseModel):
    """Public widget configuration exposed to the embedded chatbot widget."""

    chat_title: str
    welcome_message: str
    primary_color: str
    text_color: str
    show_avatar: bool
    typing_indicator: bool
    widget_position: str
    allowed_domains: str


class WidgetConfigSuccessResponse(BaseModel):
    success: bool = True
    data: WidgetConfigResponse


class PublicChatRequest(BaseModel):
    """Visitor chat message submitted from the embedded widget."""

    public_key: str
    session_id: str
    message: str


class PublicChatResponse(BaseModel):
    """AI-generated answer returned to the embedded widget."""

    success: bool = True
    answer: str


class StartSessionRequest(BaseModel):
    public_key: str


class StartSessionResponse(BaseModel):
    success: bool = True
    session_id: str


class ChatHistoryMessage(BaseModel):
    user_message: str
    bot_response: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    success: bool = True
    session_id: str
    messages: list[ChatHistoryMessage]
    visitor_step: str = "completed"
    question: str | None = None
    can_skip: bool = False
    onboarding_complete: bool = True


class VisitorInfoRequest(BaseModel):
    """Visitor onboarding input submitted from the embedded widget."""

    session_id: str
    step: str
    value: str | None = None
    skip: bool = False


class VisitorInfoResponse(BaseModel):
    """Onboarding progress returned to the embedded widget."""

    success: bool = True
    next_step: str
    question: str | None = None
    can_skip: bool = False
    onboarding_complete: bool = False
    message: str | None = None
