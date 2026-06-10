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


class WidgetConfigSuccessResponse(BaseModel):
    success: bool = True
    data: WidgetConfigResponse
