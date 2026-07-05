"""
Chatbot Settings module business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.auth.utils import USER_ROLE_ADMIN
from app.modules.chatbot.service import (
    ChatbotNotFoundError,
    ChatbotPermissionError,
    InvalidAIModelError,
    SuperAdminChatbotProtectedError,
)
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, CHATBOT_STATUS_PUBLISHED, Chatbot
from app.modules.chatbot_settings.schema import (
    ActivateChatbotData,
    ActivateChatbotSuccessResponse,
    ChatbotDetailsSuccessResponse,
    DeleteChatbotData,
    DeleteChatbotSuccessResponse,
    SettingsUpdateSuccessResponse,
    UpdateAppearanceSettingsRequest,
    UpdateGeneralSettingsRequest,
    UpdateMessagesSettingsRequest,
    UpdateSecuritySettingsRequest,
)
from app.modules.chatbot_settings.utils import (
    ChatbotSettingsNotFoundError,
    build_chatbot_details_data,
    can_hard_delete_chatbot,
    can_manage_chatbot,
    delete_knowledgebase_document,
    get_chatbot_owner,
    get_chatbot_settings_record,
    get_knowledgebase_documents,
    get_owned_chatbot,
    get_owned_chatbot_with_settings,
    get_viewable_chatbot,
    hard_delete_chatbot_record,
    is_superadmin_owned,
    restore_chromadb_vectors_for_chatbot,
    soft_delete_chatbot_record,
    validate_ai_model,
    validate_and_normalize_allowed_domains,
    validate_appearance_settings,
    validate_general_settings,
    validate_messages_settings,
)
from app.modules.chat_analysis.service import ensure_chat_analysis_for_chatbot
from app.modules.user_details.utils import is_admin
from app.modules.knowledgebase.service import (
    FileSizeExceededError,
    UnsupportedFileTypeError,
    UploadedFilePayload,
    _process_file_source,
    _process_url_source,
    _save_chunks_for_document,
    _validate_upload_payload,
)
from app.modules.knowledgebase.model import KnowledgebaseDocument

logger = logging.getLogger(__name__)


class ChatbotSettingsValidationError(Exception):
    """Raised when chatbot settings payload fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class KnowledgeBaseRequiredError(Exception):
    """Raised when a chatbot would be left without knowledge base sources."""


class ChatbotAlreadyDeletedError(Exception):
    """Raised when attempting to delete an already deleted chatbot."""


class ChatbotAlreadyActiveError(Exception):
    """Raised when attempting to activate a chatbot that is not deleted."""


class ChatbotActivatePermissionError(Exception):
    """Raised when a non-admin attempts to activate a chatbot."""


class OnlyDraftHardDeleteError(Exception):
    """Raised when a permanent delete is attempted on a non-draft chatbot."""


