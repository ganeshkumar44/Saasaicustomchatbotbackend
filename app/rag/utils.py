"""
RAG search helper utilities.
"""


def distance_to_similarity_score(distance: float) -> float:
    """
    Convert a ChromaDB distance value into a similarity score between 0 and 1.

    ChromaDB returns lower distances for more similar vectors. This helper
    converts cosine-style distances into a higher-is-better score.
    """
    return max(0.0, min(1.0, round(1.0 - distance, 4)))


def normalize_query(query: str) -> str:
    """Normalize and validate a search query string."""
    return query.strip()


def merge_chunk_texts(chunk_texts: list[str]) -> str:
    """Merge retrieved chunk texts into a single context string."""
    return "\n\n".join(text for text in chunk_texts if text.strip())
