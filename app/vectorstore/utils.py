"""
Vector store helper utilities.
"""

KNOWLEDGE_BASE_COLLECTION = "knowledge_base"


def build_chunk_id(document_id: int, chunk_index: int) -> str:
    """Build a stable ChromaDB record ID for a document chunk."""
    return f"{document_id}_{chunk_index}"


def build_chunk_metadata(
    chatbot_id: int,
    document_id: int,
    chunk_index: int,
) -> dict[str, int]:
    """Build ChromaDB metadata for a knowledge chunk."""
    return {
        "chatbot_id": chatbot_id,
        "document_id": document_id,
        "chunk_index": chunk_index,
    }
