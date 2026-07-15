"""HTTP routes for chatbot prompt configuration."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.chatbot.service import (
    ChatbotNotFoundError,
    ChatbotPermissionError,
    SuperAdminChatbotProtectedError,
)
from app.modules.chatbot.utils import get_authenticated_user
from app.modules.prompt import service
from app.modules.prompt.schema import (
    ChatbotPromptSuccessResponse,
    UpdateChatbotPromptRequest,
)

router = APIRouter(
    prefix="/v1",
    tags=["Chatbot Prompt"],
)


def _access_error_response(exc: Exception) -> JSONResponse | None:
    if isinstance(exc, ChatbotNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.CHATBOT_NOT_FOUND},
        )
    if isinstance(exc, ChatbotPermissionError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.UNAUTHORIZED_CHATBOT_ACCESS},
        )
    if isinstance(exc, SuperAdminChatbotProtectedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.SUPERADMIN_CHATBOT_PROTECTED},
        )
    return None


@router.get(
    "/chatbots/{chatbot_id}/prompt",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotPromptSuccessResponse,
)
def get_chatbot_prompt(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return chatbot prompt configuration."""
    try:
        return service.get_chatbot_prompt(db, current_user, chatbot_id)
    except (ChatbotNotFoundError, ChatbotPermissionError, SuperAdminChatbotProtectedError) as exc:
        response = _access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/{chatbot_id}/prompt",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotPromptSuccessResponse,
)
def update_chatbot_prompt(
    chatbot_id: int,
    payload: UpdateChatbotPromptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update chatbot prompt configuration."""
    try:
        return service.update_chatbot_prompt(db, current_user, chatbot_id, payload)
    except service.ChatbotPromptValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, SuperAdminChatbotProtectedError) as exc:
        response = _access_error_response(exc)
        if response is not None:
            return response
        raise
