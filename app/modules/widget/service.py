"""
Widget module business logic.
"""

import logging
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.ai.service import generate_ai_answer
from app.modules.chatbot.model import Chatbot
from app.modules.chatbot.utils import is_chatbot_widget_available
from app.modules.chat_messages.schema import CreateChatMessageRequest
from app.modules.chat_messages.service import create_message
from app.modules.chat_messages.utils import get_messages_by_session_id
from app.modules.chat_sessions.model import (
    VISITOR_STEP_COMPLETED,
    VISITOR_STEP_EMAIL,
    VISITOR_STEP_NAME,
    VISITOR_STEP_PHONE,
)
from app.modules.chat_sessions.schema import (
    UpdateChatSessionStatusRequest as ChatSessionStatusRequest,
    UpdateChatSessionStatusResponse,
)
from app.modules.chat_analysis.service import (
    record_chat_exchange,
    record_new_chat_session,
    record_new_visitor,
)
from app.modules.chat_sessions.service import (
    ChatAlreadyClosedError,
    ChatSessionNotActiveError,
    ChatSessionNotFoundError as ChatSessionServiceNotFoundError,
    ChatSessionValidationError,
    create_chat_session,
    update_chat_session_status as update_chat_session_status_record,
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
    UpdateChatSessionStatusRequest,
    UpdateChatSessionStatusResponse,
    VisitorInfoRequest,
    VisitorInfoResponse,
    WidgetConfigSuccessResponse,
)
from app.modules.auth.utils import normalize_email
from app.modules.widget.utils import (
    build_default_widget_config,
    build_onboarding_state,
    build_widget_config_response,
    get_chatbot_settings_by_public_key,
    is_onboarding_complete,
    is_widget_chatbot_available,
    validate_visitor_email,
    validate_visitor_name,
    validate_visitor_phone,
)
from app.modules.widget.visitor_utils import (
    generate_unique_visitor_key,
    get_widget_visitor_by_key,
    save_widget_visitor,
)

logger = logging.getLogger(__name__)


class ChatbotUnavailableError(Exception):
    """Raised when the chatbot cannot accept public widget traffic."""


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