def get_chatbot_details(
    db: Session,
    user: User,
    chatbot_id: int,
) -> ChatbotDetailsSuccessResponse:
    """Fetch and return complete chatbot configuration for the settings page."""
    logger.info(
        "Fetching chatbot details for chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    chatbot = get_viewable_chatbot(db, user, chatbot_id)
    owner = get_chatbot_owner(db, chatbot)

    settings = get_chatbot_settings_record(chatbot)
    if settings is None:
        logger.warning(
            "Chatbot settings not found for chatbot_id=%s user_id=%s",
            chatbot_id,
            user.id,
        )
        raise ChatbotSettingsNotFoundError()

    documents = get_knowledgebase_documents(db, chatbot_id)
    logger.info(
        "Fetched %s knowledge base documents for chatbot_id=%s",
        len(documents),
        chatbot_id,
    )

    logger.info(
        "Chatbot details fetched successfully for chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    return ChatbotDetailsSuccessResponse(
        message=messages.CHATBOT_DETAILS_FETCH_SUCCESS,
        data=build_chatbot_details_data(
            chatbot,
            settings,
            documents,
            is_editable=can_manage_chatbot(user, chatbot, owner)
            and not bool(getattr(chatbot, "is_deleted", False)),
        ),
    )


def update_general_settings(
    db: Session,
    user: User,
    payload: UpdateGeneralSettingsRequest,
) -> SettingsUpdateSuccessResponse:
    """Update general chatbot information and typing indicator."""
    logger.info(
        "Updating general settings for chatbot_id=%s user_id=%s",
        payload.chatbot_id,
        user.id,
    )

    validation_error = validate_general_settings(
        chatbot_name=payload.chatbot_name,
        description=payload.description,
    )
    if validation_error:
        raise ChatbotSettingsValidationError(validation_error)

    chatbot, settings = get_owned_chatbot_with_settings(db, user, payload.chatbot_id)
    now = datetime.now(timezone.utc)

    chatbot.chatbot_name = payload.chatbot_name.strip()
    chatbot.description = payload.description.strip()
    chatbot.updated_at = now
    settings.typing_indicator = payload.typing_indicator
    settings.updated_at = now

    db.commit()

    logger.info("General settings updated for chatbot_id=%s", payload.chatbot_id)
    return SettingsUpdateSuccessResponse(message=messages.GENERAL_SETTINGS_UPDATED)


def update_appearance_settings(
    db: Session,
    user: User,
    payload: UpdateAppearanceSettingsRequest,
) -> SettingsUpdateSuccessResponse:
    """Update widget appearance settings."""
    logger.info(
        "Updating appearance settings for chatbot_id=%s user_id=%s",
        payload.chatbot_id,
        user.id,
    )

    validation_error = validate_appearance_settings(
        primary_color=payload.primary_color,
        widget_position=payload.widget_position,
    )
    if validation_error:
        raise ChatbotSettingsValidationError(validation_error)

    _, settings = get_owned_chatbot_with_settings(db, user, payload.chatbot_id)
    settings.primary_color = payload.primary_color.strip()
    settings.widget_position = payload.widget_position.strip()
    settings.show_avatar = payload.show_avatar
    settings.updated_at = datetime.now(timezone.utc)

    db.commit()

    logger.info("Appearance settings updated for chatbot_id=%s", payload.chatbot_id)
    return SettingsUpdateSuccessResponse(message=messages.APPEARANCE_UPDATED)


def update_messages_settings(
    db: Session,
    user: User,
    payload: UpdateMessagesSettingsRequest,
) -> SettingsUpdateSuccessResponse:
    """Update chatbot message settings."""
    logger.info(
        "Updating message settings for chatbot_id=%s user_id=%s",
        payload.chatbot_id,
        user.id,
    )

    validation_error = validate_messages_settings(
        chat_title=payload.chat_title,
        welcome_message=payload.welcome_message,
        input_placeholder=payload.input_placeholder,
    )
    if validation_error:
        raise ChatbotSettingsValidationError(validation_error)

    _, settings = get_owned_chatbot_with_settings(db, user, payload.chatbot_id)
    settings.chat_title = payload.chat_title.strip()
    settings.welcome_message = payload.welcome_message.strip()
    settings.input_placeholder = payload.input_placeholder.strip()
    settings.updated_at = datetime.now(timezone.utc)

    db.commit()

    logger.info("Message settings updated for chatbot_id=%s", payload.chatbot_id)
    return SettingsUpdateSuccessResponse(message=messages.MESSAGES_UPDATED)


def update_security_settings(
    db: Session,
    user: User,
    payload: UpdateSecuritySettingsRequest,
) -> SettingsUpdateSuccessResponse:
    """Update chatbot security settings including AI model and allowed domains."""
    logger.info(
        "Updating security settings for chatbot_id=%s user_id=%s",
        payload.chatbot_id,
        user.id,
    )

    ai_model_error = validate_ai_model(payload.ai_model)
    if ai_model_error:
        raise InvalidAIModelError()

    domain_error, normalized_domains = validate_and_normalize_allowed_domains(
        payload.allowed_domains
    )
    if domain_error:
        raise ChatbotSettingsValidationError(domain_error)

    chatbot, settings = get_owned_chatbot_with_settings(db, user, payload.chatbot_id)
    now = datetime.now(timezone.utc)

    chatbot.ai_model = payload.ai_model.strip()
    chatbot.updated_at = now
    settings.allowed_domains = normalized_domains
    settings.updated_at = now

    db.commit()

    logger.info("Security settings updated for chatbot_id=%s", payload.chatbot_id)
    return SettingsUpdateSuccessResponse(message=messages.SECURITY_SETTINGS_UPDATED)


def _get_documents_for_deletion(
    db: Session,
    chatbot_id: int,
    delete_document_ids: list[int],
) -> list[KnowledgebaseDocument]:
    """Return knowledge documents to delete after validating chatbot ownership."""
    if not delete_document_ids:
        return []

    documents = list(
        db.execute(
            select(KnowledgebaseDocument).where(
                KnowledgebaseDocument.id.in_(delete_document_ids),
                KnowledgebaseDocument.chatbot_id == chatbot_id,
            )
        ).scalars().all()
    )

    if len(documents) != len(set(delete_document_ids)):
        raise ChatbotSettingsValidationError(messages.KNOWLEDGE_DOCUMENT_NOT_FOUND)

    return documents


def update_knowledge_base(
    db: Session,
    user: User,
    chatbot_id: int,
    delete_document_ids: list[int],
    files: list[UploadedFilePayload],
    urls: list[str],
) -> SettingsUpdateSuccessResponse:
    """Replace knowledge base sources, regenerating chunks and vector embeddings."""
    logger.info(
        "Updating knowledge base for chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    get_owned_chatbot_with_settings(db, user, chatbot_id)

    normalized_urls = [url.strip() for url in urls if url and url.strip()]
    delete_ids = list(dict.fromkeys(delete_document_ids))

    existing_count = db.execute(
        select(func.count(KnowledgebaseDocument.id)).where(
            KnowledgebaseDocument.chatbot_id == chatbot_id
        )
    ).scalar_one()

    remaining_count = int(existing_count) - len(delete_ids) + len(files) + len(normalized_urls)
    if remaining_count < 1:
        raise KnowledgeBaseRequiredError()

    if files or normalized_urls:
        _validate_upload_payload(files, normalized_urls)

    documents_to_delete = _get_documents_for_deletion(db, chatbot_id, delete_ids)
    for document in documents_to_delete:
        delete_knowledgebase_document(db, document)

    db.commit()

    for file_payload in files:
        document = _process_file_source(db, chatbot_id, file_payload)
        _save_chunks_for_document(db, chatbot_id, document)

    for url in normalized_urls:
        document = _process_url_source(db, chatbot_id, url)
        _save_chunks_for_document(db, chatbot_id, document)

    final_count = db.execute(
        select(func.count(KnowledgebaseDocument.id)).where(
            KnowledgebaseDocument.chatbot_id == chatbot_id
        )
    ).scalar_one()
    if int(final_count) < 1:
        raise KnowledgeBaseRequiredError()

    logger.info("Knowledge base updated for chatbot_id=%s", chatbot_id)
    return SettingsUpdateSuccessResponse(message=messages.KNOWLEDGE_BASE_UPDATED)


def delete_chatbot(
    db: Session,
    user: User,
    chatbot_id: int,
) -> DeleteChatbotSuccessResponse:
    """Delete a chatbot: hard-delete drafts, soft-delete published chatbots."""
    logger.info(
        "Chatbot delete requested chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    if chatbot.is_deleted:
        raise ChatbotAlreadyDeletedError()

    owner = get_chatbot_owner(db, chatbot)

    is_hard_delete = chatbot.status == CHATBOT_STATUS_DRAFT
    if is_hard_delete:
        if not can_hard_delete_chatbot(user, chatbot, owner):
            logger.warning(
                "Unauthorized chatbot hard-delete attempt chatbot_id=%s owner_id=%s user_id=%s",
                chatbot_id,
                chatbot.user_id,
                user.id,
            )
            if user.role == USER_ROLE_ADMIN and is_superadmin_owned(owner):
                raise SuperAdminChatbotProtectedError()
            raise ChatbotPermissionError()
    elif not can_manage_chatbot(user, chatbot, owner):
        logger.warning(
            "Unauthorized chatbot delete attempt chatbot_id=%s owner_id=%s user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )
        if user.role == USER_ROLE_ADMIN and is_superadmin_owned(owner):
            raise SuperAdminChatbotProtectedError()
        raise ChatbotPermissionError()

    success_message = messages.CHATBOT_DELETED_SUCCESS
    deleted_status = chatbot.status

    try:
        if is_hard_delete:
            hard_delete_chatbot_record(db, chatbot)
            success_message = messages.CHATBOT_HARD_DELETED_SUCCESS
        else:
            soft_delete_chatbot_record(db, chatbot)
            deleted_status = chatbot.status

        db.commit()
    except ValueError as exc:
        db.rollback()
        if str(exc) == messages.ONLY_DRAFT_CAN_BE_HARD_DELETED:
            raise OnlyDraftHardDeleteError() from exc
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to delete chatbot_id=%s", chatbot_id)
        raise

    if not is_hard_delete:
        db.refresh(chatbot)

    logger.info(
        "Chatbot deleted chatbot_id=%s user_id=%s hard_delete=%s",
        chatbot_id,
        user.id,
        is_hard_delete,
    )

    return DeleteChatbotSuccessResponse(
        message=success_message,
        data=DeleteChatbotData(
            chatbot_id=chatbot_id,
            status=deleted_status if is_hard_delete else chatbot.status,
        ),
    )


def activate_chatbot(
    db: Session,
    user: User,
    chatbot_id: int,
) -> ActivateChatbotSuccessResponse:
    """Restore a soft-deleted chatbot so it can accept widget traffic again."""
    logger.info(
        "Chatbot activate requested chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    if not is_admin(user):
        logger.warning(
            "Unauthorized chatbot activate attempt chatbot_id=%s user_id=%s",
            chatbot_id,
            user.id,
        )
        raise ChatbotActivatePermissionError()

    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    if not chatbot.is_deleted:
        raise ChatbotAlreadyActiveError()

    owner = get_chatbot_owner(db, chatbot)
    if not can_manage_chatbot(user, chatbot, owner):
        logger.warning(
            "Unauthorized chatbot activate attempt chatbot_id=%s owner_id=%s user_id=%s",
            chatbot_id,
            chatbot.user_id,
            user.id,
        )
        if user.role == USER_ROLE_ADMIN and is_superadmin_owned(owner):
            raise SuperAdminChatbotProtectedError()
        raise ChatbotPermissionError()

    now = datetime.now(timezone.utc)
    chatbot.is_deleted = False
    chatbot.deleted_at = None
    chatbot.status = CHATBOT_STATUS_PUBLISHED
    if chatbot.published_at is None:
        chatbot.published_at = now
    chatbot.updated_at = now

    try:
        restore_chromadb_vectors_for_chatbot(db, chatbot_id)
        ensure_chat_analysis_for_chatbot(db, chatbot.id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to activate chatbot_id=%s", chatbot_id)
        raise

    db.refresh(chatbot)

    logger.info(
        "Chatbot activated chatbot_id=%s user_id=%s",
        chatbot_id,
        user.id,
    )

    return ActivateChatbotSuccessResponse(
        message=messages.CHATBOT_ACTIVATED_SUCCESS,
        data=ActivateChatbotData(
            chatbot_id=chatbot.id,
            status=chatbot.status,
        ),
    )
