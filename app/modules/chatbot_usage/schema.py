"""Chatbot usage API schemas."""

from datetime import datetime

from pydantic import BaseModel


class PlanLimitsData(BaseModel):
    plan_name: str
    max_chatbots: int
    chatbot_message_limit: int | None = None
    playground_message_limit: int | None = None
    chatbot_message_unlimited: bool = False
    playground_message_unlimited: bool = False


class ChatbotUsageData(BaseModel):
    chatbot_id: int
    website_messages_used: int
    playground_messages_used: int
    website_tokens_used: int
    playground_tokens_used: int
    website_last_reset_at: datetime | None = None
    playground_last_reset_at: datetime | None = None
    limits: PlanLimitsData


class ChatbotUsageSuccessResponse(BaseModel):
    success: bool = True
    data: ChatbotUsageData
