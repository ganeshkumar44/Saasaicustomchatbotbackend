"""
Playground module Pydantic schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreatePlaygroundSessionRequest(BaseModel):
    """Request body for creating a Playground session."""

    chatbot_id: int = Field(..., description="Chatbot that owns this Playground session")
    title: str | None = Field(
        default=None,
        description="Optional session title. Defaults to 'New Chat'.",
    )


class PlaygroundSessionItem(BaseModel):
    """Playground session list/detail item."""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class PlaygroundSessionListResponse(BaseModel):
    """Response for listing Playground sessions."""

    success: bool = True
    data: list[PlaygroundSessionItem]


class CreatePlaygroundSessionResponse(BaseModel):
    """Response for creating a Playground session."""

    success: bool = True
    message: str
    data: PlaygroundSessionItem


class DeletePlaygroundSessionResponse(BaseModel):
    """Response for deleting a Playground session."""

    success: bool = True
    message: str


class PlaygroundMessageItem(BaseModel):
    """Single Playground message in a conversation."""

    id: int
    sender: str
    message: str
    response_time: Decimal | None = None
    tokens_used: int | None = None
    created_at: datetime


class PlaygroundMessagesResponse(BaseModel):
    """Response for loading a Playground conversation."""

    success: bool = True
    data: list[PlaygroundMessageItem]
