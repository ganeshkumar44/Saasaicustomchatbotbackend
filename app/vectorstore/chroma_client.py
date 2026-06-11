"""
ChromaDB client configuration.
"""

from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import get_settings
from app.vectorstore.utils import KNOWLEDGE_BASE_COLLECTION


def get_chroma_db_path() -> Path:
    """Return the persistent ChromaDB storage directory."""
    settings = get_settings()
    return Path(settings.CHROMA_DB_PATH)


@lru_cache
def get_chroma_client() -> ClientAPI:
    """Return a cached persistent ChromaDB client."""
    chroma_path = get_chroma_db_path()
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_path))


def get_knowledge_base_collection() -> Collection:
    """Return the shared knowledge base collection, creating it if needed."""
    client = get_chroma_client()
    return client.get_or_create_collection(name=KNOWLEDGE_BASE_COLLECTION)
