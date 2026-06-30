"""
Widget module business logic.
"""

import logging

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.ai.service import generate_ai_answer
from app.modules.chatbot.model import CHATBOT_STATUS_PUBLISHED, Chatbot
from app.modules.chat_messages.schema import CreateChatMessageRequest
from app.modules.chat_messages.service import create_message
from app.modules.chat_messages.utils import get_messages_by_session_id
from app.modules.chat_sessions.model import (
    VISITOR_STEP_COMPLETED,
    VISITOR_STEP_EMAIL,
    VISITOR_STEP_NAME,
    VISITOR_STEP_PHONE,
)
from app.modules.chat_sessions.service import (
    create_chat_session,
    update_last_activity,
    update_visitor_onboarding,
)
from app.modules.chat_sessions.utils import get_chat_session_by_session_id
from app.modules.widget.schema import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    PublicChatRequest,
    PublicChatResponse,
    StartSessionRequest,
    StartSessionResponse,
    VisitorInfoRequest,
    VisitorInfoResponse,
    WidgetConfigSuccessResponse,
)
from app.modules.auth.utils import normalize_email
from app.modules.widget.utils import (
    build_onboarding_state,
    build_widget_config_response,
    get_chatbot_settings_by_public_key,
    is_onboarding_complete,
    validate_visitor_email,
    validate_visitor_name,
    validate_visitor_phone,
)

logger = logging.getLogger(__name__)


class WidgetConfigNotFoundError(Exception):
    """Raised when no chatbot settings exist for the given public key."""


class ChatbotNotFoundError(Exception):
    """Raised when no chatbot exists for the given public key."""


class ChatbotNotPublishedError(Exception):
    """Raised when the chatbot is not in published status."""


class MessageRequiredError(Exception):
    """Raised when the chat message is missing or empty."""


class SessionRequiredError(Exception):
    """Raised when the chat session identifier is missing or empty."""


class ChatSessionNotFoundError(Exception):
    """Raised when the chat session does not exist or does not match the chatbot."""


class ChatMessageSaveError(Exception):
    """Raised when saving a chat message to the database fails."""


class OnboardingIncompleteError(Exception):
    """Raised when chat is attempted before visitor onboarding is complete."""


