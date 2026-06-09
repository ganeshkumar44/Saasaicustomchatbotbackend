from pydantic import BaseModel


class CreateChatbotDraftData(BaseModel):
    chatbot_id: int
    status: str


class CreateChatbotDraftSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: CreateChatbotDraftData
