from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.ai.utils import GeminiAPIError, GeminiAPIKeyMissingError
from app.modules.widget import service
from app.modules.widget.schema import (
    ChatHistoryResponse,
    PublicChatRequest,
    PublicChatResponse,
    StartSessionRequest,
    StartSessionResponse,
    VisitorInfoRequest,
    VisitorInfoResponse,
    WidgetConfigSuccessResponse,
)
from app.modules.widget.utils import get_widget_js_content

router = APIRouter(
    prefix="/v1",
    tags=["Widget"],
)

static_router = APIRouter(tags=["Widget"])


@static_router.get("/static/widget.js", include_in_schema=False)
def serve_widget_js() -> Response:
    """Serve widget.js with the API base URL from application settings."""
    return Response(
        content=get_widget_js_content(),
        media_type="application/javascript",
    )


@router.get(
    "/widget/config/{public_key}",
    status_code=status.HTTP_200_OK,
    response_model=WidgetConfigSuccessResponse,
)
def get_widget_config(
    public_key: str,
    db: Session = Depends(get_db),
):
    """Return public widget configuration for an embedded chatbot."""
    try:
        return service.get_widget_config(db, public_key)
    except service.WidgetConfigNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Widget configuration not found",
            },
        )


@router.post(
    "/widget/chat",
    status_code=status.HTTP_200_OK,
    response_model=PublicChatResponse,
)
def public_chat(
    payload: PublicChatRequest,
    db: Session = Depends(get_db),
):
    """Receive a visitor message from the widget and return an AI-generated answer."""
    try:
        return service.process_public_chat(db, payload)
    except service.MessageRequiredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Message is required",
            },
        )
    except service.SessionRequiredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Session is required",
            },
        )
    except service.ChatSessionNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Chat session not found",
            },
        )
    except service.ChatbotNotPublishedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Chatbot is not published",
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
    except GeminiAPIKeyMissingError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Gemini API key is not configured",
            },
        )
    except GeminiAPIError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "message": "Failed to generate AI answer",
            },
        )
    except service.ChatMessageSaveError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Failed to save chat message",
            },
        )
    except service.OnboardingIncompleteError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.ONBOARDING_INCOMPLETE,
            },
        )


@router.post(
    "/widget/visitor-info",
    status_code=status.HTTP_200_OK,
    response_model=VisitorInfoResponse,
)
def submit_visitor_info(
    payload: VisitorInfoRequest,
    db: Session = Depends(get_db),
):
    """Save visitor onboarding details and return the next onboarding step."""
    try:
        return service.process_visitor_info(db, payload)
    except service.VisitorOnboardingValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.InvalidVisitorStepError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.INVALID_VISITOR_STEP,
            },
        )
    except service.ChatSessionNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Session not found",
            },
        )


@router.get(
    "/widget/chat-history/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=ChatHistoryResponse,
)
def get_chat_history(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Return conversation history for an existing widget chat session."""
    try:
        return service.get_chat_history(db, session_id)
    except service.ChatSessionNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Session not found",
            },
        )


@router.post(
    "/widget/session/start",
    status_code=status.HTTP_200_OK,
    response_model=StartSessionResponse,
)
def start_chat_session(
    payload: StartSessionRequest,
    db: Session = Depends(get_db),
):
    """Create a new chat session when the widget loads for the first time."""
    try:
        return service.start_chat_session(db, payload)
    except service.ChatbotNotPublishedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Chatbot is not published",
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
