"""Lightweight BM25 keyword search over knowledge base chunks."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 scoring."""
    return _TOKEN_PATTERN.findall(text.lower())


class BM25Index:
    """In-memory BM25 index for a corpus of document strings."""

    def __init__(
        self,
        documents: list[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.tokenized = [tokenize(document) for document in documents]
        self.doc_lengths = [len(tokens) for tokens in self.tokenized]
        self.avgdl = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )
        self.n_docs = len(documents)
        document_frequency: Counter[str] = Counter()
        for tokens in self.tokenized:
            for term in set(tokens):
                document_frequency[term] += 1
        self.document_frequency = document_frequency

    def score(self, query: str) -> list[float]:
        """Return BM25 scores for every document in the index."""
        if not self.documents:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return [0.0] * len(self.documents)

        scores: list[float] = []
        for tokens, doc_length in zip(self.tokenized, self.doc_lengths, strict=False):
            term_frequency = Counter(tokens)
            doc_score = 0.0
            for term in query_tokens:
                frequency = term_frequency.get(term, 0)
                if frequency == 0:
                    continue
                df = self.document_frequency.get(term, 0)
                idf = math.log(
                    1.0 + (self.n_docs - df + 0.5) / (df + 0.5),
                )
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * doc_length / (self.avgdl or 1.0)
                )
                doc_score += idf * (frequency * (self.k1 + 1.0)) / denominator
            scores.append(doc_score)
        return scores


def normalize_scores(scores: list[float]) -> list[float]:
    """Normalize scores to the 0-1 range."""
    if not scores:
        return []
    max_score = max(scores)
    if max_score <= 0:
        return [0.0 for _ in scores]
    return [round(score / max_score, 4) for score in scores]


def search_bm25(
    query: str,
    documents: list[str],
    top_k: int,
) -> list[tuple[int, float]]:
    """
    Return top-k document indices with normalized BM25 scores.

    Each tuple is ``(corpus_index, normalized_score)``.
    """
    if not documents or not query.strip():
        return []

    index = BM25Index(documents)
    raw_scores = index.score(query)
    normalized = normalize_scores(raw_scores)
    ranked = sorted(
        enumerate(normalized),
        key=lambda item: item[1],
        reverse=True,
    )
    logger.info(
        "BM25 search returned %s candidates from corpus_size=%s",
        min(top_k, len(ranked)),
        len(documents),
    )
    return ranked[:top_k]
