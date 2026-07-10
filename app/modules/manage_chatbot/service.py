"""
Manage Chatbot module business logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import messages
from app.modules.auth.model import User
from app.modules.chatbot.service import ChatbotNotFoundError
from app.modules.knowledgebase.exceptions import KnowledgeBaseStorageError
from app.modules.manage_chatbot.schema import PermanentlyDeleteChatbotSuccessResponse
from app.modules.manage_chatbot.utils import (
    delete_chatbot_from_s3,
    delete_chatbot_related_records,
    delete_chatbot_vectors,
    get_chatbot_for_management,
    get_chatbot_owner_for_management,
    resolve_chatbot_owner_label,
    validate_manage_chatbot_permission,
)
from app.modules.notification.service import notify_chatbot_deleted

logger = logging.getLogger(__name__)


class ManageChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class ManageChatbotPermissionError(Exception):
    """Raised when the actor may not permanently delete the chatbot."""


class ManageChatbotStorageError(Exception):
    """Raised when knowledge base storage cleanup fails during hard delete."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def permanently_delete_chatbot(
    db: Session,
    actor: User,
    chatbot_id: int,
) -> PermanentlyDeleteChatbotSuccessResponse:
    """
    Permanently (hard) delete a chatbot and all related resources.

    SuperAdmin may delete any chatbot. Admin may delete User-owned chatbots only.
    """
    logger.info(
        "Manage chatbot permanent delete requested chatbot_id=%s actor_user_id=%s actor_role=%s",
        chatbot_id,
        actor.id,
        actor.role,
    )

    chatbot = get_chatbot_for_management(db, chatbot_id)
    if chatbot is None:
        raise ManageChatbotNotFoundError()

    try:
        owner = get_chatbot_owner_for_management(db, chatbot)
    except ChatbotNotFoundError as exc:
        raise ManageChatbotNotFoundError() from exc

    if not validate_manage_chatbot_permission(actor, owner):
        logger.warning(
            "Unauthorized manage-chatbot permanent delete chatbot_id=%s "
            "owner_id=%s owner_role=%s actor_user_id=%s actor_role=%s",
            chatbot_id,
            owner.id,
            owner.role,
            actor.id,
            actor.role,
        )
        raise ManageChatbotPermissionError()

    chatbot_name = chatbot.chatbot_name or "(unnamed)"
    owner_label = resolve_chatbot_owner_label(owner)
    owner_user_id = owner.id
    deleted_at = datetime.now(timezone.utc)

    try:
        # External storage first, then vectors, then DB records in one transaction.
        delete_chatbot_from_s3(db, chatbot_id)
        delete_chatbot_vectors(db, chatbot_id)
        delete_chatbot_related_records(db, chatbot)
        db.commit()
    except KnowledgeBaseStorageError as exc:
        db.rollback()
        logger.exception(
            "Manage chatbot permanent delete failed during S3 cleanup chatbot_id=%s",
            chatbot_id,
        )
        raise ManageChatbotStorageError(str(exc)) from exc
    except Exception:
        db.rollback()
        logger.exception(
            "Manage chatbot permanent delete failed chatbot_id=%s actor_user_id=%s",
            chatbot_id,
            actor.id,
        )
        raise

    logger.info(
        "Manage chatbot permanently deleted "
        "actor_user_id=%s actor_role=%s chatbot_id=%s chatbot_name=%s "
        "chatbot_owner=%s deleted_at=%s",
        actor.id,
        actor.role,
        chatbot_id,
        chatbot_name,
        owner_label,
        deleted_at.isoformat(),
    )

    notify_chatbot_deleted(
        db,
        owner_user_id=owner_user_id,
        chatbot_id=chatbot_id,
        deleted_by_user_id=actor.id,
    )

    return PermanentlyDeleteChatbotSuccessResponse(
        message=messages.MANAGE_CHATBOT_PERMANENTLY_DELETED_SUCCESS,
    )
