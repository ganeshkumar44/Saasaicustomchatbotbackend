from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.notification import service
from app.modules.notification.schema import (
    NotificationSettingsSuccessResponse,
    UpdateNotificationSettingsRequest,
    UpdateNotificationSettingsSuccessResponse,
)

router = APIRouter(
    prefix="/v1",
    tags=["Notification"],
)


@router.get(
    "/notification/settings",
    status_code=status.HTTP_200_OK,
    response_model=NotificationSettingsSuccessResponse,
)
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's notification preferences."""
    return service.get_notification_settings(db, current_user)


@router.put(
    "/notification/settings",
    status_code=status.HTTP_200_OK,
    response_model=UpdateNotificationSettingsSuccessResponse,
)
def update_notification_settings(
    payload: UpdateNotificationSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the authenticated user's notification preferences."""
    return service.update_notification_settings(db, current_user, payload)
