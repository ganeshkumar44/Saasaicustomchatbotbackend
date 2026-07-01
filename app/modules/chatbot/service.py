from datetime import datetime, timezone

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.knowledgebase.model import (
    SOURCE_TYPE_FILE,
    SOURCE_TYPE_URL,
    KnowledgebaseDocument,
)
from app.modules.chatbot.model import (
    CHATBOT_STATUS_DRAFT,
    CHATBOT_STATUS_PUBLISHED,
    Chatbot,
    ChatbotSettings,
)
from app.modules.chatbot.utils import (
    DEFAULT_CHAT_TITLE,
    DEFAULT_INPUT_PLACEHOLDER,
    DEFAULT_PRIMARY_COLOR,
    DEFAULT_SHOW_AVATAR,
    DEFAULT_TEXT_COLOR,
    DEFAULT_TYPING_INDICATOR,
    DEFAULT_WELCOME_MESSAGE,
    DEFAULT_WIDGET_POSITION,
    find_unfinished_draft_for_user,
    generate_embed_code,
    generate_unique_public_key,
    get_default_allowed_domains,
)
from app.modules.chat_analysis.service import ensure_chat_analysis_for_chatbot
from app.modules.chatbot.schema import (
    AIModelEnum,
    CreateChatbotDraftData,
    CreateChatbotDraftSuccessResponse,
    LanguageEnum,
    PersonalityEnum,
    UpdateBasicInfoRequest,
    UpdateBasicInfoData,
    UpdateBasicInfoSuccessResponse,
    UpdateBehaviourRequest,
    UpdateBehaviourData,
    UpdateBehaviourSuccessResponse,
    ChatbotReviewData,
    ChatbotReviewSuccessResponse,
    KnowledgebaseSummary,
    PublishChatbotData,
    PublishChatbotSuccessResponse,
)

logger = logging.getLogger(__name__)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class ChatbotPermissionError(Exception):
    """Raised when the user does not own the chatbot."""


class ChatbotNameRequiredError(Exception):
    """Raised when chatbot_name is missing or empty."""


class InvalidPersonalityError(Exception):
    """Raised when personality is not an allowed value."""


class InvalidAIModelError(Exception):
    """Raised when ai_model is not an allowed value."""


class InvalidLanguageError(Exception):
    """Raised when language is not an allowed value."""


class ChatbotIncompleteConfigError(Exception):
    """Raised when required builder steps are not completed before publish."""

    def __init__(self, missing_steps: list[str]) -> None:
        self.missing_steps = missing_steps
        super().__init__()


def create_chatbot_draft(db: Session, user: User) -> CreateChatbotDraftSuccessResponse:
    """
    Return an existing unfinished draft or create a new blank chatbot draft.

    At most one unfinished draft (no basic info) exists per user at any time.
    """
    existing_draft = find_unfinished_draft_for_user(db, user.id)
    if existing_draft is not None:
        logger.info(
            "Returning existing unfinished draft chatbot_id=%s user_id=%s",
            existing_draft.id,
            user.id,
        )
        return CreateChatbotDraftSuccessResponse(
            message=messages.DRAFT_CHATBOT_EXISTS,
            data=CreateChatbotDraftData(
                chatbot_id=existing_draft.id,
                status=existing_draft.status,
            ),
        )

    chatbot = Chatbot(
        user_id=user.id,
        chatbot_name=None,
        description=None,
        personality=None,
        language=None,
        ai_model=None,
        status=CHATBOT_STATUS_DRAFT,
    )

    db.add(chatbot)
    db.commit()
    db.refresh(chatbot)

    logger.info("Created new draft chatbot_id=%s user_id=%s", chatbot.id, user.id)

    return CreateChatbotDraftSuccessResponse(
        message=messages.DRAFT_CHATBOT_CREATED,
        data=CreateChatbotDraftData(
            chatbot_id=chatbot.id,
            status=chatbot.status,
        ),
    )


def update_basic_info(
    db: Session,
    user: User,
    chatbot_id: int,
    payload: UpdateBasicInfoRequest,
) -> UpdateBasicInfoSuccessResponse:
    """Update Step 1 basic information on an existing chatbot draft."""
    if not payload.chatbot_name or not payload.chatbot_name.strip():
        raise ChatbotNameRequiredError()

    chatbot = db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise ChatbotNotFoundError()

    if chatbot.user_id != user.id:
        raise ChatbotPermissionError()

    chatbot.chatbot_name = payload.chatbot_name.strip()
    chatbot.description = (payload.description or "").strip() or None
    chatbot.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(chatbot)

    return UpdateBasicInfoSuccessResponse(
        message="Basic information updated successfully",
        data=UpdateBasicInfoData(
            chatbot_id=chatbot.id,
            chatbot_name=chatbot.chatbot_name,
            description=chatbot.description,
            status=chatbot.status,
        ),
    )


