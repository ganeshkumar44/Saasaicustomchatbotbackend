from datetime import datetime
from typing import Annotated

from fastapi import UploadFile
from pydantic import BaseModel, WithJsonSchema

# Swagger UI renders multipart file fields as "Choose File" when format is binary.
SwaggerUploadFile = Annotated[
    UploadFile,
    WithJsonSchema({"type": "string", "format": "binary"}),
]


class KnowledgebaseDocumentItem(BaseModel):
    """Knowledge base source uploaded or linked to a chatbot."""

    id: int
    chatbot_id: int
    source_type: str
    original_file_name: str | None = None
    stored_file_name: str | None = None
    file_extension: str | None = None
    file_size: int | None = None
    url: str | None = None
    processing_status: str
    extracted_text_preview: str | None = None
    extracted_text_length: int | None = None
    created_at: datetime
    updated_at: datetime


class ChatbotDetailsData(BaseModel):
    """Complete chatbot configuration merged from chatbots and chatbot_settings."""

    # chatbots table
    id: int
    user_id: int
    chatbot_name: str | None
    description: str | None
    personality: str | None
    ai_model: str | None
    language: str | None
    status: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # chatbot_settings table
    settings_id: int
    public_key: str
    embed_code: str
    allowed_domains: str
    typing_indicator: bool
    primary_color: str
    text_color: str
    widget_position: str
    show_avatar: bool
    chat_title: str
    welcome_message: str
    input_placeholder: str
    settings_created_at: datetime
    settings_updated_at: datetime

    # knowledgebase_documents table
    knowledgebase_documents: list[KnowledgebaseDocumentItem] = []


class ChatbotDetailsSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: ChatbotDetailsData


class UpdateGeneralSettingsRequest(BaseModel):
    chatbot_id: int
    chatbot_name: str
    description: str
    typing_indicator: bool


class UpdateAppearanceSettingsRequest(BaseModel):
    chatbot_id: int
    primary_color: str
    widget_position: str
    show_avatar: bool


class UpdateMessagesSettingsRequest(BaseModel):
    chatbot_id: int
    chat_title: str
    welcome_message: str
    input_placeholder: str


class UpdateSecuritySettingsRequest(BaseModel):
    chatbot_id: int
    ai_model: str
    allowed_domains: list[str]


class SettingsUpdateSuccessResponse(BaseModel):
    success: bool = True
    message: str


class DeleteChatbotData(BaseModel):
    chatbot_id: int
    status: str


class DeleteChatbotSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: DeleteChatbotData
