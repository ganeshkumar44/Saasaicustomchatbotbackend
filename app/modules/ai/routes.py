"""
Temporary AI development endpoints.

These routes are for internal testing only and will be replaced or removed
when AI answer generation is integrated into the public widget chat flow.

When ``session_id`` is provided, the request is treated as a Playground turn:
the shared AI pipeline is reused and messages are stored in playground_*.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.security import (
    InvalidTokenError,
    TokenBlacklistedError,
    TokenExpiredError,
    decode_access_token,
)
from app.modules.ai import service
from app.modules.ai.schema import AITestAnswerRequest, AITestAnswerResponse
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
from app.modules.auth.model import User
from app.modules.chatbot.service import (
    ChatbotNotFoundError,
    ChatbotPermissionError,
    SuperAdminChatbotProtectedError,
)
from app.modules.playground import service as playground_service
from app.modules.playground.utils import (
    PlaygroundSessionMismatchError,
    PlaygroundSessionNotFoundError,
)
from app.modules.chatbot_usage.service import PlaygroundMessageLimitExceededError
from app.rag import rag_service
from app.rag.search_service import QueryRequiredError

router = APIRouter(
    prefix="/v1",
    tags=["AI (Temporary Test)"],
)

_optional_bearer = HTTPBearer(auto_error=False)


def _resolve_optional_user(
    db: Session,
    credentials: HTTPAuthorizationCredentials | None,
) -> User | None:
    """Return the authenticated user when a Bearer token is present."""
    if credentials is None or not credentials.credentials.strip():
        return None

    token = credentials.credentials.strip()
    try:
        payload = decode_access_token(token, db=db)
        user = db.get(User, payload["user_id"])
    except (TokenExpiredError, TokenBlacklistedError, InvalidTokenError, KeyError, TypeError):
        return None

    if not user or not user.is_active:
        return None
    return user


def _ai_error_response(exc: Exception) -> JSONResponse | None:
    if isinstance(exc, (service.QuestionRequiredError, QueryRequiredError)):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Question is required"},
        )
    if isinstance(exc, (rag_service.ChatbotNotFoundError, service.ChatbotNotFoundError, ChatbotNotFoundError)):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Chatbot not found"},
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
    if isinstance(exc, PlaygroundSessionNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.PLAYGROUND_SESSION_NOT_FOUND},
        )
    if isinstance(exc, PlaygroundSessionMismatchError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.PLAYGROUND_SESSION_CHATBOT_MISMATCH},
        )
    if isinstance(exc, PlaygroundMessageLimitExceededError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error_code": "PLAYGROUND_MESSAGE_LIMIT_REACHED",
                "message": exc.message,
            },
        )
    if isinstance(exc, GeminiAPIKeyMissingError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Gemini API key is not configured"},
        )
    if isinstance(exc, GeminiQuotaExceededError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "AI_QUOTA_EXCEEDED",
                "message": messages.AI_QUOTA_EXCEEDED,
            },
        )
    if isinstance(exc, OpenAIAPIKeyMissingError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "OpenAI API key is not configured"},
        )
    if isinstance(exc, OpenAIAuthenticationError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error_code": "OPENAI_AUTHENTICATION_FAILED",
                "message": exc.message,
            },
        )
    if isinstance(exc, OpenAIRateLimitError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "OPENAI_RATE_LIMIT_EXCEEDED",
                "message": exc.message,
            },
        )
    if isinstance(exc, OpenAITimeoutError):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "success": False,
                "error_code": "OPENAI_REQUEST_TIMEOUT",
                "message": exc.message,
            },
        )
    if isinstance(exc, OpenAINetworkError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OPENAI_NETWORK_ERROR",
                "message": exc.message,
            },
        )
    if isinstance(exc, OpenAIServiceUnavailableError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error_code": "OPENAI_SERVICE_UNAVAILABLE",
                "message": exc.message,
            },
        )
    if isinstance(exc, OpenAIProviderError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OPENAI_PROVIDER_ERROR",
                "message": exc.message,
            },
        )
    if isinstance(exc, GeminiAPIError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"success": False, "message": "Failed to generate AI answer"},
        )
    return None


@router.post(
    "/ai/test-answer",
    status_code=status.HTTP_200_OK,
    response_model=AITestAnswerResponse,
    summary="Temporary AI answer test endpoint",
    description=(
        "Development endpoint for testing the full RAG + AI pipeline. "
        "When session_id is provided (Playground), requires authentication and "
        "persists the turn to playground_messages using the same AI pipeline "
        "as the website widget."
    ),
)
def test_ai_answer(
    payload: AITestAnswerRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
):
    """Generate an AI answer from knowledge base context and the selected provider."""
    try:
        if payload.session_id is not None:
            user = _resolve_optional_user(db, credentials)
            if user is None:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "success": False,
                        "message": messages.TOKEN_REQUIRED,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return playground_service.generate_playground_answer(
                db,
                user,
                chatbot_id=payload.chatbot_id,
                question=payload.question,
                session_id=payload.session_id,
            )

        return service.generate_ai_answer(
            db,
            payload.chatbot_id,
            payload.question,
        )
    except Exception as exc:
        response = _ai_error_response(exc)
        if response is not None:
            return response
        raise
