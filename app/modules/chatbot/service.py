from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.chatbot.schema import (
    CreateChatbotDraftData,
    CreateChatbotDraftSuccessResponse,
    UpdateBasicInfoRequest,
    UpdateBasicInfoData,
    UpdateBasicInfoSuccessResponse,
)


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class ChatbotPermissionError(Exception):
    """Raised when the user does not own the chatbot."""


class ChatbotNameRequiredError(Exception):
    """Raised when chatbot_name is missing or empty."""


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
