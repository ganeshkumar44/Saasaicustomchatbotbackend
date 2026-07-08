"""Knowledge base module exceptions."""


class KnowledgeBaseStorageError(Exception):
    """Raised when knowledge base file storage operations fail."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