def _get_owned_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot owned by the user or raise a domain error."""
    chatbot = db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise ChatbotNotFoundError()

    if chatbot.user_id != user.id:
        raise ChatbotPermissionError()

    return chatbot


def update_behaviour(
    db: Session,
    user: User,
    chatbot_id: int,
    payload: UpdateBehaviourRequest,
) -> UpdateBehaviourSuccessResponse:
    """Update Step 2 behaviour settings on an existing chatbot draft."""
    allowed_personalities = {item.value for item in PersonalityEnum}
    allowed_ai_models = {item.value for item in AIModelEnum}
    allowed_languages = {item.value for item in LanguageEnum}

    if payload.personality not in allowed_personalities:
        raise InvalidPersonalityError()

    if payload.ai_model not in allowed_ai_models:
        raise InvalidAIModelError()

    if payload.language not in allowed_languages:
        raise InvalidLanguageError()

    chatbot = _get_owned_chatbot(db, user, chatbot_id)

    chatbot.personality = payload.personality
    chatbot.ai_model = payload.ai_model
    chatbot.language = payload.language
    chatbot.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(chatbot)

    return UpdateBehaviourSuccessResponse(
        message="Behaviour updated successfully",
        data=UpdateBehaviourData(
            chatbot_id=chatbot.id,
            personality=chatbot.personality,
            ai_model=chatbot.ai_model,
            language=chatbot.language,
        ),
    )


def _build_knowledgebase_summary(
    db: Session,
    chatbot_id: int,
) -> KnowledgebaseSummary:
    """Calculate knowledge base source counts for a chatbot."""
    documents = db.execute(
        select(KnowledgebaseDocument).where(
            KnowledgebaseDocument.chatbot_id == chatbot_id
        )
    ).scalars().all()

    total_files_uploaded = sum(
        1 for document in documents if document.source_type == SOURCE_TYPE_FILE
    )
    total_urls_uploaded = sum(
        1 for document in documents if document.source_type == SOURCE_TYPE_URL
    )

    return KnowledgebaseSummary(
        total_files_uploaded=total_files_uploaded,
        total_urls_uploaded=total_urls_uploaded,
        total_knowledge_sources=len(documents),
    )


def get_chatbot_review(
    db: Session,
    user: User,
    chatbot_id: int,
) -> ChatbotReviewSuccessResponse:
    """Return a review summary of all chatbot builder steps."""
    chatbot = _get_owned_chatbot(db, user, chatbot_id)
    knowledgebase_summary = _build_knowledgebase_summary(db, chatbot_id)

    return ChatbotReviewSuccessResponse(
        message="Chatbot review data fetched successfully",
        data=ChatbotReviewData(
            chatbot_id=chatbot.id,
            chatbot_name=chatbot.chatbot_name,
            description=chatbot.description,
            personality=chatbot.personality,
            ai_model=chatbot.ai_model,
            language=chatbot.language,
            status=chatbot.status,
            knowledgebase=knowledgebase_summary,
        ),
    )


def _get_missing_publish_steps(chatbot: Chatbot, db: Session, chatbot_id: int) -> list[str]:
    """Return human-readable labels for incomplete builder steps."""
    missing_steps: list[str] = []

    if not chatbot.chatbot_name or not chatbot.chatbot_name.strip():
        missing_steps.append("Basic Info")

    if not chatbot.personality or not chatbot.ai_model or not chatbot.language:
        missing_steps.append("Behaviour")

    knowledgebase_summary = _build_knowledgebase_summary(db, chatbot_id)
    if knowledgebase_summary.total_knowledge_sources < 1:
        missing_steps.append("Knowledge Base")

    return missing_steps


def _create_default_chatbot_settings(
    db: Session,
    chatbot_id: int,
) -> ChatbotSettings:
    """Create default widget settings for a newly published chatbot."""
    public_key = generate_unique_public_key(db)
    embed_code = generate_embed_code(public_key)

    settings = ChatbotSettings(
        chatbot_id=chatbot_id,
        typing_indicator=DEFAULT_TYPING_INDICATOR,
        primary_color=DEFAULT_PRIMARY_COLOR,
        text_color=DEFAULT_TEXT_COLOR,
        widget_position=DEFAULT_WIDGET_POSITION,
        show_avatar=DEFAULT_SHOW_AVATAR,
        chat_title=DEFAULT_CHAT_TITLE,
        welcome_message=DEFAULT_WELCOME_MESSAGE,
        input_placeholder=DEFAULT_INPUT_PLACEHOLDER,
        public_key=public_key,
        embed_code=embed_code,
        allowed_domains=get_default_allowed_domains(),
    )
    db.add(settings)
    return settings


def publish_chatbot(
    db: Session,
    user: User,
    chatbot_id: int,
) -> PublishChatbotSuccessResponse:
    """Validate builder steps, publish the chatbot, and create default settings."""
    chatbot = _get_owned_chatbot(db, user, chatbot_id)

    missing_steps = _get_missing_publish_steps(chatbot, db, chatbot_id)
    if missing_steps:
        raise ChatbotIncompleteConfigError(missing_steps)

    if chatbot.status == CHATBOT_STATUS_PUBLISHED and chatbot.settings is not None:
        ensure_chat_analysis_for_chatbot(db, chatbot.id)
        db.commit()
        return PublishChatbotSuccessResponse(
            message="Chatbot published successfully",
            data=PublishChatbotData(
                chatbot_id=chatbot.id,
                status=chatbot.status,
                public_key=chatbot.settings.public_key,
                embed_code=chatbot.settings.embed_code,
            ),
        )

    now = datetime.now(timezone.utc)
    chatbot.status = CHATBOT_STATUS_PUBLISHED
    chatbot.published_at = now
    chatbot.updated_at = now

    settings = chatbot.settings
    if settings is None:
        settings = _create_default_chatbot_settings(db, chatbot.id)

    ensure_chat_analysis_for_chatbot(db, chatbot.id)

    db.commit()
    db.refresh(chatbot)
    db.refresh(settings)

    return PublishChatbotSuccessResponse(
        message="Chatbot published successfully",
        data=PublishChatbotData(
            chatbot_id=chatbot.id,
            status=chatbot.status,
            public_key=settings.public_key,
            embed_code=settings.embed_code,
        ),
    )
