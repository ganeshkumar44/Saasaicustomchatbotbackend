from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
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
from app.modules.knowledgebase.exceptions import KnowledgeBaseStorageError
from app.modules.knowledgebase import service
from app.modules.knowledgebase.form_parser import parse_knowledgebase_multipart_form
from app.modules.knowledgebase.schema import (
    KnowledgebaseProcessingStatusResponse,
    KnowledgebaseUploadSuccessResponse,
)

router = APIRouter(
    prefix="/v1",
    tags=["Knowledge Base"],
)


@router.post(
    "/chatbots/{chatbot_id}/knowledgebase/upload",
    status_code=status.HTTP_200_OK,
    response_model=KnowledgebaseUploadSuccessResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "binary",
                                },
                                "description": (
                                    "Knowledge base files (PDF, DOC, DOCX, TXT, CSV, MD)"
                                ),
                            },
                            "urls": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Website URLs to scrape",
                            },
                        },
                    },
                },
            },
        },
    },
)
async def upload_knowledgebase(
    chatbot_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Upload knowledge base files and website URLs for a chatbot."""
    file_payloads, urls = await parse_knowledgebase_multipart_form(request)

    try:
        return await service.upload_knowledgebase(
            db,
            current_user,
            chatbot_id,
            file_payloads,
            urls,
            background_tasks,
        )
    except service.UnsupportedFileTypeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Unsupported file type",
            },
        )
    except service.FileSizeExceededError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Maximum upload size is 50 MB",
            },
        )
    except service.KnowledgeBaseFileSizeExceededError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except KnowledgeBaseStorageError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.NoKnowledgeSourcesError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "At least one file or URL is required",
            },
        )
    except ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.CHATBOT_NOT_FOUND,
            },
        )
    except ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.UNAUTHORIZED_CHATBOT_ACCESS,
            },
        )
    except SuperAdminChatbotProtectedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.SUPERADMIN_CHATBOT_PROTECTED,
            },
        )


@router.get(
    "/chatbots/{chatbot_id}/knowledgebase/status",
    status_code=status.HTTP_200_OK,
    response_model=KnowledgebaseProcessingStatusResponse,
)
def get_knowledgebase_status(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return aggregate knowledge base processing status for a chatbot."""
    try:
        return service.get_knowledgebase_processing_status(db, current_user, chatbot_id)
    except ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.CHATBOT_NOT_FOUND,
            },
        )
    except ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.UNAUTHORIZED_CHATBOT_ACCESS,
            },
        )
    except SuperAdminChatbotProtectedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.SUPERADMIN_CHATBOT_PROTECTED,
            },
        )
