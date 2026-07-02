from datetime import datetime

from pydantic import BaseModel


class ChatbotListItem(BaseModel):
    """Summary row for a chatbot on the dashboard."""

    chatbot_id: int
    chatbot_name: str | None
    description: str | None
    ai_model: str | None
    language: str | None
    status: str
    public_key: str | None
    total_conversations: int
    total_messages: int
    total_uploaded_documents: int
    created_at: datetime
    updated_at: datetime
    owner_name: str | None = None


class ChatbotListSuccessResponse(BaseModel):
    success: bool = True
    message: str
    total_chatbots: int
    data: list[ChatbotListItem]


class RecentConversationItem(BaseModel):
    """Latest conversation row for the dashboard recent conversations section."""

    chat_session_id: int
    chatbot_id: int
    chatbot_name: str | None
    visitor_name: str | None
    user_question: str
    message_time: datetime
    status: str


class RecentConversationsSuccessResponse(BaseModel):
    """Response for the dashboard recent conversations endpoint."""

    success: bool = True
    message: str
    data: list[RecentConversationItem]
