"""
Manage Chatbot module API routes.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.manage_chatbot import service
from app.modules.manage_chatbot.schema import PermanentlyDeleteChatbotSuccessResponse
from app.modules.user_details.utils import require_admin_user

router = APIRouter(
    prefix="/v1",
    tags=["Manage Chatbot"],
)


@router.delete(
    "/manage-chatbot/{chatbot_id}/permanently-delete",
    status_code=status.HTTP_200_OK,
    response_model=PermanentlyDeleteChatbotSuccessResponse,
)
def permanently_delete_manage_chatbot(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    """
    Permanently delete a chatbot and all related data (administrator only).

    SuperAdmin may delete any chatbot. Admin may delete User-owned chatbots only.
    """
    try:
        return service.permanently_delete_chatbot(db, current_user, chatbot_id)
    except service.ManageChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.CHATBOT_NOT_FOUND},
        )
    except service.ManageChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.MANAGE_CHATBOT_PERMANENT_DELETE_FORBIDDEN,
            },
        )
    except service.ManageChatbotStorageError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": exc.message},
        )
