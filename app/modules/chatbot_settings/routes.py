from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError
from app.modules.chatbot.utils import get_authenticated_user
from app.modules.chatbot_settings import service
from app.modules.chatbot_settings.schema import ChatbotDetailsSuccessResponse

router = APIRouter(
    prefix="/v1",
    tags=["Chatbot Settings"],
)


@router.get(
    "/chatbots/{chatbot_id}/details",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotDetailsSuccessResponse,
)
def get_chatbot_details(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return complete chatbot configuration for the settings page."""
    try:
        return service.get_chatbot_details(db, current_user, chatbot_id)
    except ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.CHATBOT_NOT_FOUND,
            },
        )
    except ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.UNAUTHORIZED_CHATBOT_ACCESS,
            },
        )
    except service.ChatbotSettingsNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.CHATBOT_SETTINGS_NOT_FOUND,
            },
        )
