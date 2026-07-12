from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.ai.exceptions import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiQuotaExceededError,
    OpenAIAPIKeyMissingError,
    OpenAIAuthenticationError,
    OpenAINetworkError,
    OpenAIProviderError,
    OpenAIRateLimitError,
    OpenAIServiceUnavailableError,
    OpenAITimeoutError,
)
from app.modules.widget import service
from app.modules.chatbot_usage.service import WebsiteMessageLimitExceededError
from app.modules.widget.schema import (
    ChatHistoryResponse,
    PublicChatRequest,
    PublicChatResponse,
    StartSessionRequest,
    StartSessionResponse,
    UpdateChatSessionStatusRequest,
    UpdateChatSessionStatusResponse,
    VisitorInfoRequest,
    VisitorInfoResponse,
    WidgetConfigSuccessResponse,
)
from app.modules.widget.utils import get_widget_js_content
from app.modules.chat_sessions.service import (
    ChatAlreadyClosedError,
    ChatSessionNotActiveError,
    ChatSessionValidationError,
)

router = APIRouter(
    prefix="/v1",
    tags=["Widget"],
)

static_router = APIRouter(tags=["Widget"])


def _chatbot_unavailable_content() -> dict:
    """Return a consistent public response when a chatbot cannot accept traffic."""
    return {
        "success": False,
        "chatbot_available": False,
        "message": messages.CHATBOT_UNAVAILABLE_PUBLIC,
    }


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
    return service.get_widget_config(db, public_key)


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
    except WebsiteMessageLimitExceededError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error_code": "WEBSITE_MESSAGE_LIMIT_REACHED",
                "message": exc.message,
            },
        )
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
    except (service.ChatbotUnavailableError, service.ChatbotNotPublishedError):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_chatbot_unavailable_content(),
        )
    except service.ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_chatbot_unavailable_content(),
        )
    except GeminiAPIKeyMissingError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Gemini API key is not configured",
            },
        )
    except GeminiQuotaExceededError:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "AI_QUOTA_EXCEEDED",
                "message": messages.AI_QUOTA_EXCEEDED,
            },
        )
    except OpenAIAPIKeyMissingError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "OpenAI API key is not configured",
            },
        )
    except OpenAIAuthenticationError as exc:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error_code": "OPENAI_AUTHENTICATION_FAILED",
                "message": exc.message,
            },
        )
    except OpenAIRateLimitError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "OPENAI_RATE_LIMIT_EXCEEDED",
                "message": exc.message,
            },
        )
    except OpenAITimeoutError as exc:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "success": False,
                "error_code": "OPENAI_REQUEST_TIMEOUT",
                "message": exc.message,
            },
        )
    except OpenAINetworkError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OPENAI_NETWORK_ERROR",
                "message": exc.message,
            },
        )
    except OpenAIServiceUnavailableError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error_code": "OPENAI_SERVICE_UNAVAILABLE",
                "message": exc.message,
            },
        )
    except OpenAIProviderError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OPENAI_PROVIDER_ERROR",
                "message": exc.message,
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


@router.put(
    "/widget/chat-session/status",
    status_code=status.HTTP_200_OK,
    response_model=UpdateChatSessionStatusResponse,
)
def update_chat_session_status(
    payload: UpdateChatSessionStatusRequest,
    db: Session = Depends(get_db),
):
    """Close a widget chat session and record mandatory visitor feedback."""
    try:
        return service.update_chat_session_status(db, payload)
    except ChatSessionValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except ChatAlreadyClosedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.CHAT_ALREADY_CLOSED},
        )
    except ChatSessionNotActiveError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.SESSION_NOT_ACTIVE},
        )
    except service.ChatSessionNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.SESSION_NOT_FOUND},
        )
    except (service.ChatbotUnavailableError, service.ChatbotNotPublishedError):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_chatbot_unavailable_content(),
        )
    except service.ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_chatbot_unavailable_content(),
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
    except (service.ChatbotUnavailableError, service.ChatbotNotPublishedError):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_chatbot_unavailable_content(),
        )
    except service.ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_chatbot_unavailable_content(),
        )
