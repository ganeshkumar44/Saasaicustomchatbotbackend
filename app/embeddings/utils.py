"""
Embedding helper utilities.
"""

from app.core.config import get_settings


def get_default_embedding_model_name() -> str:
    """Return the configured embedding model name."""
    return get_settings().EMBEDDING_MODEL_NAME


# Kept for backward compatibility with any imports of this constant.
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def is_valid_chunk_text(chunk_text: str) -> bool:
    """Return True when chunk text is non-empty after trimming."""
    return bool(chunk_text and chunk_text.strip())
