"""
Sentence Transformer model client.

Loads the embedding model from the local HuggingFace cache by default so live
servers never attempt outbound downloads to huggingface.co.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingModelLoadError(RuntimeError):
    """Raised when the embedding model cannot be loaded from local files."""


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the embedding model for reuse across requests."""
    settings = get_settings()
    model_name = settings.EMBEDDING_MODEL_NAME
    local_files_only = settings.EMBEDDING_LOCAL_FILES_ONLY
    cache_folder = settings.EMBEDDING_CACHE_FOLDER or None

    if local_files_only:
        # Force offline mode so transformers/huggingface_hub skip Hub calls.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    logger.info(
        "Loading embedding model=%s local_files_only=%s cache_folder=%s",
        model_name,
        local_files_only,
        cache_folder or "(default)",
    )

    try:
        model = SentenceTransformer(
            model_name,
            cache_folder=cache_folder,
            local_files_only=local_files_only,
        )
    except Exception as exc:
        if local_files_only:
            raise EmbeddingModelLoadError(
                "Embedding model is not available locally. "
                "Pre-download "
                f"'{model_name}' on a machine with internet, then deploy the "
                "HuggingFace cache to this server. "
                "Set EMBEDDING_LOCAL_FILES_ONLY=false only for one-time download."
            ) from exc
        raise

    logger.info("Embedding model loaded successfully: %s", model_name)
    return model
