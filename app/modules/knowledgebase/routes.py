from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError
from app.modules.chatbot.utils import get_authenticated_user
from app.modules.knowledgebase import service
from app.modules.knowledgebase.schema import KnowledgebaseUploadSuccessResponse
from app.modules.knowledgebase.service import UploadedFilePayload

router = APIRouter(
    prefix="/v1",
    tags=["Knowledge Base"],
)


@router.post(
    "/chatbots/{chatbot_id}/knowledgebase/upload",
    status_code=status.HTTP_201_CREATED,
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
    files: Annotated[
        list[UploadFile] | None,
        File(description="Knowledge base files (PDF, DOC, DOCX, TXT, CSV, MD)"),
    ] = None,
    urls: Annotated[list[str], Form(description="Website URLs to scrape")] = [],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Upload knowledge base files and website URLs for a chatbot."""
    file_payloads: list[UploadedFilePayload] = []
    for upload_file in files or []:
        if not upload_file.filename:
            continue
        content = await upload_file.read()
        if not content:
            continue
        file_payloads.append(
            UploadedFilePayload(
                filename=upload_file.filename,
                content=content,
            )
        )

    try:
        return service.upload_knowledgebase(
            db,
            current_user,
            chatbot_id,
            file_payloads,
            urls,
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
                "message": "Chatbot not found",
            },
        )
    except ChatbotPermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": "You do not have permission to access this chatbot",
            },
        )
