from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.dashboard import service
from app.modules.dashboard.schema import ChatbotListSuccessResponse

router = APIRouter(
    prefix="/v1",
    tags=["Dashboard"],
)


@router.get(
    "/chatbot-list",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotListSuccessResponse,
)
def get_chatbot_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return chatbots for the dashboard with conversation and document counts."""
    return service.get_chatbot_list(db, current_user)