class VisitorOnboardingValidationError(Exception):
    """Raised when visitor onboarding input fails validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidVisitorStepError(Exception):
    """Raised when the submitted onboarding step does not match the session."""


def get_widget_config(db: Session, public_key: str) -> WidgetConfigSuccessResponse:
    """Return public widget configuration for the given public key."""
    settings = get_chatbot_settings_by_public_key(db, public_key)
    if settings is None:
        raise WidgetConfigNotFoundError

    return WidgetConfigSuccessResponse(
        data=build_widget_config_response(settings),
    )


def _build_visitor_info_response(session_step: str) -> VisitorInfoResponse:
    """Build a visitor onboarding response for the given session step."""
    onboarding = build_onboarding_state(session_step)
    complete = bool(onboarding["onboarding_complete"])
    return VisitorInfoResponse(
        next_step=str(onboarding["visitor_step"]),
        question=onboarding["question"],  # type: ignore[arg-type]
        can_skip=bool(onboarding["can_skip"]),
        onboarding_complete=complete,
        message=messages.THANK_YOU_START_CHAT if complete else None,
    )


def process_visitor_info(
    db: Session,
    payload: VisitorInfoRequest,
) -> VisitorInfoResponse:
    """Save visitor onboarding details and advance the session step."""
    if not payload.session_id or not payload.session_id.strip():
        raise ChatSessionNotFoundError()

    session = get_chat_session_by_session_id(db, payload.session_id.strip())
    if session is None:
        raise ChatSessionNotFoundError()

    if is_onboarding_complete(session.visitor_step):
        return _build_visitor_info_response(VISITOR_STEP_COMPLETED)

    submitted_step = payload.step.strip().lower() if payload.step else ""
    if submitted_step != session.visitor_step:
        raise InvalidVisitorStepError()

    if session.visitor_step == VISITOR_STEP_NAME:
        if payload.skip:
            raise VisitorOnboardingValidationError(messages.VISITOR_NAME_REQUIRED)

        error = validate_visitor_name(payload.value)
        if error:
            raise VisitorOnboardingValidationError(error)

        update_visitor_onboarding(
            db,
            session,
            visitor_id=payload.value.strip(),  # type: ignore[union-attr]
            visitor_step=VISITOR_STEP_EMAIL,
        )
        return _build_visitor_info_response(VISITOR_STEP_EMAIL)

    if session.visitor_step == VISITOR_STEP_EMAIL:
        if payload.skip:
            update_visitor_onboarding(
                db,
                session,
                visitor_email=None,
                visitor_step=VISITOR_STEP_PHONE,
            )
            return _build_visitor_info_response(VISITOR_STEP_PHONE)

        error = validate_visitor_email(payload.value)
        if error:
            raise VisitorOnboardingValidationError(error)

        update_visitor_onboarding(
            db,
            session,
            visitor_email=normalize_email(payload.value),  # type: ignore[arg-type]
            visitor_step=VISITOR_STEP_PHONE,
        )
        return _build_visitor_info_response(VISITOR_STEP_PHONE)

    if session.visitor_step == VISITOR_STEP_PHONE:
        if payload.skip:
            update_visitor_onboarding(
                db,
                session,
                visitor_phone=None,
                visitor_step=VISITOR_STEP_COMPLETED,
            )
            return _build_visitor_info_response(VISITOR_STEP_COMPLETED)

        error = validate_visitor_phone(payload.value)
        if error:
            raise VisitorOnboardingValidationError(error)

        update_visitor_onboarding(
            db,
            session,
            visitor_phone=payload.value.strip(),  # type: ignore[union-attr]
            visitor_step=VISITOR_STEP_COMPLETED,
        )
        return _build_visitor_info_response(VISITOR_STEP_COMPLETED)

    raise InvalidVisitorStepError()


def process_public_chat(
    db: Session,
    payload: PublicChatRequest,
) -> PublicChatResponse:
    """Accept a visitor message, generate an AI answer, and save the conversation."""
    if not payload.public_key or not payload.public_key.strip():
        raise ChatbotNotFoundError()

    if not payload.message or not payload.message.strip():
        raise MessageRequiredError()

    public_key = payload.public_key.strip()
    user_message = payload.message.strip()
    session_id = payload.session_id.strip() if payload.session_id else ""

    logger.info("Widget chat request received for public_key=%s", public_key)

    settings = get_chatbot_settings_by_public_key(db, public_key)
    if settings is None:
        logger.warning("Chatbot settings not found for public_key=%s", public_key)
        raise ChatbotNotFoundError()

    chatbot = db.get(Chatbot, settings.chatbot_id)
    if chatbot is None or chatbot.status != CHATBOT_STATUS_PUBLISHED:
        logger.warning(
            "Chatbot unavailable or unpublished for public_key=%s chatbot_id=%s",
            public_key,
            settings.chatbot_id,
        )
        raise ChatbotNotPublishedError()

    logger.info("Chatbot resolved for public_key=%s chatbot_id=%s", public_key, chatbot.id)

    if not session_id:
        raise SessionRequiredError()

    session = get_chat_session_by_session_id(db, session_id)
    if session is None or session.chatbot_id != chatbot.id:
        logger.warning(
            "Chat session not found or mismatched for session_id=%s chatbot_id=%s",
            session_id,
            chatbot.id,
        )
        raise ChatSessionNotFoundError()

    if not is_onboarding_complete(session.visitor_step):
        logger.warning(
            "Chat blocked until onboarding completes session_id=%s step=%s",
            session.session_id,
            session.visitor_step,
        )
        raise OnboardingIncompleteError()

    logger.info(
        "Session resolved for session_id=%s chatbot_id=%s",
        session.session_id,
        chatbot.id,
    )

    ai_response = generate_ai_answer(db, chatbot.id, user_message)
    answer = ai_response.answer

    logger.info(
        "AI answer generated for chatbot_id=%s session_id=%s answer_length=%s",
        chatbot.id,
        session.session_id,
        len(answer),
    )

    try:
        create_message(
            db,
            CreateChatMessageRequest(
                session_id=session.id,
                user_message=user_message,
                bot_response=answer,
            ),
        )
        update_last_activity(db, session.session_id)
    except Exception as exc:
        logger.exception(
            "Failed to save chat message for session_id=%s chatbot_id=%s",
            session.session_id,
            chatbot.id,
        )
        raise ChatMessageSaveError() from exc

    logger.info(
        "Chat message saved for session_id=%s chatbot_id=%s",
        session.session_id,
        chatbot.id,
    )

    return PublicChatResponse(answer=answer)


def start_chat_session(
    db: Session,
    payload: StartSessionRequest,
) -> StartSessionResponse:
    """Create a new chat session for a published chatbot visitor."""
    if not payload.public_key or not payload.public_key.strip():
        raise ChatbotNotFoundError()

    settings = get_chatbot_settings_by_public_key(db, payload.public_key.strip())
    if settings is None:
        raise ChatbotNotFoundError()

    chatbot = db.get(Chatbot, settings.chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    if chatbot.status != CHATBOT_STATUS_PUBLISHED:
        raise ChatbotNotPublishedError()

    session = create_chat_session(db, chatbot.id)
    return StartSessionResponse(session_id=session.session_id)


def get_chat_history(db: Session, session_id: str) -> ChatHistoryResponse:
    """Return chat history and visitor onboarding state for a session."""
    if not session_id or not session_id.strip():
        raise ChatSessionNotFoundError()

    session = get_chat_session_by_session_id(db, session_id.strip())
    if session is None:
        raise ChatSessionNotFoundError()

    messages_list = get_messages_by_session_id(db, session.id)
    onboarding = build_onboarding_state(session.visitor_step)

    return ChatHistoryResponse(
        session_id=session.session_id,
        messages=[
            ChatHistoryMessage(
                user_message=message.user_message,
                bot_response=message.bot_response,
                created_at=message.created_at,
            )
            for message in messages_list
        ],
        visitor_step=str(onboarding["visitor_step"]),
        question=onboarding["question"],  # type: ignore[arg-type]
        can_skip=bool(onboarding["can_skip"]),
        onboarding_complete=bool(onboarding["onboarding_complete"]),
    )
