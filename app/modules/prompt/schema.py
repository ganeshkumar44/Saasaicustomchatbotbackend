"""Request/response schemas for chatbot prompt configuration APIs."""

from pydantic import BaseModel, Field


class ChatbotPromptData(BaseModel):
    system_prompt: str = ""
    tone: str = ""
    response_style: str = ""
    response_length: str = ""
    language: str = ""
    extra_instruction: str = ""


class ChatbotPromptSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: ChatbotPromptData


class UpdateChatbotPromptRequest(BaseModel):
    system_prompt: str = ""
    tone: str = ""
    response_style: str = ""
    response_length: str = ""
    language: str = ""
    extra_instruction: str = Field(default="", max_length=5000)
