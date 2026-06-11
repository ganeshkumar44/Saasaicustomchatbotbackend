"""
Knowledge chunks business logic.
"""

from sqlalchemy.orm import Session

from app.modules.chatbot.model import Chatbot
from app.modules.knowledge_chunks.model import KnowledgeChunk
from app.modules.knowledge_chunks.schema import (
    CreateKnowledgeChunkRequest,
    KnowledgeChunkResponse,
)
from app.modules.knowledge_chunks.utils import (
    build_knowledge_chunk_response,
    get_chunks_by_chatbot_id,
    get_chunks_by_document_id,
)
from app.modules.knowledgebase.model import KnowledgebaseDocument


class ChatbotNotFoundError(Exception):
    """Raised when the requested chatbot does not exist."""


class DocumentNotFoundError(Exception):
    """Raised when the requested knowledge document does not exist."""


class DocumentChatbotMismatchError(Exception):
    """Raised when a document does not belong to the specified chatbot."""


def _validate_document_for_chatbot(
    db: Session,
    chatbot_id: int,
    document_id: int,
) -> KnowledgebaseDocument:
    """Return the document when it exists and belongs to the chatbot."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    document = db.get(KnowledgebaseDocument, document_id)
    if document is None:
        raise DocumentNotFoundError()

    if document.chatbot_id != chatbot_id:
        raise DocumentChatbotMismatchError()

    return document


def create_chunk(
    db: Session,
    payload: CreateKnowledgeChunkRequest,
) -> KnowledgeChunkResponse:
    """Create a single knowledge chunk for a document."""
    _validate_document_for_chatbot(db, payload.chatbot_id, payload.document_id)

    chunk = KnowledgeChunk(
        chatbot_id=payload.chatbot_id,
        document_id=payload.document_id,
        chunk_text=payload.chunk_text,
        chunk_index=payload.chunk_index,
        character_count=payload.character_count,
    )

    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    return build_knowledge_chunk_response(chunk)


def bulk_create_chunks(
    db: Session,
    payloads: list[CreateKnowledgeChunkRequest],
) -> list[KnowledgeChunkResponse]:
    """Create multiple knowledge chunks in a single transaction."""
    if not payloads:
        return []

    first_payload = payloads[0]
    _validate_document_for_chatbot(
        db,
        first_payload.chatbot_id,
        first_payload.document_id,
    )

    for payload in payloads[1:]:
        if (
            payload.chatbot_id != first_payload.chatbot_id
            or payload.document_id != first_payload.document_id
        ):
            raise DocumentChatbotMismatchError()

    chunks = [
        KnowledgeChunk(
            chatbot_id=payload.chatbot_id,
            document_id=payload.document_id,
            chunk_text=payload.chunk_text,
            chunk_index=payload.chunk_index,
            character_count=payload.character_count,
        )
        for payload in payloads
    ]

    db.add_all(chunks)
    db.commit()

    for chunk in chunks:
        db.refresh(chunk)

    return [build_knowledge_chunk_response(chunk) for chunk in chunks]


def get_chunks_by_document(
    db: Session,
    document_id: int,
) -> list[KnowledgeChunkResponse]:
    """Return all chunks for a knowledge document."""
    document = db.get(KnowledgebaseDocument, document_id)
    if document is None:
        raise DocumentNotFoundError()

    chunks = get_chunks_by_document_id(db, document_id)
    return [build_knowledge_chunk_response(chunk) for chunk in chunks]


def get_chunks_by_chatbot(
    db: Session,
    chatbot_id: int,
) -> list[KnowledgeChunkResponse]:
    """Return all chunks for a chatbot."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None:
        raise ChatbotNotFoundError()

    chunks = get_chunks_by_chatbot_id(db, chatbot_id)
    return [build_knowledge_chunk_response(chunk) for chunk in chunks]


def delete_document_chunks(db: Session, document_id: int) -> int:
    """Delete all chunks for a knowledge document."""
    document = db.get(KnowledgebaseDocument, document_id)
    if document is None:
        raise DocumentNotFoundError()

    chunks = get_chunks_by_document_id(db, document_id)
    deleted_count = len(chunks)

    for chunk in chunks:
        db.delete(chunk)

    db.commit()
    return deleted_count
