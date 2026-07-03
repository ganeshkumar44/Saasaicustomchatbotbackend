from enum import Enum

from pydantic import BaseModel, Field


class PersonalityEnum(str, Enum):
    PROFESSIONAL = "Professional"
    FRIENDLY = "Friendly"
    CASUAL = "Casual"


class AIModelEnum(str, Enum):
    GEMINI_2_5_FLASH = "Gemini 2.5 Flash"


class LanguageEnum(str, Enum):
    ENGLISH = "English"


class CreateChatbotDraftData(BaseModel):
    chatbot_id: int
    status: str


class CreateChatbotDraftSuccessResponse(BaseModel):
    success: bool = True
    message: str
    is_existing_draft: bool
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


class UpdateBehaviourRequest(BaseModel):
    personality: str = Field(..., description="Chatbot personality style")
    ai_model: str = Field(..., description="AI model used by the chatbot")
    language: str = Field(..., description="Chatbot response language")


class UpdateBehaviourData(BaseModel):
    chatbot_id: int
    personality: str
    ai_model: str
    language: str


class UpdateBehaviourSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: UpdateBehaviourData


class KnowledgebaseSummary(BaseModel):
    total_files_uploaded: int
    total_urls_uploaded: int
    total_knowledge_sources: int


class ChatbotReviewData(BaseModel):
    chatbot_id: int
    chatbot_name: str | None
    description: str | None
    personality: str | None
    ai_model: str | None
    language: str | None
    status: str
    knowledgebase: KnowledgebaseSummary


class ChatbotReviewSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: ChatbotReviewData


class PublishChatbotData(BaseModel):
    chatbot_id: int
    status: str
    public_key: str
    embed_code: str


class PublishChatbotSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: PublishChatbotData
