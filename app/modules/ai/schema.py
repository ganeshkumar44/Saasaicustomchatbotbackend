"""
AI answer generation schemas.
"""

from pydantic import BaseModel, Field


class AITestAnswerRequest(BaseModel):
    chatbot_id: int
    question: str = Field(min_length=1)
    session_id: int | None = Field(
        default=None,
        description=(
            "Optional Playground session id. When provided, the turn is stored "
            "in playground_messages and conversation memory uses that session."
        ),
    )


class AITestAnswerResponse(BaseModel):
    success: bool = True
    question: str
    answer: str
