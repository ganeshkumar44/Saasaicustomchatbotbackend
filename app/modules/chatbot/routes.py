from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.chatbot import service
from app.modules.chatbot.schema import (
    CreateChatbotDraftSuccessResponse,
    UpdateBasicInfoRequest,
    UpdateBasicInfoSuccessResponse,
    UpdateBehaviourRequest,
    UpdateBehaviourSuccessResponse,
)
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


@router.put(
    "/chatbots/{chatbot_id}/basic-info",
    status_code=status.HTTP_200_OK,
    response_model=UpdateBasicInfoSuccessResponse,
)
def update_basic_info(
    chatbot_id: int,
    payload: UpdateBasicInfoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update Step 1 basic information for an existing chatbot draft."""
    try:
        return service.update_basic_info(db, current_user, chatbot_id, payload)
    except service.ChatbotNameRequiredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Chatbot name is required",
            },
        )
    except service.ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Chatbot not found",
            },
        )
    except service.ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": "You do not have permission to update this chatbot",
            },
        )


@router.put(
    "/chatbots/{chatbot_id}/behaviour",
    status_code=status.HTTP_200_OK,
    response_model=UpdateBehaviourSuccessResponse,
)
def update_behaviour(
    chatbot_id: int,
    payload: UpdateBehaviourRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update Step 2 behaviour settings for an existing chatbot draft."""
    try:
        return service.update_behaviour(db, current_user, chatbot_id, payload)
    except service.InvalidPersonalityError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Invalid personality value",
            },
        )
    except service.InvalidAIModelError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Invalid AI model",
            },
        )
    except service.InvalidLanguageError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Invalid language",
            },
        )
    except service.ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Chatbot not found",
            },
        )
    except service.ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": "You do not have permission to update this chatbot",
            },
        )
