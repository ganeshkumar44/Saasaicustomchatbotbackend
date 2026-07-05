"""
Chatbot Settings module helper utilities.
"""

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import USER_ROLE_ADMIN, USER_ROLE_SUPERADMIN
from app.modules.chatbot.model import (
    CHATBOT_STATUS_DELETED,
    CHATBOT_STATUS_DRAFT,
    CHATBOT_STATUS_PUBLISHED,
    Chatbot,
    ChatbotSettings,
)
from app.modules.chatbot.schema import AIModelEnum
from app.modules.chatbot.service import (
    ChatbotNotFoundError,
    ChatbotPermissionError,
    SuperAdminChatbotProtectedError,
)
from app.modules.chatbot_settings.schema import ChatbotDetailsData, KnowledgebaseDocumentItem
from app.modules.knowledgebase.model import (
    SOURCE_TYPE_FILE,
    SOURCE_TYPE_URL,
    KnowledgebaseDocument,
)
from app.modules.knowledgebase.utils import KNOWLEDGEBASE_UPLOAD_DIR
from app.modules.knowledge_chunks.utils import get_chunks_by_document_id
from app.modules.user_details.utils import is_admin, is_superadmin
from app.modules.chat_analysis.service import ensure_chat_analysis_for_chatbot
from app.embeddings.embedding_service import generate_embeddings_for_chunks
from app.vectorstore.chroma_service import store_chunks_in_chromadb
from app.vectorstore.chroma_client import get_knowledge_base_collection

logger = logging.getLogger(__name__)

EXTRACTED_TEXT_PREVIEW_LENGTH = 250
CHATBOT_NAME_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 1000
CHAT_TITLE_MAX_LENGTH = 100
WELCOME_MESSAGE_MAX_LENGTH = 1000
INPUT_PLACEHOLDER_MAX_LENGTH = 150
ALLOWED_WIDGET_POSITIONS = {"bottom-right", "bottom-left"}
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
_DOMAIN_URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}(?:/.*)?$",
    re.IGNORECASE,
)


def get_chatbot_owner(db: Session, chatbot: Chatbot) -> User:
    """Return the chatbot owner or raise when the owner record is missing."""
    owner = db.get(User, chatbot.user_id)
    if owner is None:
        logger.warning(
            "Chatbot owner not found chatbot_id=%s owner_id=%s",
            chatbot.id,
            chatbot.user_id,
        )
        raise ChatbotNotFoundError()
    return owner


def is_superadmin_owned(owner: User) -> bool:
    """Return True when the chatbot belongs to a SuperAdmin account."""
    return owner.role == USER_ROLE_SUPERADMIN


def can_view_chatbot(user: User, chatbot: Chatbot, owner: User) -> bool:
    """Return True when the user may view chatbot details."""
    if is_superadmin(user):
        return True
    if chatbot.user_id == user.id:
        return True
    if user.role == USER_ROLE_ADMIN:
        return True
    return False


def can_manage_chatbot(user: User, chatbot: Chatbot, owner: User) -> bool:
    """Return True when the user may edit, delete, or upload to a chatbot."""
    if is_superadmin(user):
        return True
    if chatbot.user_id == user.id:
        return True
    if user.role == USER_ROLE_ADMIN and not is_superadmin_owned(owner):
        return True
    return False


def can_delete_chatbot(user: User, chatbot: Chatbot, owner: User) -> bool:
    """Return True when the user may delete a chatbot (soft or hard)."""
    return can_manage_chatbot(user, chatbot, owner)


def can_hard_delete_chatbot(user: User, chatbot: Chatbot, owner: User) -> bool:
    """Return True when the user may permanently delete a draft chatbot."""
    if chatbot.status != CHATBOT_STATUS_DRAFT or chatbot.is_deleted:
        return False
    return can_manage_chatbot(user, chatbot, owner)


def _raise_chatbot_access_error(user: User, chatbot: Chatbot, owner: User) -> None:
    """Raise the appropriate access error for a denied chatbot management attempt."""
    if user.role == USER_ROLE_ADMIN and is_superadmin_owned(owner):
        raise SuperAdminChatbotProtectedError()
    raise ChatbotPermissionError()


