"""
Chatbot analysis Pydantic schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ChatbotAnalyticsItem(BaseModel):
    """Analytics summary for a single non-draft chatbot."""

    chatbot_id: int
    chatbot_name: str | None
    status: str
    ai_model: str | None
    total_conversations: int
    total_visitors: int
    resolved_conversations: int
    unresolved_conversations: int
    resolution_rate: Decimal
    average_response_time: Decimal
    total_messages: int
    total_user_messages: int
    total_bot_messages: int
    created_at: datetime
    updated_at: datetime


class ChatbotAnalyticsSuccessResponse(BaseModel):
    """Response for the chatbot analytics details endpoint."""

    success: bool = True
    message: str
    total_chatbots: int
    data: list[ChatbotAnalyticsItem]


class MergedChatbotAnalyticsData(BaseModel):
    """Merged analytics summary across eligible chatbots."""

    total_chatbots: int
    total_conversations: int
    total_visitors: int
    resolved_conversations: int
    unresolved_conversations: int
    resolution_rate: Decimal
    average_response_time: Decimal
    total_messages: int
    total_user_messages: int
    total_bot_messages: int


class MergedChatbotAnalyticsSuccessResponse(BaseModel):
    """Response for the merged chatbot analytics overview endpoint."""

    success: bool = True
    message: str
    data: MergedChatbotAnalyticsData
