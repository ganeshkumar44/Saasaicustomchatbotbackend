"""
AI answer generation schemas.
"""

from pydantic import BaseModel, Field


class AITestAnswerRequest(BaseModel):
    chatbot_id: int
    question: str = Field(min_length=1)


class AITestAnswerResponse(BaseModel):
    success: bool = True
    question: str
    answer: str
