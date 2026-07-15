"""Business logic for chatbot prompt configuration APIs."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chatbot.service import ChatbotNotFoundError
from app.modules.chatbot_settings.utils import get_owned_chatbot
from app.modules.prompt.schema import (
    ChatbotPromptData,
    ChatbotPromptSuccessResponse,
    UpdateChatbotPromptRequest,
)
from app.modules.prompt.utils import (
    ALLOWED_LANGUAGES,
    ALLOWED_RESPONSE_LENGTHS,
    ALLOWED_RESPONSE_STYLES,
    ALLOWED_TONES,
    EXTRA_INSTRUCTION_MAX_LENGTH,
    SYSTEM_PROMPT_MAX_LENGTH,
    get_or_create_chatbot_prompt,
    normalize_dropdown_value,
    normalize_language,
    normalize_optional_text,
    record_to_response_data,
)

logger = logging.getLogger(__name__)


class ChatbotPromptValidationError(Exception):
    """Raised when prompt payload fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _validate_payload(payload: UpdateChatbotPromptRequest) -> dict[str, str | None]:
    try:
        language = normalize_language(payload.language)
        if language is not None and language not in ALLOWED_LANGUAGES:
            raise ValueError("Invalid language value.")

        return {
            "system_prompt": normalize_optional_text(
                payload.system_prompt,
                max_length=SYSTEM_PROMPT_MAX_LENGTH,
            ),
            "tone": normalize_dropdown_value(
                payload.tone,
                allowed=ALLOWED_TONES,
                field_label="tone",
            ),
            "response_style": normalize_dropdown_value(
                payload.response_style,
                allowed=ALLOWED_RESPONSE_STYLES,
                field_label="response style",
            ),
            "response_length": normalize_dropdown_value(
                payload.response_length,
                allowed=ALLOWED_RESPONSE_LENGTHS,
                field_label="response length",
            ),
            "language": language,
            "extra_instruction": normalize_optional_text(
                payload.extra_instruction,
                max_length=EXTRA_INSTRUCTION_MAX_LENGTH,
            ),
        }
    except ValueError as exc:
        raise ChatbotPromptValidationError(str(exc)) from exc


def get_chatbot_prompt(
    db: Session,
    user: User,
    chatbot_id: int,
) -> ChatbotPromptSuccessResponse:
    """Return prompt configuration for a chatbot."""
    get_owned_chatbot(db, user, chatbot_id)
    record = get_or_create_chatbot_prompt(db, chatbot_id)
    db.commit()

    return ChatbotPromptSuccessResponse(
        message="Chatbot prompt configuration retrieved successfully.",
        data=ChatbotPromptData(**record_to_response_data(record)),
    )


def update_chatbot_prompt(
    db: Session,
    user: User,
    chatbot_id: int,
    payload: UpdateChatbotPromptRequest,
) -> ChatbotPromptSuccessResponse:
    """Update prompt configuration. Blank values are stored as NULL."""
    get_owned_chatbot(db, user, chatbot_id)
    validated = _validate_payload(payload)
    record = get_or_create_chatbot_prompt(db, chatbot_id)

    record.system_prompt = validated["system_prompt"]
    record.tone = validated["tone"]
    record.response_style = validated["response_style"]
    record.response_length = validated["response_length"]
    record.language = validated["language"]
    record.extra_instruction = validated["extra_instruction"]

    db.commit()
    db.refresh(record)

    logger.info("Updated chatbot_prompt for chatbot_id=%s user_id=%s", chatbot_id, user.id)

    return ChatbotPromptSuccessResponse(
        message="Chatbot prompt updated successfully.",
        data=ChatbotPromptData(**record_to_response_data(record)),
    )


def reset_chatbot_prompt(
    db: Session,
    user: User,
    chatbot_id: int,
) -> ChatbotPromptSuccessResponse:
    """Reset all prompt fields to NULL so the global default prompt is used."""
    return update_chatbot_prompt(
        db,
        user,
        chatbot_id,
        UpdateChatbotPromptRequest(),
    )
