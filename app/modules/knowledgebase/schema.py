from pydantic import BaseModel


class KnowledgebaseUploadData(BaseModel):
    chatbot_id: int
    total_sources: int
    processed_sources: int


class KnowledgebaseUploadSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: KnowledgebaseUploadData
