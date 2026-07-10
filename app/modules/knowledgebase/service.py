import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import messages

logger = logging.getLogger(__name__)

from app.modules.auth.model import User
from app.modules.chatbot.model import Chatbot
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError
from app.modules.chatbot_settings.utils import get_owned_chatbot
from app.modules.notification.service import trigger_chatbot_updated_notification
from app.modules.knowledgebase.model import (
    SOURCE_TYPE_FILE,
    SOURCE_TYPE_URL,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    KnowledgeChunk,
    KnowledgebaseDocument,
)
from app.modules.knowledgebase.schema import (
    KnowledgebaseProcessingStatusResponse,
    KnowledgebaseUploadData,
    KnowledgebaseUploadSuccessResponse,
)
from app.embeddings.embedding_service import generate_embeddings_for_chunks
from app.modules.knowledgebase.exceptions import KnowledgeBaseStorageError
from app.modules.knowledgebase.s3_storage import (
    build_knowledgebase_object_key,
    delete_knowledgebase_file_from_s3,
    resolve_knowledgebase_content_type,
    upload_knowledgebase_file_to_s3,
)
from app.modules.knowledgebase.utils import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MAX_UPLOAD_SIZE_BYTES,
    get_file_extension,
    is_allowed_file_type,
    split_text_into_chunks,
    validate_knowledgebase_file_size,
)
from app.vectorstore.chroma_service import store_chunks_in_chromadb


class UnsupportedFileTypeError(Exception):
    """Raised when an uploaded file type is not supported."""


class FileSizeExceededError(Exception):
    """Raised when the total upload size exceeds the allowed limit."""


class KnowledgeBaseFileSizeExceededError(Exception):
    """Raised when an individual knowledge base file exceeds the allowed size."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or messages.KNOWLEDGE_BASE_FILE_SIZE_EXCEEDED
        super().__init__(self.message)


class NoKnowledgeSourcesError(Exception):
    """Raised when no files or URLs are provided."""


ACTIVE_PROCESSING_STATUSES = {STATUS_PENDING, STATUS_PROCESSING}


@dataclass
class UploadedFilePayload:
    filename: str
    content: bytes


def _get_owned_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot the user may modify or raise a domain error."""
    return get_owned_chatbot(db, user, chatbot_id)


def _validate_upload_payload(
    files: list[UploadedFilePayload],
    urls: list[str],
) -> None:
    """Validate file types, total size, and presence of at least one source."""
    if not files and not urls:
        raise NoKnowledgeSourcesError()

    for file in files:
        if not is_allowed_file_type(file.filename):
            raise UnsupportedFileTypeError()
        file_size_error = validate_knowledgebase_file_size(len(file.content))
        if file_size_error:
            raise KnowledgeBaseFileSizeExceededError(file_size_error)

    total_size = sum(len(file.content) for file in files)
    if total_size > MAX_UPLOAD_SIZE_BYTES:
        raise FileSizeExceededError()


def _create_file_document(
    db: Session,
    chatbot_id: int,
    file_payload: UploadedFilePayload,
) -> KnowledgebaseDocument:
    """Upload a file to S3 and create a pending knowledge base document record."""
    file_type = get_file_extension(file_payload.filename)
    object_key = build_knowledgebase_object_key(chatbot_id, file_payload.filename)
    s3_url: str | None = None
    now = datetime.now(timezone.utc)

    try:
        s3_url = upload_knowledgebase_file_to_s3(
            content=file_payload.content,
            object_key=object_key,
            content_type=resolve_knowledgebase_content_type(file_type),
        )
    except RuntimeError as exc:
        raise KnowledgeBaseStorageError(str(exc)) from exc

    document = KnowledgebaseDocument(
        chatbot_id=chatbot_id,
        source_type=SOURCE_TYPE_FILE,
        original_name=Path(file_payload.filename).name,
        source_url=None,
        file_path=s3_url,
        file_type=file_type.lstrip("."),
        file_size=len(file_payload.content),
        extracted_text=None,
        processing_status=STATUS_PROCESSING,
        processing_started_at=now,
        processing_completed_at=None,
        processing_error=None,
    )
    db.add(document)

    try:
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        delete_knowledgebase_file_from_s3(s3_url)
        logger.exception(
            "Failed to persist knowledge base document after S3 upload file=%s",
            file_payload.filename,
        )
        raise

    return document


