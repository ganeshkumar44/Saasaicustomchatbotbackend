"""
Theme module business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.theme.schema import (
    ThemeData,
    ThemeSuccessResponse,
    UpdateThemeRequest,
    UpdateThemeSuccessResponse,
)
from app.modules.theme.utils import (
    ensure_user_theme_exists,
    normalize_theme,
    validate_theme,
)

logger = logging.getLogger(__name__)


class ThemeValidationError(Exception):
    """Raised when a theme payload fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def get_user_theme(db: Session, user: User) -> ThemeSuccessResponse:
    """Return the authenticated user's current theme preference."""
    logger.info("Fetching theme for user_id=%s", user.id)

    theme = ensure_user_theme_exists(db, user.id)

    return ThemeSuccessResponse(
        data=ThemeData(theme=theme.theme),
    )


def update_user_theme(
    db: Session,
    user: User,
    payload: UpdateThemeRequest,
) -> UpdateThemeSuccessResponse:
    """Update the authenticated user's theme preference."""
    logger.info("Theme update requested for user_id=%s", user.id)

    validation_error = validate_theme(payload.theme)
    if validation_error:
        raise ThemeValidationError(validation_error)

    theme = ensure_user_theme_exists(db, user.id)
    normalized_theme = normalize_theme(payload.theme)
    theme.theme = normalized_theme
    theme.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(theme)

    logger.info(
        "Theme updated successfully for user_id=%s theme=%s",
        user.id,
        theme.theme,
    )

    return UpdateThemeSuccessResponse(
        message=messages.THEME_UPDATED_SUCCESS,
        data=ThemeData(theme=theme.theme),
    )
