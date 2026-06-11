import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.modules.auth.model import User
from app.modules.chatbot.model import Chatbot
from app.modules.chatbot.service import ChatbotNotFoundError, ChatbotPermissionError
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
    KnowledgebaseUploadData,
    KnowledgebaseUploadSuccessResponse,
)
from app.modules.knowledgebase.utils import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MAX_UPLOAD_SIZE_BYTES,
    extract_file_text,
    extract_url_text,
    get_file_extension,
    is_allowed_file_type,
    save_uploaded_file,
    split_text_into_chunks,
)


class UnsupportedFileTypeError(Exception):
    """Raised when an uploaded file type is not supported."""


class FileSizeExceededError(Exception):
    """Raised when the total upload size exceeds the allowed limit."""


class NoKnowledgeSourcesError(Exception):
    """Raised when no files or URLs are provided."""


@dataclass
class UploadedFilePayload:
    filename: str
    content: bytes


def _get_owned_chatbot(db: Session, user: User, chatbot_id: int) -> Chatbot:
    """Return a chatbot owned by the user or raise a domain error."""
    chatbot = db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise ChatbotNotFoundError()

    if chatbot.user_id != user.id:
        raise ChatbotPermissionError()

    return chatbot


def _validate_upload_payload(
    files: list[UploadedFilePayload],
    urls: list[str],
) -> None:
    """Validate file types, total size, and presence of at least one source."""
    if not files and not urls:
        raise NoKnowledgeSourcesError()

    total_size = sum(len(file.content) for file in files)
    if total_size > MAX_UPLOAD_SIZE_BYTES:
        raise FileSizeExceededError()

    for file in files:
        if not is_allowed_file_type(file.filename):
            raise UnsupportedFileTypeError()


def _process_file_source(
    db: Session,
    chatbot_id: int,
    file_payload: UploadedFilePayload,
) -> KnowledgebaseDocument:
    """Save a file, create a DB record, and extract its text."""
    file_type = get_file_extension(file_payload.filename)
    document = KnowledgebaseDocument(
        chatbot_id=chatbot_id,
        source_type=SOURCE_TYPE_FILE,
        original_name=Path(file_payload.filename).name,
        source_url=None,
        file_path=None,
        file_type=file_type.lstrip("."),
        file_size=len(file_payload.content),
        extracted_text=None,
        processing_status=STATUS_PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        document.processing_status = STATUS_PROCESSING
        document.updated_at = datetime.now(timezone.utc)
        db.commit()

        saved_path = save_uploaded_file(
            chatbot_id,
            file_payload.filename,
            file_payload.content,
        )
        extracted_text = extract_file_text(saved_path, file_type)

        document.file_path = str(saved_path)
        document.extracted_text = extracted_text
        document.processing_status = STATUS_COMPLETED
    except Exception:
        logger.exception("Failed to extract text from file %s", file_payload.filename)
        document.processing_status = STATUS_FAILED
    finally:
        document.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)

    return document


def _process_url_source(db: Session, chatbot_id: int, url: str) -> KnowledgebaseDocument:
    """Create a DB record for a URL and extract its text."""
    normalized_url = url.strip()
    document = KnowledgebaseDocument(
        chatbot_id=chatbot_id,
        source_type=SOURCE_TYPE_URL,
        original_name=normalized_url,
        source_url=normalized_url,
        file_path=None,
        file_type="url",
        file_size=None,
        extracted_text=None,
        processing_status=STATUS_PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        document.processing_status = STATUS_PROCESSING
        document.updated_at = datetime.now(timezone.utc)
        db.commit()

        extracted_text = extract_url_text(normalized_url)
        document.extracted_text = extracted_text
        document.processing_status = STATUS_COMPLETED
    except Exception:
        logger.exception("Failed to extract text from URL %s", normalized_url)
        document.processing_status = STATUS_FAILED
    finally:
        document.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)

    return document


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
) -> int:
    """Generate and persist knowledge chunks for an uploaded document."""
    chunks_data = generate_chunks_from_text(extracted_text)
    if not chunks_data:
        return 0

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
    return len(chunk_records)


def _save_chunks_for_document(
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

    return save_document_chunks(
        db,
        chatbot_id,
        document.id,
        document.extracted_text,
    )


def upload_knowledgebase(
    db: Session,
    user: User,
    chatbot_id: int,
    files: list[UploadedFilePayload],
    urls: list[str],
) -> KnowledgebaseUploadSuccessResponse:
    """Upload files and URLs, extract text, and store knowledge base records."""
    _get_owned_chatbot(db, user, chatbot_id)
    _validate_upload_payload(files, urls)

    documents: list[KnowledgebaseDocument] = []
    total_chunks = 0

    for file_payload in files:
        document = _process_file_source(db, chatbot_id, file_payload)
        documents.append(document)
        total_chunks += _save_chunks_for_document(db, chatbot_id, document)

    for url in urls:
        normalized_url = url.strip()
        if not normalized_url:
            continue
        document = _process_url_source(db, chatbot_id, normalized_url)
        documents.append(document)
        total_chunks += _save_chunks_for_document(db, chatbot_id, document)

    total_sources = len(documents)
    processed_sources = sum(
        1 for document in documents if document.processing_status == STATUS_COMPLETED
    )

    return KnowledgebaseUploadSuccessResponse(
        message="Knowledge base uploaded successfully",
        data=KnowledgebaseUploadData(
            chatbot_id=chatbot_id,
            total_sources=total_sources,
            processed_sources=processed_sources,
            total_chunks=total_chunks,
        ),
    )
