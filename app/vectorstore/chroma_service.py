"""
ChromaDB storage service for knowledge base chunks.
"""

import logging

from app.vectorstore.chroma_client import get_knowledge_base_collection
from app.vectorstore.utils import build_chunk_id, build_chunk_metadata

logger = logging.getLogger(__name__)


class ChromaStorageError(Exception):
    """Raised when storing chunks in ChromaDB fails."""


def store_chunks_in_chromadb(
    chatbot_id: int,
    document_id: int,
    chunks: list[dict[str, int | str]],
) -> int:
    """
    Store document chunks in ChromaDB for future semantic search and RAG retrieval.

    Chunk text is persisted now; custom embedding generation will be added later.
    """
    if not chunks:
        return 0

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, int]] = []

    for chunk in chunks:
        chunk_index = int(chunk["chunk_index"])
        ids.append(build_chunk_id(document_id, chunk_index))
        documents.append(str(chunk["chunk_text"]))
        metadatas.append(
            build_chunk_metadata(chatbot_id, document_id, chunk_index)
        )

    try:
        collection = get_knowledge_base_collection()
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "Stored %s chunks in ChromaDB for chatbot_id=%s document_id=%s",
            len(chunks),
            chatbot_id,
            document_id,
        )
        return len(chunks)
    except Exception as exc:
        logger.exception(
            "Failed to store chunks in ChromaDB for chatbot_id=%s document_id=%s",
            chatbot_id,
            document_id,
        )
        raise ChromaStorageError(
            "Failed to store document chunks in ChromaDB"
        ) from exc
