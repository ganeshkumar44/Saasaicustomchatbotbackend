"""
Knowledge chunks helper utilities.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.knowledge_chunks.model import KnowledgeChunk
from app.modules.knowledge_chunks.schema import KnowledgeChunkResponse


def get_chunks_by_document_id(db: Session, document_id: int) -> list[KnowledgeChunk]:
    """Return all chunks for a document ordered by chunk index."""
    return list(
        db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        ).scalars().all()
    )


def get_chunks_by_chatbot_id(db: Session, chatbot_id: int) -> list[KnowledgeChunk]:
    """Return all chunks for a chatbot ordered by document and chunk index."""
    return list(
        db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.chatbot_id == chatbot_id)
            .order_by(
                KnowledgeChunk.document_id.asc(),
                KnowledgeChunk.chunk_index.asc(),
            )
        ).scalars().all()
    )


def build_knowledge_chunk_response(chunk: KnowledgeChunk) -> KnowledgeChunkResponse:
    """Map a knowledge chunk ORM record to a Pydantic response."""
    return KnowledgeChunkResponse(
        id=chunk.id,
        chatbot_id=chunk.chatbot_id,
        document_id=chunk.document_id,
        chunk_text=chunk.chunk_text,
        chunk_index=chunk.chunk_index,
        created_at=chunk.created_at,
    )
