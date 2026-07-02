from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.chat_history import service
from app.modules.chat_history.schema import (
    ChatHistoryDetailSuccessResponse,
    ChatSessionListSuccessResponse,
)
from app.modules.chat_history.utils import DEFAULT_PAGE, DEFAULT_PER_PAGE

router = APIRouter(
    prefix="/v1",
    tags=["Chat History"],
)


@router.get(
    "/chat-history/sessions",
    status_code=status.HTTP_200_OK,
    response_model=ChatSessionListSuccessResponse,
)
def get_chat_sessions(
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a paginated list of chat sessions for the chat history page."""
    return service.get_chat_sessions(
        db,
        current_user,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/chat-history/session/{chat_session_id}",
    status_code=status.HTTP_200_OK,
    response_model=ChatHistoryDetailSuccessResponse,
)
def get_chat_session_history(
    chat_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the complete conversation history for a single chat session."""
    try:
        return service.get_chat_session_history(db, current_user, chat_session_id)
    except service.ChatSessionNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.SESSION_NOT_FOUND},
        )