def _create_url_document(db: Session, chatbot_id: int, url: str) -> KnowledgebaseDocument:
    """Create a pending knowledge base document record for a website URL."""
    normalized_url = url.strip()
    now = datetime.now(timezone.utc)
    document = KnowledgebaseDocument(
        chatbot_id=chatbot_id,
        source_type=SOURCE_TYPE_URL,
        original_name=normalized_url,
        source_url=normalized_url,
        file_path=None,
        file_type="url",
        file_size=None,
        extracted_text=None,
        processing_status=STATUS_PROCESSING,
        processing_started_at=now,
        processing_completed_at=None,
        processing_error=None,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def schedule_knowledgebase_processing(
    background_tasks: BackgroundTasks,
    chatbot_id: int,
    document_ids: list[int],
) -> None:
    """
    Enqueue background processing for uploaded knowledge base documents.

    Uses the synchronous entry point so FastAPI/Starlette runs it in a
    threadpool. That keeps heavy PDF/OCR/embedding work off the event loop
    and prevents other API requests from timing out while processing.
    """
    from app.modules.knowledgebase.background_processor import (
        process_knowledgebase_document_sync,
    )

    for document_id in document_ids:
        background_tasks.add_task(
            process_knowledgebase_document_sync,
            document_id,
            chatbot_id,
        )


def generate_chunks_from_text(
    extracted_text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, int | str]]:
    """Generate structured chunk data from extracted document text."""
    return split_text_into_chunks(
        text=extracted_text,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def save_document_chunks(
    db: Session,
    chatbot_id: int,
    document_id: int,
    extracted_text: str,
) -> tuple[int, list[dict[str, int | str]]]:
    """Generate and persist knowledge chunks for an uploaded document."""
    chunks_data = generate_chunks_from_text(extracted_text)
    if not chunks_data:
        return 0, []

    chunk_records = [
        KnowledgeChunk(
            chatbot_id=chatbot_id,
            document_id=document_id,
            chunk_index=int(chunk["chunk_index"]),
            chunk_text=str(chunk["chunk_text"]),
            character_count=int(chunk["character_count"]),
        )
        for chunk in chunks_data
    ]

    db.add_all(chunk_records)
    db.commit()
    return len(chunk_records), chunks_data


def save_chunks_for_document(
    db: Session,
    chatbot_id: int,
    document: KnowledgebaseDocument,
) -> int:
    """Persist chunks when document text extraction completed successfully."""
    if (
        document.processing_status != STATUS_COMPLETED
        or not document.extracted_text
        or not document.extracted_text.strip()
    ):
        return 0

    chunk_count, chunks_data = save_document_chunks(
        db,
        chatbot_id,
        document.id,
        document.extracted_text,
    )
    if chunk_count > 0:
        embedded_chunks = generate_embeddings_for_chunks(chunks_data)
        if embedded_chunks:
            store_chunks_in_chromadb(chatbot_id, document.id, embedded_chunks)
    return chunk_count


def _get_chatbot_documents(db: Session, chatbot_id: int) -> list[KnowledgebaseDocument]:
    return list(
        db.execute(
            select(KnowledgebaseDocument)
            .where(KnowledgebaseDocument.chatbot_id == chatbot_id)
            .order_by(KnowledgebaseDocument.id.asc())
        ).scalars().all()
    )


def resolve_knowledgebase_processing_status(
    documents: list[KnowledgebaseDocument],
) -> tuple[str, str | None]:
    """Resolve aggregate processing status and optional error message."""
    if not documents:
        return STATUS_COMPLETED, None

    statuses = {document.processing_status for document in documents}
    if statuses & ACTIVE_PROCESSING_STATUSES:
        return STATUS_PROCESSING, None

    failed_documents = [
        document for document in documents if document.processing_status == STATUS_FAILED
    ]
    if failed_documents:
        latest_failed = max(
            failed_documents,
            key=lambda document: document.updated_at,
        )
        return STATUS_FAILED, latest_failed.processing_error

    if statuses == {STATUS_COMPLETED}:
        return STATUS_COMPLETED, None

    return STATUS_PROCESSING, None


def get_knowledgebase_processing_status(
    db: Session,
    user: User,
    chatbot_id: int,
) -> KnowledgebaseProcessingStatusResponse:
    """Return aggregate knowledge base processing status for a chatbot."""
    _get_owned_chatbot(db, user, chatbot_id)
    documents = _get_chatbot_documents(db, chatbot_id)
    status, error = resolve_knowledgebase_processing_status(documents)

    return KnowledgebaseProcessingStatusResponse(
        success=True,
        status=status,
        error=error,
    )


async def upload_knowledgebase(
    db: Session,
    user: User,
    chatbot_id: int,
    files: list[UploadedFilePayload],
    urls: list[str],
    background_tasks: BackgroundTasks,
) -> KnowledgebaseUploadSuccessResponse:
    """Upload files and URLs, then process knowledge base records in the background."""
    chatbot = get_owned_chatbot(db, user, chatbot_id)
    _validate_upload_payload(files, urls)

    documents: list[KnowledgebaseDocument] = []
    document_ids: list[int] = []

    for file_payload in files:
        document = _create_file_document(db, chatbot_id, file_payload)
        documents.append(document)
        document_ids.append(document.id)

    for url in urls:
        normalized_url = url.strip()
        if not normalized_url:
            continue
        document = _create_url_document(db, chatbot_id, normalized_url)
        documents.append(document)
        document_ids.append(document.id)

    schedule_knowledgebase_processing(background_tasks, chatbot_id, document_ids)
    trigger_chatbot_updated_notification(db, chatbot, user)

    return KnowledgebaseUploadSuccessResponse(
        message=messages.KNOWLEDGE_BASE_UPLOAD_STARTED,
        status=STATUS_PROCESSING,
        data=KnowledgebaseUploadData(
            chatbot_id=chatbot_id,
            total_sources=len(documents),
            processed_sources=0,
            total_chunks=0,
        ),
    )
