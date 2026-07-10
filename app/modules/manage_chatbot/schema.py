"""
Manage Chatbot module Pydantic schemas.
"""

from pydantic import BaseModel


class PermanentlyDeleteChatbotSuccessResponse(BaseModel):
    """Response returned after a chatbot is permanently deleted."""

    success: bool = True
    message: str
