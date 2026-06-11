"""
Sentence Transformer model client.
"""

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the embedding model for reuse across requests."""
    model_name = get_settings().EMBEDDING_MODEL_NAME
    logger.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)
    logger.info("Embedding model loaded successfully: %s", model_name)
    return model
