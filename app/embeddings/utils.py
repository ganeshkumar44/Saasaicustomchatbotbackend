"""
Embedding helper utilities.
"""

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def is_valid_chunk_text(chunk_text: str) -> bool:
    """Return True when chunk text is non-empty after trimming."""
    return bool(chunk_text and chunk_text.strip())
