"""
ChromaDB similarity search for knowledge base retrieval.
"""

import logging

from app.embeddings.embedding_service import generate_embedding
from app.rag.utils import distance_to_similarity_score, normalize_query
from app.vectorstore.chroma_client import get_knowledge_base_collection

logger = logging.getLogger(__name__)


class QueryRequiredError(Exception):
    """Raised when the search query is missing or empty."""


class ChromaSearchError(Exception):
    """Raised when ChromaDB similarity search fails."""


def generate_query_embedding(query: str) -> list[float]:
    """Generate an embedding vector for a user search query."""
    normalized_query = normalize_query(query)
    if not normalized_query:
        raise QueryRequiredError()
    return generate_embedding(normalized_query)


def format_search_results(
    query_result: dict,
) -> list[dict[str, int | float | str]]:
    """Format ChromaDB query output into ranked search results."""
    if not query_result or not query_result.get("ids"):
        return []

    ids = query_result.get("ids", [[]])[0]
    documents = query_result.get("documents", [[]])[0]
    metadatas = query_result.get("metadatas", [[]])[0]
    distances = query_result.get("distances", [[]])[0]

    formatted_results: list[dict[str, int | float | str]] = []

    for index, _chunk_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        document = documents[index] if index < len(documents) else ""
        distance = distances[index] if index < len(distances) else 1.0

        if not document or not metadata:
            continue

        formatted_results.append(
            {
                "chunk_text": str(document),
                "document_id": int(metadata.get("document_id", 0)),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "similarity_score": distance_to_similarity_score(float(distance)),
            }
        )

    formatted_results.sort(
        key=lambda item: float(item["similarity_score"]),
        reverse=True,
    )
    return formatted_results


def query_chromadb(
    chatbot_id: int,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, int | float | str]]:
    """Run a similarity search in ChromaDB scoped to a chatbot."""
    try:
        collection = get_knowledge_base_collection()
        query_result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"chatbot_id": chatbot_id},
            include=["documents", "metadatas", "distances"],
        )
        return format_search_results(query_result)
    except Exception as exc:
        logger.exception(
            "ChromaDB search failed for chatbot_id=%s",
            chatbot_id,
        )
        raise ChromaSearchError("Failed to search knowledge base in ChromaDB") from exc
