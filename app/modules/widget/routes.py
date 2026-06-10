from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.widget import service
from app.modules.widget.schema import WidgetConfigSuccessResponse

router = APIRouter(
    prefix="/v1",
    tags=["Widget"],
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
