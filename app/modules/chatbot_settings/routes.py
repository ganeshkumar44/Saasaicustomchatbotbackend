from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError, InvalidAIModelError
from app.modules.chatbot.utils import get_authenticated_user
from app.modules.chatbot_settings import service
from app.modules.chatbot_settings.schema import (
    ActivateChatbotSuccessResponse,
    ChatbotDetailsSuccessResponse,
    DeleteChatbotSuccessResponse,
    SettingsUpdateSuccessResponse,
    SwaggerUploadFile,
    UpdateAppearanceSettingsRequest,
    UpdateGeneralSettingsRequest,
    UpdateMessagesSettingsRequest,
    UpdateSecuritySettingsRequest,
)
from app.modules.chatbot_settings.utils import ChatbotSettingsNotFoundError
from app.modules.knowledgebase.service import (
    FileSizeExceededError,
    UnsupportedFileTypeError,
    UploadedFilePayload,
)

router = APIRouter(
    prefix="/v1",
    tags=["Chatbot Settings"],
)


def _chatbot_access_error_response(exc: Exception) -> JSONResponse | None:
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
    if isinstance(exc, ChatbotSettingsNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.CHATBOT_SETTINGS_NOT_FOUND},
        )
    return None


@router.get(
    "/chatbots/{chatbot_id}/details",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotDetailsSuccessResponse,
)
def get_chatbot_details(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return complete chatbot configuration for the settings page."""
    try:
        return service.get_chatbot_details(db, current_user, chatbot_id)
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/general-setting",
    status_code=status.HTTP_200_OK,
    response_model=SettingsUpdateSuccessResponse,
)
def update_general_settings(
    payload: UpdateGeneralSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update general chatbot information."""
    try:
        return service.update_general_settings(db, current_user, payload)
    except service.ChatbotSettingsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/appearance",
    status_code=status.HTTP_200_OK,
    response_model=SettingsUpdateSuccessResponse,
)
def update_appearance_settings(
    payload: UpdateAppearanceSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update widget appearance settings."""
    try:
        return service.update_appearance_settings(db, current_user, payload)
    except service.ChatbotSettingsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/messages",
    status_code=status.HTTP_200_OK,
    response_model=SettingsUpdateSuccessResponse,
)
def update_messages_settings(
    payload: UpdateMessagesSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update chatbot message settings."""
    try:
        return service.update_messages_settings(db, current_user, payload)
    except service.ChatbotSettingsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/security",
    status_code=status.HTTP_200_OK,
    response_model=SettingsUpdateSuccessResponse,
)
def update_security_settings(
    payload: UpdateSecuritySettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update chatbot security settings."""
    try:
        return service.update_security_settings(db, current_user, payload)
    except InvalidAIModelError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.INVALID_AI_MODEL},
        )
    except service.ChatbotSettingsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/knowledge-base",
    status_code=status.HTTP_200_OK,
    response_model=SettingsUpdateSuccessResponse,
)
async def update_knowledge_base(
    chatbot_id: Annotated[int, Form(description="Chatbot ID")],
    delete_document_ids: Annotated[
        list[int],
        Form(description="Delete Document IDs (optional)"),
    ] = [],
    files: Annotated[
        list[SwaggerUploadFile] | None,
        File(
            description=(
                "Choose Files — PDF, DOC, DOCX, TXT, CSV, MD (multiple allowed)"
            ),
        ),
    ] = None,
    urls: Annotated[
        list[str],
        Form(description="New URLs (optional)"),
    ] = [],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update chatbot knowledge base by deleting old sources and uploading new ones."""
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
        return service.update_knowledge_base(
            db,
            current_user,
            chatbot_id,
            delete_document_ids,
            file_payloads,
            urls,
        )
    except service.KnowledgeBaseRequiredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.KNOWLEDGE_BASE_REQUIRED},
        )
    except service.ChatbotSettingsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except UnsupportedFileTypeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Unsupported file type"},
        )
    except FileSizeExceededError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Maximum upload size is 50 MB"},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.delete(
    "/chatbots/{chatbot_id}/delete",
    status_code=status.HTTP_200_OK,
    response_model=DeleteChatbotSuccessResponse,
)
def delete_chatbot(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Soft-delete a chatbot and disable all public widget access."""
    try:
        return service.delete_chatbot(db, current_user, chatbot_id)
    except service.ChatbotAlreadyDeletedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.CHATBOT_ALREADY_DELETED},
        )
    except (ChatbotNotFoundError, ChatbotPermissionError, ChatbotSettingsNotFoundError) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.put(
    "/chatbots/{chatbot_id}/activate",
    status_code=status.HTTP_200_OK,
    response_model=ActivateChatbotSuccessResponse,
)
def activate_chatbot(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Restore a soft-deleted chatbot (admin only)."""
    try:
        return service.activate_chatbot(db, current_user, chatbot_id)
    except service.ChatbotAlreadyActiveError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.CHATBOT_ALREADY_ACTIVE},
        )
    except service.ChatbotActivatePermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.UNAUTHORIZED_ACTION},
        )
    except ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.CHATBOT_NOT_FOUND},
        )
