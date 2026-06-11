from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.widget import service
from app.modules.widget.schema import (
    PublicChatRequest,
    PublicChatResponse,
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
    """Receive a visitor message from the widget and return a temporary response."""
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
