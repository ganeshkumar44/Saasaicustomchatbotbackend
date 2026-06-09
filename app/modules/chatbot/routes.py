from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.chatbot import service
from app.modules.chatbot.schema import CreateChatbotDraftSuccessResponse
from app.modules.chatbot.utils import get_authenticated_user

router = APIRouter(
    prefix="/v1",
    tags=["Chatbot Builder"],
)


@router.post(
    "/chatbots",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateChatbotDraftSuccessResponse,
)
def create_chatbot_draft(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create a blank chatbot draft for the authenticated user."""
    return service.create_chatbot_draft(db, current_user)