def _resolve_published_chatbot(db: Session, public_key: str) -> Chatbot:
    """Return a published, available chatbot for the given widget public key."""
    settings = get_chatbot_settings_by_public_key(db, public_key)
    if settings is None:
        raise ChatbotNotFoundError()

    chatbot = db.get(Chatbot, settings.chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    if not is_widget_chatbot_available(db, settings):
        raise ChatbotUnavailableError()

    return chatbot


def get_widget_config(db: Session, public_key: str) -> WidgetConfigSuccessResponse:
    """Return public widget configuration for the given public key."""
    settings = get_chatbot_settings_by_public_key(db, public_key)
    if settings is None:
        return WidgetConfigSuccessResponse(
            chatbot_available=False,
            message=messages.CHATBOT_UNAVAILABLE,
            data=build_default_widget_config(),
        )

    config_data = build_widget_config_response(settings)
    if not is_widget_chatbot_available(db, settings):
        return WidgetConfigSuccessResponse(
            chatbot_available=False,
            message=messages.CHATBOT_UNAVAILABLE,
            data=config_data,
        )

    return WidgetConfigSuccessResponse(
        chatbot_available=True,
        data=config_data,
    )


def _build_visitor_info_response(
    session_step: str,
    *,
    visitor_key: str | None = None,
) -> VisitorInfoResponse:
    """Build a visitor onboarding response for the given session step."""
    onboarding = build_onboarding_state(session_step)
    complete = bool(onboarding["onboarding_complete"])
    return VisitorInfoResponse(
        next_step=str(onboarding["visitor_step"]),
        question=onboarding["question"],  # type: ignore[arg-type]
        can_skip=bool(onboarding["can_skip"]),
        onboarding_complete=complete,
        message=messages.THANK_YOU_START_CHAT if complete else None,
        visitor_key=visitor_key,
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
        return _build_visitor_info_response(
            VISITOR_STEP_COMPLETED,
            visitor_key=session.visitor_id,
        )

    submitted_step = payload.step.strip().lower() if payload.step else ""
    if submitted_step != session.visitor_step:
        raise InvalidVisitorStepError()

    if payload.skip:
        raise VisitorOnboardingValidationError(messages.VISITOR_SKIP_NOT_ALLOWED)

    if session.visitor_step == VISITOR_STEP_NAME:
        error = validate_visitor_name(payload.value)
        if error:
            raise VisitorOnboardingValidationError(error)

        update_visitor_onboarding(
            db,
            session,
            visitor_name=payload.value.strip(),  # type: ignore[union-attr]
            visitor_step=VISITOR_STEP_EMAIL,
        )
        return _build_visitor_info_response(VISITOR_STEP_EMAIL)

    if session.visitor_step == VISITOR_STEP_EMAIL:
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
        error = validate_visitor_phone(payload.value)
        if error:
            raise VisitorOnboardingValidationError(error)

        visitor_key = generate_unique_visitor_key(db)
        visitor_name = session.visitor_name or ""
        visitor_email = session.visitor_email or ""
        visitor_phone = payload.value.strip()  # type: ignore[union-attr]

        _, created = save_widget_visitor(
            db,
            chatbot_id=session.chatbot_id,
            visitor_key=visitor_key,
            visitor_name=visitor_name,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
        )
        if created:
            try:
                record_new_visitor(db, session.chatbot_id)
            except Exception:
                logger.exception(
                    "Failed to update visitor analytics for chatbot_id=%s",
                    session.chatbot_id,
                )
        update_visitor_onboarding(
            db,
            session,
            visitor_id=visitor_key,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
            visitor_step=VISITOR_STEP_COMPLETED,
        )
        logger.info(
            "Visitor onboarding completed session_id=%s visitor_key=%s",
            session.session_id,
            visitor_key,
        )
        return _build_visitor_info_response(
            VISITOR_STEP_COMPLETED,
            visitor_key=visitor_key,
        )

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

    if not is_widget_chatbot_available(db, settings):
        logger.warning(
            "Chatbot unavailable for public_key=%s chatbot_id=%s",
            public_key,
            settings.chatbot_id,
        )
        raise ChatbotUnavailableError()

    chatbot = db.get(Chatbot, settings.chatbot_id)
    if chatbot is None:
        logger.warning("Chatbot not found for public_key=%s", public_key)
        raise ChatbotNotFoundError()

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

    start_time = time.perf_counter()
    ai_response = generate_ai_answer(db, chatbot.id, user_message)
    response_time = Decimal(str(round(time.perf_counter() - start_time, 3)))
    answer = ai_response.answer

    logger.info(
        "AI answer generated for chatbot_id=%s session_id=%s answer_length=%s "
        "response_time=%s",
        chatbot.id,
        session.session_id,
        len(answer),
        response_time,
    )

    try:
        create_message(
            db,
            CreateChatMessageRequest(
                session_id=session.id,
                user_message=user_message,
                bot_response=answer,
                response_time=response_time,
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

    try:
        record_chat_exchange(db, chatbot.id)
    except Exception:
        logger.exception(
            "Failed to update chat analytics for chatbot_id=%s session_id=%s",
            chatbot.id,
            session.session_id,
        )

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

    if not is_widget_chatbot_available(db, settings):
        raise ChatbotUnavailableError()

    chatbot = db.get(Chatbot, settings.chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    visitor_key = payload.visitor_key.strip() if payload.visitor_key else None
    if visitor_key:
        visitor = get_widget_visitor_by_key(db, chatbot.id, visitor_key)
        if visitor is not None:
            session = create_chat_session(
                db,
                chatbot.id,
                visitor_key=visitor.visitor_key,
                visitor_name=visitor.visitor_name,
                visitor_email=visitor.visitor_email,
                visitor_phone=visitor.visitor_phone,
                visitor_step=VISITOR_STEP_COMPLETED,
            )
            logger.info(
                "Created chat session with returning visitor session_id=%s visitor_key=%s",
                session.session_id,
                visitor.visitor_key,
            )
            _record_new_session_analytics(db, chatbot.id)
            return StartSessionResponse(session_id=session.session_id)

    session = create_chat_session(db, chatbot.id)
    _record_new_session_analytics(db, chatbot.id)
    return StartSessionResponse(session_id=session.session_id)


def _record_new_session_analytics(db: Session, chatbot_id: int) -> None:
    """Update analytics counters for a newly created widget chat session."""
    try:
        record_new_chat_session(db, chatbot_id)
    except Exception:
        logger.exception(
            "Failed to update chat analytics for new session chatbot_id=%s",
            chatbot_id,
        )


def get_chat_history(db: Session, session_id: str) -> ChatHistoryResponse:
    """Return chat history and visitor onboarding state for a session."""
    if not session_id or not session_id.strip():
        raise ChatSessionNotFoundError()

    session = get_chat_session_by_session_id(db, session_id.strip())
    if session is None:
        raise ChatSessionNotFoundError()

    chatbot = db.get(Chatbot, session.chatbot_id)
    if not is_chatbot_widget_available(chatbot):
        return ChatHistoryResponse(
            success=False,
            chatbot_available=False,
            message=messages.CHATBOT_UNAVAILABLE_PUBLIC,
        )

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
        is_active=session.is_active,
        is_resolved=session.is_resolved,
    )


def update_chat_session_status(
    db: Session,
    payload: UpdateChatSessionStatusRequest,
) -> UpdateChatSessionStatusResponse:
    """Close a widget chat session and record mandatory visitor feedback."""
    if not payload.public_key or not payload.public_key.strip():
        raise ChatbotNotFoundError()

    if not payload.session_id or not payload.session_id.strip():
        raise ChatSessionNotFoundError()

    public_key = payload.public_key.strip()
    chatbot = _resolve_published_chatbot(db, public_key)

    logger.info(
        "Widget chat session status update public_key=%s session_id=%s",
        public_key,
        payload.session_id,
    )

    try:
        return update_chat_session_status_record(
            db,
            ChatSessionStatusRequest(
                public_key=public_key,
                session_id=payload.session_id.strip(),
                is_active=payload.is_active,
                is_resolved=payload.is_resolved,
            ),
            chatbot_id=chatbot.id,
        )
    except ChatSessionServiceNotFoundError:
        raise ChatSessionNotFoundError() from None
    except ChatSessionValidationError:
        raise
    except ChatAlreadyClosedError:
        raise
    except ChatSessionNotActiveError:
        raise
