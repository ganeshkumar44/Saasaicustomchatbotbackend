from datetime import datetime

from pydantic import BaseModel


class CreateChatMessageRequest(BaseModel):
    """Request payload for creating a chat message."""

    session_id: int
    user_message: str
    bot_response: str


class ChatMessageResponse(BaseModel):
    """Chat message data for future API responses."""

    id: int
    session_id: int
    user_message: str
    bot_response: str
    created_at: datetime
