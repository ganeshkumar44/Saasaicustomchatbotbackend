"""
RAG search schemas.
"""

from pydantic import BaseModel, Field


class RAGSearchResultItem(BaseModel):
    chunk_text: str
    document_id: int
    chunk_index: int
    similarity_score: float
    source_name: str | None = None
    source_url: str | None = None
    source_type: str | None = None


class RAGTestSearchRequest(BaseModel):
    chatbot_id: int
    query: str = Field(min_length=1)


class RAGTestSearchResponse(BaseModel):
    success: bool = True
    results: list[RAGSearchResultItem]


class ContextRequest(BaseModel):
    chatbot_id: int
    query: str = Field(min_length=1)


class ContextResponse(BaseModel):
    success: bool = True
    question: str
    total_chunks: int
    context_length: int
    context: str
