from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CreateChatMessageRequest(BaseModel):
    """Request payload for creating a chat message."""

    session_id: int
    user_message: str
    bot_response: str
    response_time: Decimal | None = None


class ChatMessageResponse(BaseModel):
    """Chat message data for future API responses."""

    id: int
    session_id: int
    user_message: str
    bot_response: str
    created_at: datetime
