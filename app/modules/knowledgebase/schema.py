from pydantic import BaseModel


class KnowledgebaseUploadData(BaseModel):
    chatbot_id: int
    total_sources: int
    processed_sources: int
    total_chunks: int = 0


class KnowledgebaseUploadSuccessResponse(BaseModel):
    success: bool = True
    message: str
    status: str
    data: KnowledgebaseUploadData


class KnowledgebaseProcessingStatusResponse(BaseModel):
    success: bool = True
    status: str
    error: str | None = None
