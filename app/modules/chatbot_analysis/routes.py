from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.chatbot_analysis import service
from app.modules.chatbot_analysis.schema import ChatbotAnalyticsSuccessResponse

router = APIRouter(
    prefix="/v1",
    tags=["Chatbot Analysis"],
)


@router.get(
    "/analysis/details",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotAnalyticsSuccessResponse,
)
def get_chatbot_analytics_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return chatbot analytics from the chat_analysis table for the dashboard."""
    return service.get_chatbot_analytics_details(db, current_user)
