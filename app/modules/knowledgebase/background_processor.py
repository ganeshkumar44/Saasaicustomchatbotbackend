"""
Background knowledge base document processing.

Entry points here are designed for FastAPI BackgroundTasks today and can be
reused by Celery/RQ workers later without changing processing logic.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.modules.knowledgebase.model import (
    SOURCE_TYPE_FILE,
    SOURCE_TYPE_URL,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    KnowledgebaseDocument,
)
from app.modules.knowledgebase.utils import (
    extract_file_text_from_storage,
    extract_url_text,
)

logger = logging.getLogger(__name__)


def _get_document(
    db,
    document_id: int,
    chatbot_id: int,
) -> KnowledgebaseDocument | None:
    document = db.get(KnowledgebaseDocument, document_id)
    if document is None or document.chatbot_id != chatbot_id:
        logger.error(
            "Knowledge base document not found document_id=%s chatbot_id=%s",
            document_id,
            chatbot_id,
        )
        return None
    return document


def _mark_processing_started(db, document: KnowledgebaseDocument) -> None:
    now = datetime.now(timezone.utc)
    document.processing_status = STATUS_PROCESSING
    document.processing_started_at = now
    document.processing_completed_at = None
    document.processing_error = None
    document.updated_at = now
    db.commit()


def _mark_processing_failed(
    db,
    document: KnowledgebaseDocument,
    error_message: str,
) -> None:
    now = datetime.now(timezone.utc)
    document.processing_status = STATUS_FAILED
    document.processing_error = error_message[:2000]
    document.processing_completed_at = now
    document.updated_at = now
    db.commit()


def _mark_processing_completed(db, document: KnowledgebaseDocument, extracted_text: str) -> None:
    now = datetime.now(timezone.utc)
    document.extracted_text = extracted_text
    document.processing_status = STATUS_COMPLETED
    document.processing_error = None
    document.processing_completed_at = now
    document.updated_at = now
    db.commit()


async def _extract_document_text(document: KnowledgebaseDocument) -> str:
    if document.source_type == SOURCE_TYPE_FILE:
        return extract_file_text_from_storage(
            file_path=document.file_path,
            file_type=document.file_type,
        )

    if document.source_type == SOURCE_TYPE_URL:
        url = document.source_url or document.original_name
        return await extract_url_text(url)

    raise ValueError(f"Unsupported knowledge base source type: {document.source_type}")


async def process_knowledgebase_document(document_id: int, chatbot_id: int) -> None:
    """
    Process a single knowledge base document in the background.

  Responsibilities:
    - Text extraction (files, URLs, OCR, tables)
    - Chunking, embedding, and ChromaDB storage
    - Database status updates
    """
    # Import here to avoid circular imports between service and background processor.
    from app.modules.knowledgebase.service import save_chunks_for_document

    db = SessionLocal()
    try:
        document = _get_document(db, document_id, chatbot_id)
        if document is None:
            return

        _mark_processing_started(db, document)
        db.refresh(document)

        try:
            extracted_text = await _extract_document_text(document)
            _mark_processing_completed(db, document, extracted_text)
            db.refresh(document)

            if document.extracted_text and document.extracted_text.strip():
                save_chunks_for_document(db, chatbot_id, document)
        except Exception as exc:
            logger.exception(
                "Knowledge base background processing failed document_id=%s chatbot_id=%s",
                document_id,
                chatbot_id,
            )
            db.refresh(document)
            _mark_processing_failed(db, document, str(exc))
    except Exception as exc:
        logger.exception(
            "Unhandled knowledge base background processing error document_id=%s chatbot_id=%s",
            document_id,
            chatbot_id,
        )
        try:
            document = _get_document(db, document_id, chatbot_id)
            if document is not None:
                _mark_processing_failed(db, document, str(exc))
        except Exception:
            logger.exception(
                "Failed to persist knowledge base failure status document_id=%s",
                document_id,
            )
    finally:
        db.close()


def process_knowledgebase_document_sync(document_id: int, chatbot_id: int) -> None:
    """
    Synchronous entry point for FastAPI BackgroundTasks, Celery, and RQ.

    FastAPI/Starlette runs sync background tasks in a threadpool, which keeps
    heavy extraction/embedding work from blocking the API event loop.
    """
    asyncio.run(process_knowledgebase_document(document_id, chatbot_id))
