"""
Chat analysis Pydantic schemas.

Reserved for future analytics API responses.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ChatAnalysisResponse(BaseModel):
    """Chatbot analytics record for future dashboard reporting."""

    id: int
    chatbot_id: int
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
