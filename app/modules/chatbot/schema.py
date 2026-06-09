from pydantic import BaseModel, Field


class CreateChatbotDraftData(BaseModel):
    chatbot_id: int
    status: str


class CreateChatbotDraftSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: CreateChatbotDraftData


class UpdateBasicInfoRequest(BaseModel):
    chatbot_name: str | None = Field(
        default=None,
        description="Display name for the chatbot",
    )
    description: str | None = Field(
        default=None,
        description="Optional chatbot description",
    )


class UpdateBasicInfoData(BaseModel):
    chatbot_id: int
    chatbot_name: str
    description: str | None
    status: str


class UpdateBasicInfoSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: UpdateBasicInfoData
