"""Abstract base class for AI answer providers."""

from abc import ABC, abstractmethod


class BaseAIProvider(ABC):
    """Interface implemented by all AI answer providers."""

    @abstractmethod
    def generate_answer(self, prompt: str) -> str:
        """Generate an answer from a fully-built prompt containing context and question."""
