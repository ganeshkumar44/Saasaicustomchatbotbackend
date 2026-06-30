"""
Widget module helper utilities.
"""

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages
from app.core.config import get_settings
from app.modules.auth.utils import normalize_email, validate_email, validate_mobile
from app.modules.chat_sessions.model import (
    VISITOR_STEP_COMPLETED,
    VISITOR_STEP_EMAIL,
    VISITOR_STEP_NAME,
    VISITOR_STEP_PHONE,
)
from app.modules.chatbot.model import ChatbotSettings
from app.modules.widget.schema import WidgetConfigResponse

WIDGET_JS_PLACEHOLDER = "__WIDGET_API_BASE_URL__"
WIDGET_JS_PATH = Path(__file__).resolve().parents[3] / "static" / "widget.js"

VISITOR_NAME_MIN_LENGTH = 2
VISITOR_NAME_MAX_LENGTH = 100
_VISITOR_NAME_PATTERN = re.compile(r"^[A-Za-z ]+$")


def get_widget_js_content() -> str:
    """Return widget.js with the API base URL injected from application settings."""
    template = WIDGET_JS_PATH.read_text(encoding="utf-8")
    api_base_url = get_settings().WIDGET_BASE_URL.rstrip("/")
    return template.replace(WIDGET_JS_PLACEHOLDER, api_base_url)


def get_chatbot_settings_by_public_key(
    db: Session,
    public_key: str,
) -> ChatbotSettings | None:
    """Return chatbot settings for a published widget public key."""
    return db.execute(
        select(ChatbotSettings).where(ChatbotSettings.public_key == public_key)
    ).scalar_one_or_none()


def build_widget_config_response(settings: ChatbotSettings) -> WidgetConfigResponse:
    """Map chatbot settings to the public widget configuration response."""
    return WidgetConfigResponse(
        chat_title=settings.chat_title,
        welcome_message=settings.welcome_message,
        primary_color=settings.primary_color,
        text_color=settings.text_color,
        show_avatar=settings.show_avatar,
        typing_indicator=settings.typing_indicator,
        widget_position=settings.widget_position,
        allowed_domains=settings.allowed_domains,
    )


def validate_visitor_name(value: str | None) -> str | None:
    """
    Validate a visitor display name (alphabets and spaces, 2-100 characters).

    Returns an error message or None when valid.
    """
    if value is None or not value.strip():
        return messages.VISITOR_NAME_REQUIRED

    trimmed = value.strip()
    if len(trimmed) < VISITOR_NAME_MIN_LENGTH:
        return messages.VISITOR_NAME_TOO_SHORT
    if len(trimmed) > VISITOR_NAME_MAX_LENGTH:
        return messages.VISITOR_NAME_TOO_LONG
    if not _VISITOR_NAME_PATTERN.fullmatch(trimmed):
        return messages.INVALID_VISITOR_NAME

    return None


def validate_visitor_email(value: str | None) -> str | None:
    """Validate an optional visitor email when the visitor chooses to provide one."""
    if value is None or not value.strip():
        return messages.PLEASE_ENTER_EMAIL
    return validate_email(value)


def validate_visitor_phone(value: str | None) -> str | None:
    """Validate an optional visitor phone when the visitor chooses to provide one."""
    if value is None or not value.strip():
        return messages.PLEASE_ENTER_PHONE
    return validate_mobile(value)


def get_visitor_step_question(step: str) -> str | None:
    """Return the onboarding prompt for the given step."""
    if step == VISITOR_STEP_NAME:
        return messages.VISITOR_NAME_QUESTION
    if step == VISITOR_STEP_EMAIL:
        return messages.VISITOR_EMAIL_QUESTION
    if step == VISITOR_STEP_PHONE:
        return messages.VISITOR_PHONE_QUESTION
    return None


def can_skip_visitor_step(step: str) -> bool:
    """Return True when the visitor may skip the current onboarding step."""
    return step in (VISITOR_STEP_EMAIL, VISITOR_STEP_PHONE)


def is_onboarding_complete(step: str) -> bool:
    """Return True when visitor onboarding has finished for the session."""
    return step == VISITOR_STEP_COMPLETED


def build_onboarding_state(visitor_step: str) -> dict[str, str | bool | None]:
    """Build onboarding metadata exposed to the widget client."""
    complete = is_onboarding_complete(visitor_step)
    return {
        "visitor_step": visitor_step,
        "question": None if complete else get_visitor_step_question(visitor_step),
        "can_skip": can_skip_visitor_step(visitor_step),
        "onboarding_complete": complete,
    }
