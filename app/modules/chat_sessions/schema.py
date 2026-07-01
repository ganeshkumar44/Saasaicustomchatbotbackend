from datetime import datetime

from pydantic import BaseModel


class ChatSessionResponse(BaseModel):
    """Chat session data for future API responses."""

    id: int
    chatbot_id: int
    session_id: str
    visitor_id: str | None
    visitor_name: str | None = None
    visitor_step: str
    is_active: str
    is_resolved: str
    started_at: datetime
    last_activity: datetime


class UpdateChatSessionStatusRequest(BaseModel):
    """Request payload for updating chat session lifecycle status."""

    public_key: str
    session_id: str
    is_active: str | None = None
    is_resolved: str | None = None


class UpdateChatSessionStatusResponse(BaseModel):
    """Response after updating chat session lifecycle status."""

    success: bool = True
    message: str
    session_id: str
    is_active: str
    is_resolved: str
