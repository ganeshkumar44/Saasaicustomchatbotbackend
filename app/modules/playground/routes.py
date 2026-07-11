"""
Playground API routes.

Authenticated endpoints for owner-facing chatbot testing conversations.
"""

from fastapi import APIRouter, Depends, Query, status
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
from app.modules.playground import service
from app.modules.playground.schema import (
    CreatePlaygroundSessionRequest,
    CreatePlaygroundSessionResponse,
    DeletePlaygroundSessionResponse,
    PlaygroundMessagesResponse,
    PlaygroundSessionListResponse,
)
from app.modules.playground.utils import PlaygroundSessionNotFoundError

router = APIRouter(
    prefix="/v1",
    tags=["Playground"],
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
    if isinstance(exc, PlaygroundSessionNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.PLAYGROUND_SESSION_NOT_FOUND},
        )
    return None


@router.get(
    "/playground/session",
    status_code=status.HTTP_200_OK,
    response_model=PlaygroundSessionListResponse,
    summary="List Playground sessions for a chatbot",
)
def list_playground_sessions(
    chatbot_id: int = Query(..., description="Chatbot id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all Playground sessions for a chatbot, latest first."""
    try:
        return service.get_playground_sessions(db, current_user, chatbot_id)
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
    ) as exc:
        response = _access_error_response(exc)
        if response is not None:
            return response
        raise


@router.post(
    "/playground/session",
    status_code=status.HTTP_200_OK,
    response_model=CreatePlaygroundSessionResponse,
    summary="Create a Playground session",
)
def create_playground_session(
    payload: CreatePlaygroundSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Playground conversation for a chatbot."""
    try:
        return service.create_playground_session(db, current_user, payload)
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
    ) as exc:
        response = _access_error_response(exc)
        if response is not None:
            return response
        raise


@router.get(
    "/playground/messages/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=PlaygroundMessagesResponse,
    summary="Load Playground conversation messages",
)
def get_playground_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all messages for a Playground session ordered by created_at ASC."""
    try:
        return service.get_playground_messages(db, current_user, session_id)
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        PlaygroundSessionNotFoundError,
    ) as exc:
        response = _access_error_response(exc)
        if response is not None:
            return response
        raise


@router.delete(
    "/playground/session/{id}",
    status_code=status.HTTP_200_OK,
    response_model=DeletePlaygroundSessionResponse,
    summary="Delete a Playground session",
)
def delete_playground_session(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a Playground session and all related playground messages."""
    try:
        return service.delete_playground_session(db, current_user, id)
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        PlaygroundSessionNotFoundError,
    ) as exc:
        response = _access_error_response(exc)
        if response is not None:
            return response
        raise
