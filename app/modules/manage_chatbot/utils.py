"""
Manage Chatbot module helper utilities.
"""

import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.auth.utils import USER_ROLE_ADMIN, USER_ROLE_SUPERADMIN
from app.modules.chatbot.model import Chatbot
from app.modules.chatbot_settings.utils import (
    delete_chromadb_vectors_for_chatbot,
    delete_chromadb_vectors_for_document,
    get_chatbot_owner,
    get_knowledgebase_documents,
)
from app.modules.knowledgebase.exceptions import KnowledgeBaseStorageError
from app.modules.knowledgebase.s3_storage import (
    delete_knowledgebase_file_from_s3_strict,
    is_knowledgebase_s3_url,
)
from app.modules.knowledgebase.utils import KNOWLEDGEBASE_UPLOAD_DIR
from app.modules.user_details.utils import is_superadmin
from app.modules.user_plan.service import reconcile_created_chatbot_count

logger = logging.getLogger(__name__)


def get_chatbot_for_management(db: Session, chatbot_id: int) -> Chatbot | None:
    """Return a chatbot by ID for administrative management, including soft-deleted rows."""
    return db.get(Chatbot, chatbot_id)


def validate_manage_chatbot_permission(actor: User, owner: User) -> bool:
    """
    Return True when the actor may permanently delete the owner's chatbot.

    SuperAdmin may permanently delete any chatbot.
    Admin may permanently delete Admin- and User-owned chatbots (not SuperAdmin).
    """
    if is_superadmin(actor):
        return True
    if actor.role == USER_ROLE_ADMIN and owner.role != USER_ROLE_SUPERADMIN:
        return True
    return False


def delete_chatbot_from_s3(db: Session, chatbot_id: int) -> None:
    """
    Delete knowledge base files stored in AWS S3 (and local fallbacks) for a chatbot.

    Reuses the existing S3 delete service. Must run before database record removal.
    """
    documents = get_knowledgebase_documents(db, chatbot_id)
    for document in documents:
        if not document.file_path:
            continue

        if is_knowledgebase_s3_url(document.file_path):
            try:
                delete_knowledgebase_file_from_s3_strict(document.file_path)
                logger.info(
                    "Deleted knowledge base S3 file for chatbot_id=%s document_id=%s",
                    chatbot_id,
                    document.id,
                )
            except RuntimeError as exc:
                raise KnowledgeBaseStorageError(str(exc)) from exc
        else:
            file_path = Path(document.file_path)
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(
                        "Deleted local knowledge base file for chatbot_id=%s document_id=%s",
                        chatbot_id,
                        document.id,
                    )
                except OSError:
                    logger.exception(
                        "Failed to delete local knowledge base file %s",
                        file_path,
                    )


def delete_chatbot_vectors(db: Session, chatbot_id: int) -> None:
    """Remove ChromaDB embeddings associated with a single chatbot."""
    documents = get_knowledgebase_documents(db, chatbot_id)
    for document in documents:
        delete_chromadb_vectors_for_document(document.id)

    delete_chromadb_vectors_for_chatbot(chatbot_id)


def delete_chatbot_related_records(db: Session, chatbot: Chatbot) -> None:
    """
    Permanently remove the chatbot row and related database records.

    Related tables cascade via ORM/DB foreign keys (settings, sessions, messages,
    knowledge base documents/chunks, analysis, widget visitors).
    """
    chatbot_id = chatbot.id
    owner_user_id = chatbot.user_id

    documents = get_knowledgebase_documents(db, chatbot_id)
    for document in documents:
        db.delete(document)

    upload_dir = KNOWLEDGEBASE_UPLOAD_DIR / str(chatbot_id)
    if upload_dir.exists():
        try:
            shutil.rmtree(upload_dir)
            logger.info(
                "Removed knowledge base upload directory for chatbot_id=%s",
                chatbot_id,
            )
        except OSError:
            logger.exception(
                "Failed to remove knowledge base upload directory for chatbot_id=%s",
                chatbot_id,
            )

    db.delete(chatbot)
    db.flush()
    reconcile_created_chatbot_count(db, owner_user_id)
    logger.info("Deleted chatbot-related database records for chatbot_id=%s", chatbot_id)


def resolve_chatbot_owner_label(owner: User) -> str:
    """Build a human-readable owner label for audit logging."""
    name_parts = [part for part in (owner.first_name, owner.last_name) if part]
    full_name = " ".join(name_parts).strip()
    if full_name:
        return f"{full_name} (user_id={owner.id}, role={owner.role})"
    return f"user_id={owner.id}, role={owner.role}"


def get_chatbot_owner_for_management(db: Session, chatbot: Chatbot) -> User:
    """Return the chatbot owner for management permission checks."""
    return get_chatbot_owner(db, chatbot)
