from datetime import datetime

from pydantic import BaseModel


class ChatSessionResponse(BaseModel):
    """Chat session data for future API responses."""

    id: int
    chatbot_id: int
    session_id: str
    visitor_id: str | None
    started_at: datetime
    last_activity: datetime
