"""
Chat History module Pydantic schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ChatSessionListItem(BaseModel):
    """Summary row for a chat session on the chat history listing page."""

    chat_session_id: int
    chatbot_id: int
    chatbot_name: str | None
    visitor_name: str | None
    visitor_email: str | None
    first_message: str | None
    total_messages: int
    session_started_at: datetime
    last_activity: datetime
    status: str


class ChatSessionListSuccessResponse(BaseModel):
    """Paginated response for the chat session listing endpoint."""

    success: bool = True
    message: str
    page: int
    per_page: int
    total_records: int
    total_pages: int
    data: list[ChatSessionListItem]


class ChatHistoryMessageItem(BaseModel):
    """Single message exchange within a chat session."""

    user_message: str
    bot_response: str
    response_time: Decimal | None
    created_at: datetime


class ChatHistoryDetailData(BaseModel):
    """Detailed chat history for a single chat session."""

    chat_session_id: int
    chatbot_id: int
    chatbot_name: str | None
    visitor_name: str | None
    visitor_email: str | None
    session_started_at: datetime
    status: str
    messages: list[ChatHistoryMessageItem]


class ChatHistoryDetailSuccessResponse(BaseModel):
    """Response for the chat session detail endpoint."""

    success: bool = True
    message: str
    data: ChatHistoryDetailData
