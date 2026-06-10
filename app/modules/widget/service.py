"""
Widget module business logic.
"""

from sqlalchemy.orm import Session

from app.modules.widget.schema import WidgetConfigSuccessResponse
from app.modules.widget.utils import (
    build_widget_config_response,
    get_chatbot_settings_by_public_key,
)


class WidgetConfigNotFoundError(Exception):
    """Raised when no chatbot settings exist for the given public key."""


def get_widget_config(db: Session, public_key: str) -> WidgetConfigSuccessResponse:
    """Return public widget configuration for the given public key."""
    settings = get_chatbot_settings_by_public_key(db, public_key)
    if settings is None:
        raise WidgetConfigNotFoundError

    return WidgetConfigSuccessResponse(
        data=build_widget_config_response(settings),
    )
