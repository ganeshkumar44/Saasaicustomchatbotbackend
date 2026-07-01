from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.chat_sessions import service
from app.modules.chat_sessions.schema import UpdateChatSessionStatusRequest, UpdateChatSessionStatusResponse

router = APIRouter(
    prefix="/v1",
    tags=["Chat Sessions"],
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
    """Update chat session lifecycle status for close and visitor feedback."""
    try:
        return service.update_chat_session_status(db, payload)
    except service.ChatSessionValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except service.ChatAlreadyClosedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.CHAT_ALREADY_CLOSED},
        )
    except service.ChatSessionNotClosedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.CHAT_SESSION_NOT_CLOSED},
        )
    except service.ChatSessionNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.SESSION_NOT_FOUND},
        )