def can_access_chatbot(user: User, chatbot: Chatbot) -> bool:
    """Return True when the user may manage the chatbot (legacy alias)."""
    if chatbot.user_id == user.id:
        return True
    if is_superadmin(user):
        return True
    if user.role == USER_ROLE_ADMIN:
        return True
    return False


def get_owned_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot the user may modify or raise a domain error."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        logger.warning("Chatbot not found for chatbot_id=%s user_id=%s", chatbot_id, user.id)
        raise ChatbotNotFoundError()

    if getattr(chatbot, "is_deleted", False):
        logger.warning(
            "Deleted chatbot access attempt chatbot_id=%s user_id=%s",
            chatbot_id,
            user.id,
        )
        raise ChatbotNotFoundError()

    owner = get_chatbot_owner(db, chatbot)
    if not can_manage_chatbot(user, chatbot, owner):
        logger.warning(
            "Unauthorized chatbot modify attempt chatbot_id=%s owner_id=%s user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )
        _raise_chatbot_access_error(user, chatbot, owner)

    if is_admin(user) and chatbot.user_id != user.id:
        logger.info(
            "Admin accessing chatbot chatbot_id=%s owner_id=%s admin_user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )

    return chatbot


def get_viewable_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot the user may view, including soft-deleted chatbots."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        logger.warning("Chatbot not found for chatbot_id=%s user_id=%s", chatbot_id, user.id)
        raise ChatbotNotFoundError()

    owner = get_chatbot_owner(db, chatbot)
    if not can_view_chatbot(user, chatbot, owner):
        logger.warning(
            "Unauthorized chatbot access attempt chatbot_id=%s owner_id=%s user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )
        raise ChatbotPermissionError()

    if is_admin(user) and chatbot.user_id != user.id:
        logger.info(
            "Admin accessing chatbot chatbot_id=%s owner_id=%s admin_user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )

    return chatbot


def resolve_chatbot_details_status(chatbot: Chatbot) -> str:
    """Return the display status for chatbot details, including soft-deleted chatbots."""
    if getattr(chatbot, "is_deleted", False):
        return CHATBOT_STATUS_DELETED
    return chatbot.status


def get_chatbot_settings_record(chatbot: Chatbot) -> ChatbotSettings | None:
    """Return the chatbot_settings row for a chatbot, if one exists."""
    return chatbot.settings


def get_owned_chatbot_with_settings(
    db: Session,
    user: User,
    chatbot_id: int,
) -> tuple[Chatbot, ChatbotSettings]:
    """Return an owned chatbot and its settings or raise a domain error."""
    chatbot = get_owned_chatbot(db, user, chatbot_id)
    settings = get_chatbot_settings_record(chatbot)
    if settings is None:
        raise ChatbotSettingsNotFoundError()
    return chatbot, settings


class ChatbotSettingsNotFoundError(Exception):
    """Raised when no chatbot_settings record exists for the chatbot."""


def _is_blank(value: str | None) -> bool:
    """Return True when a value is None or contains only whitespace."""
    return value is None or not value.strip()


def validate_general_settings(
    *,
    chatbot_name: str | None,
    description: str | None,
) -> str | None:
    """Validate general settings fields."""
    if _is_blank(chatbot_name):
        return messages.CHATBOT_NAME_REQUIRED
    if len(chatbot_name.strip()) > CHATBOT_NAME_MAX_LENGTH:
        return messages.CHATBOT_NAME_TOO_LONG
    if _is_blank(description):
        return messages.DESCRIPTION_REQUIRED
    if len(description.strip()) > DESCRIPTION_MAX_LENGTH:
        return messages.DESCRIPTION_TOO_LONG
    return None


def validate_appearance_settings(
    *,
    primary_color: str | None,
    widget_position: str | None,
) -> str | None:
    """Validate appearance settings fields."""
    if _is_blank(primary_color) or not _HEX_COLOR_PATTERN.fullmatch(primary_color.strip()):
        return messages.INVALID_COLOR
    if _is_blank(widget_position) or widget_position.strip() not in ALLOWED_WIDGET_POSITIONS:
        return messages.INVALID_WIDGET_POSITION
    return None


def validate_messages_settings(
    *,
    chat_title: str | None,
    welcome_message: str | None,
    input_placeholder: str | None,
) -> str | None:
    """Validate chat message settings fields."""
    if _is_blank(chat_title):
        return messages.CHAT_TITLE_REQUIRED
    if len(chat_title.strip()) > CHAT_TITLE_MAX_LENGTH:
        return messages.CHAT_TITLE_TOO_LONG
    if _is_blank(welcome_message):
        return messages.WELCOME_MESSAGE_REQUIRED
    if len(welcome_message.strip()) > WELCOME_MESSAGE_MAX_LENGTH:
        return messages.WELCOME_MESSAGE_TOO_LONG
    if _is_blank(input_placeholder):
        return messages.INPUT_PLACEHOLDER_REQUIRED
    if len(input_placeholder.strip()) > INPUT_PLACEHOLDER_MAX_LENGTH:
        return messages.INPUT_PLACEHOLDER_TOO_LONG
    return None


def validate_ai_model(ai_model: str | None) -> str | None:
    """Validate the chatbot AI model against allowed values."""
    allowed_models = {item.value for item in AIModelEnum}
    if _is_blank(ai_model) or ai_model.strip() not in allowed_models:
        return messages.INVALID_AI_MODEL
    return None


def normalize_domain(domain: str) -> str:
    """Normalize a domain URL for storage and comparison."""
    return domain.strip().rstrip("/")


def _is_valid_domain_url(value: str) -> bool:
    """Return True when the value is a valid http(s) domain URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    hostname = parsed.netloc.split(":")[0].lower()
    if hostname in {"localhost", "127.0.0.1"}:
        return True

    return bool(_DOMAIN_URL_PATTERN.fullmatch(value))


def validate_and_normalize_allowed_domains(domains: list[str]) -> tuple[str | None, str]:
    """
    Validate allowed domains and return a comma-separated normalized string.

    Returns (error_message, normalized_domains_string).
    """
    if not domains:
        return messages.ALLOWED_DOMAINS_REQUIRED, ""

    normalized_domains: list[str] = []
    seen: set[str] = set()

    for domain in domains:
        trimmed = domain.strip()
        if not trimmed:
            continue

        if not _is_valid_domain_url(trimmed):
            return messages.INVALID_DOMAIN, ""

        normalized = normalize_domain(trimmed).lower()
        if normalized in seen:
            continue

        seen.add(normalized)
        normalized_domains.append(normalize_domain(trimmed))

    if not normalized_domains:
        return messages.ALLOWED_DOMAINS_REQUIRED, ""

    return None, ",".join(normalized_domains)


def delete_chromadb_vectors_for_document(document_id: int) -> None:
    """Remove all ChromaDB vectors associated with a knowledge document."""
    try:
        collection = get_knowledge_base_collection()
        collection.delete(where={"document_id": document_id})
        logger.info("Deleted ChromaDB vectors for document_id=%s", document_id)
    except Exception:
        logger.exception(
            "Failed to delete ChromaDB vectors for document_id=%s",
            document_id,
        )


def delete_chromadb_vectors_for_chatbot(chatbot_id: int) -> None:
    """Remove all ChromaDB vectors associated with a chatbot."""
    try:
        collection = get_knowledge_base_collection()
        collection.delete(where={"chatbot_id": chatbot_id})
        logger.info("Deleted ChromaDB vectors for chatbot_id=%s", chatbot_id)
    except Exception:
        logger.exception(
            "Failed to delete ChromaDB vectors for chatbot_id=%s",
            chatbot_id,
        )


def restore_chromadb_vectors_for_chatbot(db: Session, chatbot_id: int) -> None:
    """Re-generate and store ChromaDB vectors from existing knowledge chunks."""
    documents = get_knowledgebase_documents(db, chatbot_id)
    restored_chunks = 0

    for document in documents:
        chunks = get_chunks_by_document_id(db, document.id)
        if not chunks:
            continue

        chunks_data = [
            {
                "chunk_index": chunk.chunk_index,
                "chunk_text": chunk.chunk_text,
                "character_count": chunk.character_count,
            }
            for chunk in chunks
        ]
        embedded_chunks = generate_embeddings_for_chunks(chunks_data)
        if embedded_chunks:
            restored_chunks += store_chunks_in_chromadb(
                chatbot_id,
                document.id,
                embedded_chunks,
            )

    logger.info(
        "Restored %s ChromaDB vectors for chatbot_id=%s",
        restored_chunks,
        chatbot_id,
    )


def hard_delete_chatbot_record(db: Session, chatbot: Chatbot) -> None:
    """Permanently delete a draft chatbot and all related data."""
    if chatbot.status != CHATBOT_STATUS_DRAFT:
        raise ValueError(messages.ONLY_DRAFT_CAN_BE_HARD_DELETED)

    chatbot_id = chatbot.id
    documents = get_knowledgebase_documents(db, chatbot_id)
    for document in documents:
        delete_knowledgebase_document(db, document)

    delete_chromadb_vectors_for_chatbot(chatbot_id)

    upload_dir = KNOWLEDGEBASE_UPLOAD_DIR / str(chatbot_id)
    if upload_dir.exists():
        try:
            shutil.rmtree(upload_dir)
            logger.info("Removed knowledge base upload directory for chatbot_id=%s", chatbot_id)
        except OSError:
            logger.exception(
                "Failed to remove knowledge base upload directory for chatbot_id=%s",
                chatbot_id,
            )

    db.delete(chatbot)
    logger.info("Hard-deleted draft chatbot_id=%s", chatbot_id)


def soft_delete_chatbot_record(db: Session, chatbot: Chatbot) -> None:
    """Soft-delete a chatbot and remove its knowledge base vectors from ChromaDB."""
    if chatbot.is_deleted:
        return

    documents = get_knowledgebase_documents(db, chatbot.id)
    for document in documents:
        delete_chromadb_vectors_for_document(document.id)

    delete_chromadb_vectors_for_chatbot(chatbot.id)

    now = datetime.now(timezone.utc)
    chatbot.is_deleted = True
    chatbot.deleted_at = now
    chatbot.updated_at = now


def restore_chatbot_record(db: Session, chatbot: Chatbot) -> None:
    """Restore a soft-deleted chatbot and rebuild its ChromaDB vectors."""
    if not chatbot.is_deleted:
        return

    now = datetime.now(timezone.utc)
    chatbot.is_deleted = False
    chatbot.deleted_at = None
    chatbot.status = CHATBOT_STATUS_PUBLISHED
    if chatbot.published_at is None:
        chatbot.published_at = now
    chatbot.updated_at = now
    restore_chromadb_vectors_for_chatbot(db, chatbot.id)
    ensure_chat_analysis_for_chatbot(db, chatbot.id)


def soft_delete_all_chatbots_for_user(db: Session, user_id: int) -> int:
    """Soft-delete all active chatbots owned by a user."""
    chatbots = list(
        db.execute(
            select(Chatbot).where(
                Chatbot.user_id == user_id,
                Chatbot.is_deleted.is_(False),
            )
        ).scalars().all()
    )
    for chatbot in chatbots:
        soft_delete_chatbot_record(db, chatbot)

    logger.info("Soft-deleted %s chatbots for user_id=%s", len(chatbots), user_id)
    return len(chatbots)


def restore_all_chatbots_for_user(db: Session, user_id: int) -> int:
    """Restore all soft-deleted chatbots owned by a user."""
    chatbots = list(
        db.execute(
            select(Chatbot).where(
                Chatbot.user_id == user_id,
                Chatbot.is_deleted.is_(True),
            )
        ).scalars().all()
    )
    for chatbot in chatbots:
        restore_chatbot_record(db, chatbot)

    logger.info("Restored %s chatbots for user_id=%s", len(chatbots), user_id)
    return len(chatbots)


def delete_knowledgebase_document(
    db: Session,
    document: KnowledgebaseDocument,
) -> None:
    """Delete a knowledge document, its stored file, and associated vectors."""
    delete_chromadb_vectors_for_document(document.id)

    if document.file_path:
        file_path = Path(document.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                logger.exception("Failed to delete knowledge base file %s", file_path)

    db.delete(document)


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
    *,
    is_editable: bool | None = None,
) -> ChatbotDetailsData:
    """Merge chatbot and settings records into a single response payload."""
    resolved_editable = (
        is_editable
        if is_editable is not None
        else not bool(getattr(chatbot, "is_deleted", False))
    )
    return ChatbotDetailsData(
        id=chatbot.id,
        user_id=chatbot.user_id,
        chatbot_name=chatbot.chatbot_name,
        description=chatbot.description,
        personality=chatbot.personality,
        ai_model=chatbot.ai_model,
        language=chatbot.language,
        status=resolve_chatbot_details_status(chatbot),
        is_editable=resolved_editable,
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
