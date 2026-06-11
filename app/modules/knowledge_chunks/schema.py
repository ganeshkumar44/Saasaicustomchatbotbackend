from datetime import datetime

from pydantic import BaseModel


class CreateKnowledgeChunkRequest(BaseModel):
    """Request payload for creating a knowledge chunk."""

    chatbot_id: int
    document_id: int
    chunk_text: str
    chunk_index: int
    character_count: int


class KnowledgeChunkResponse(BaseModel):
    """Knowledge chunk data for future API responses."""

    id: int
    chatbot_id: int
    document_id: int
    chunk_text: str
    chunk_index: int
    character_count: int
    created_at: datetime
