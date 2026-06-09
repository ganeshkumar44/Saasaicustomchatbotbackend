from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.chatbot.model import CHATBOT_STATUS_DRAFT, Chatbot
from app.modules.chatbot.schema import (
    CreateChatbotDraftData,
    CreateChatbotDraftSuccessResponse,
)


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
