"""
ChromaDB storage service for knowledge base chunks.
"""

import logging
from typing import Any

from app.vectorstore.chroma_client import get_knowledge_base_collection
from app.vectorstore.utils import build_chunk_id, build_chunk_metadata

logger = logging.getLogger(__name__)


class ChromaStorageError(Exception):
    """Raised when storing chunks in ChromaDB fails."""


def store_chunks_in_chromadb(
    chatbot_id: int,
    document_id: int,
    chunks: list[dict[str, Any]],
) -> int:
    """
    Store document chunks and embeddings in ChromaDB for future RAG retrieval.
    """
    valid_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("embedding") and str(chunk.get("chunk_text", "")).strip()
    ]
    if not valid_chunks:
        logger.warning(
            "No valid embedded chunks to store for chatbot_id=%s document_id=%s",
            chatbot_id,
            document_id,
        )
        return 0

    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict[str, int]] = []

    for chunk in valid_chunks:
        chunk_index = int(chunk["chunk_index"])
        ids.append(build_chunk_id(document_id, chunk_index))
        documents.append(str(chunk["chunk_text"]))
        embeddings.append(list(chunk["embedding"]))
        metadatas.append(
            build_chunk_metadata(chatbot_id, document_id, chunk_index)
        )

    try:
        collection = get_knowledge_base_collection()
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(
            "Stored %s embedded chunks in ChromaDB for chatbot_id=%s document_id=%s",
            len(valid_chunks),
            chatbot_id,
            document_id,
        )
        return len(valid_chunks)
    except Exception as exc:
        logger.exception(
            "Failed to store chunks in ChromaDB for chatbot_id=%s document_id=%s",
            chatbot_id,
            document_id,
        )
        raise ChromaStorageError(
            "Failed to store document chunks in ChromaDB"
        ) from exc
