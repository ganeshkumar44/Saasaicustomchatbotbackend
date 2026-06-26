"""
Chatbot Settings module helper utilities.
"""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import Chatbot, ChatbotSettings
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError
from app.modules.chatbot_settings.schema import ChatbotDetailsData, KnowledgebaseDocumentItem
from app.modules.knowledgebase.model import (
    SOURCE_TYPE_FILE,
    SOURCE_TYPE_URL,
    KnowledgebaseDocument,
)

logger = logging.getLogger(__name__)

EXTRACTED_TEXT_PREVIEW_LENGTH = 250


def get_owned_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot owned by the authenticated user or raise a domain error."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        logger.warning("Chatbot not found for chatbot_id=%s user_id=%s", chatbot_id, user.id)
        raise ChatbotNotFoundError()

    if chatbot.user_id != user.id:
        logger.warning(
            "Unauthorized chatbot access attempt chatbot_id=%s owner_id=%s user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )
        raise ChatbotPermissionError()

    return chatbot


def get_chatbot_settings_record(chatbot: Chatbot) -> ChatbotSettings | None:
    """Return the chatbot_settings row for a chatbot, if one exists."""
    return chatbot.settings


def get_knowledgebase_documents(
    db: Session,
    chatbot_id: int,
) -> list[KnowledgebaseDocument]:
    """Return all knowledge base documents for a chatbot ordered by upload date."""
    return list(
        db.execute(
            select(KnowledgebaseDocument)
            .where(KnowledgebaseDocument.chatbot_id == chatbot_id)
            .order_by(KnowledgebaseDocument.created_at.desc())
        ).scalars().all()
    )


def build_extracted_text_preview(extracted_text: str | None) -> tuple[str | None, int | None]:
    """Return a short preview and total length without exposing full extracted text."""
    if not extracted_text or not extracted_text.strip():
        return None, None

    normalized = extracted_text.strip()
    text_length = len(normalized)
    if text_length <= EXTRACTED_TEXT_PREVIEW_LENGTH:
        return normalized, text_length

    return normalized[:EXTRACTED_TEXT_PREVIEW_LENGTH], text_length


def build_knowledgebase_document_item(
    document: KnowledgebaseDocument,
) -> KnowledgebaseDocumentItem:
    """Map a knowledgebase_documents row to the API response shape."""
    preview, text_length = build_extracted_text_preview(document.extracted_text)

    original_file_name: str | None = None
    stored_file_name: str | None = None
    file_extension: str | None = None
    url: str | None = None

    if document.source_type == SOURCE_TYPE_FILE:
        original_file_name = document.original_name
        if document.file_path:
            stored_file_name = Path(document.file_path).name
        if document.file_type:
            file_extension = document.file_type.lstrip(".")
    elif document.source_type == SOURCE_TYPE_URL:
        url = document.source_url or document.original_name

    return KnowledgebaseDocumentItem(
        id=document.id,
        chatbot_id=document.chatbot_id,
        source_type=document.source_type,
        original_file_name=original_file_name,
        stored_file_name=stored_file_name,
        file_extension=file_extension,
        file_size=document.file_size,
        url=url,
        processing_status=document.processing_status,
        extracted_text_preview=preview,
        extracted_text_length=text_length,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def build_chatbot_details_data(
    chatbot: Chatbot,
    settings: ChatbotSettings,
    knowledgebase_documents: list[KnowledgebaseDocument] | None = None,
) -> ChatbotDetailsData:
    """Merge chatbot and settings records into a single response payload."""
    return ChatbotDetailsData(
        id=chatbot.id,
        user_id=chatbot.user_id,
        chatbot_name=chatbot.chatbot_name,
        description=chatbot.description,
        personality=chatbot.personality,
        ai_model=chatbot.ai_model,
        language=chatbot.language,
        status=chatbot.status,
        published_at=chatbot.published_at,
        created_at=chatbot.created_at,
        updated_at=chatbot.updated_at,
        settings_id=settings.id,
        public_key=settings.public_key,
        embed_code=settings.embed_code,
        allowed_domains=settings.allowed_domains,
        typing_indicator=settings.typing_indicator,
        primary_color=settings.primary_color,
        text_color=settings.text_color,
        widget_position=settings.widget_position,
        show_avatar=settings.show_avatar,
        chat_title=settings.chat_title,
        welcome_message=settings.welcome_message,
        input_placeholder=settings.input_placeholder,
        settings_created_at=settings.created_at,
        settings_updated_at=settings.updated_at,
        knowledgebase_documents=[
            build_knowledgebase_document_item(document)
            for document in (knowledgebase_documents or [])
        ],
    )
