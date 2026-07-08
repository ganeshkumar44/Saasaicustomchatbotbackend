"""
Notification module Pydantic schemas.
"""

from pydantic import BaseModel, Field


class NotificationSettingsData(BaseModel):
    """Notification preference payload."""

    new_chatbot_email: bool
    chatbot_changes_email: bool
    new_chat_start_push: bool
    critical_alert_sms: bool


class NotificationSettingsSuccessResponse(BaseModel):
    """Response for notification settings fetch endpoint."""

    success: bool = True
    message: str
    data: NotificationSettingsData


class UpdateNotificationSettingsRequest(BaseModel):
    """Request body for updating the authenticated user's notification settings."""

    new_chatbot_email: bool = Field(
        ...,
        description="Receive email when a new chatbot is created",
    )
    chatbot_changes_email: bool = Field(
        ...,
        description="Receive email when a chatbot is updated",
    )
    new_chat_start_push: bool = Field(
        ...,
        description="Receive push notification when a visitor starts a new chat",
    )
    critical_alert_sms: bool = Field(
        ...,
        description="Receive SMS for critical alerts such as chatbot deletion",
    )


class UpdateNotificationSettingsSuccessResponse(BaseModel):
    """Response for the notification settings update endpoint."""

    success: bool = True
    message: str
    data: NotificationSettingsData
