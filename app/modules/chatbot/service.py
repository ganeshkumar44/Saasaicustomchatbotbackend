from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
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
)


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


def create_chatbot_draft(db: Session, user: User) -> CreateChatbotDraftSuccessResponse:
    """Create a blank chatbot draft owned by the authenticated user."""
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

    return CreateChatbotDraftSuccessResponse(
        message="Chatbot draft created successfully",
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
