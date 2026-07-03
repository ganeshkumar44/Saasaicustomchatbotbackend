from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.theme import service
from app.modules.theme.schema import (
    ThemeSuccessResponse,
    UpdateThemeRequest,
    UpdateThemeSuccessResponse,
)

router = APIRouter(
    prefix="/v1",
    tags=["Theme"],
)


@router.get(
    "/theme/color-mode",
    status_code=status.HTTP_200_OK,
    response_model=ThemeSuccessResponse,
)
def get_theme_color_mode(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's current dashboard theme."""
    return service.get_user_theme(db, current_user)


@router.put(
    "/theme/color-mode",
    status_code=status.HTTP_200_OK,
    response_model=UpdateThemeSuccessResponse,
)
def update_theme_color_mode(
    payload: UpdateThemeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the authenticated user's dashboard theme."""
    try:
        return service.update_user_theme(db, current_user, payload)
    except service.ThemeValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
