"""
Embedding generation service.
"""

import logging
from typing import Any

from app.embeddings.embedding_client import get_embedding_model

logger = logging.getLogger(__name__)


def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for a single text input."""
    model = get_embedding_model()
    embedding = model.encode(text.strip(), convert_to_numpy=True)
    return embedding.tolist()


def generate_embeddings_for_chunks(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate embeddings for document chunks.

    Empty or invalid chunks are skipped. Failures for individual chunks are
    logged and skipped so the remaining chunks can continue processing.
    """
    embedded_chunks: list[dict[str, Any]] = []

    for chunk in chunks:
        chunk_index = chunk.get("chunk_index")
        chunk_text = str(chunk.get("chunk_text", "")).strip()

        if not chunk_text:
            logger.warning("Skipping empty chunk with index=%s", chunk_index)
            continue

        try:
            embedding = generate_embedding(chunk_text)
            embedded_chunk: dict[str, Any] = {
                "chunk_index": int(chunk_index),
                "chunk_text": chunk_text,
                "embedding": embedding,
            }
            if "character_count" in chunk:
                embedded_chunk["character_count"] = int(chunk["character_count"])
            embedded_chunks.append(embedded_chunk)
        except Exception:
            logger.exception(
                "Failed to generate embedding for chunk_index=%s",
                chunk_index,
            )
            continue

    logger.info(
        "Generated embeddings for %s of %s chunks",
        len(embedded_chunks),
        len(chunks),
    )
    return embedded_chunks
