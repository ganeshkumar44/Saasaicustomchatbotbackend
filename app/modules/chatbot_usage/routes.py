"""Chatbot usage API routes."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.chatbot.service import (
    ChatbotNotFoundError,
    ChatbotPermissionError,
    SuperAdminChatbotProtectedError,
)
from app.modules.chatbot_settings.utils import get_owned_chatbot
from app.modules.chatbot_usage.schema import ChatbotUsageSuccessResponse
from app.modules.chatbot_usage import service

router = APIRouter(
    prefix="/v1",
    tags=["Subscription Usage"],
)


@router.get(
    "/subscription/usage/{chatbot_id}",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotUsageSuccessResponse,
    summary="Get plan limits and usage for a chatbot",
)
def get_subscription_usage(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return subscription limits and current usage for an accessible chatbot."""
    try:
        chatbot = get_owned_chatbot(db, current_user, chatbot_id)
        return service.get_chatbot_usage_overview(
            db,
            chatbot_id=chatbot.id,
            owner_user_id=chatbot.user_id,
        )
    except ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.CHATBOT_NOT_FOUND},
        )
    except ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.UNAUTHORIZED_CHATBOT_ACCESS},
        )
    except SuperAdminChatbotProtectedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.SUPERADMIN_CHATBOT_PROTECTED},
        )
