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
    input_placeholder: str = "Type your message..."


class WidgetConfigSuccessResponse(BaseModel):
    success: bool = True
    chatbot_available: bool = True
    message: str | None = None
    data: WidgetConfigResponse | None = None


class PublicChatRequest(BaseModel):
    """Visitor chat message submitted from the embedded widget."""

    public_key: str
    session_id: str
    message: str


class PublicChatResponse(BaseModel):
    """AI-generated answer returned to the embedded widget."""

    success: bool = True
    chatbot_available: bool = True
    answer: str | None = None
    message: str | None = None


class StartSessionRequest(BaseModel):
    public_key: str
    visitor_key: str | None = None


class StartSessionResponse(BaseModel):
    success: bool = True
    chatbot_available: bool = True
    session_id: str | None = None
    message: str | None = None


class ChatHistoryMessage(BaseModel):
    user_message: str
    bot_response: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    success: bool = True
    chatbot_available: bool = True
    session_id: str | None = None
    messages: list[ChatHistoryMessage] = []
    visitor_step: str = "completed"
    question: str | None = None
    can_skip: bool = False
    onboarding_complete: bool = True
    is_active: str = "active"
    is_resolved: str = "pending"
    message: str | None = None


class UpdateChatSessionStatusRequest(BaseModel):
    """Request payload for closing a widget chat session with feedback."""

    public_key: str
    session_id: str
    is_active: str | None = None
    is_resolved: str | None = None


class UpdateChatSessionStatusResponse(BaseModel):
    """Response after updating widget chat session lifecycle status."""

    success: bool = True
    message: str
    session_id: str
    is_active: str
    is_resolved: str


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
    visitor_key: str | None = None
