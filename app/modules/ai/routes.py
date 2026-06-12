"""
Temporary AI development endpoints.

These routes are for internal testing only and will be replaced or removed
when AI answer generation is integrated into the public widget chat flow.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ai import service
from app.modules.ai.schema import AITestAnswerRequest, AITestAnswerResponse
from app.modules.ai.utils import GeminiAPIError, GeminiAPIKeyMissingError
from app.rag import rag_service
from app.rag.search_service import QueryRequiredError

router = APIRouter(
    prefix="/v1",
    tags=["AI (Temporary Test)"],
)


@router.post(
    "/ai/test-answer",
    status_code=status.HTTP_200_OK,
    response_model=AITestAnswerResponse,
    summary="Temporary AI answer test endpoint",
    description=(
        "Development-only endpoint for testing the full RAG + Gemini pipeline. "
        "This endpoint is temporary and will be removed after widget chat integration."
    ),
)
def test_ai_answer(
    payload: AITestAnswerRequest,
    db: Session = Depends(get_db),
):
    """Generate an AI answer from knowledge base context and Gemini."""
    try:
        return service.generate_ai_answer(
            db,
            payload.chatbot_id,
            payload.question,
        )
    except (service.QuestionRequiredError, QueryRequiredError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Question is required",
            },
        )
    except rag_service.ChatbotNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Chatbot not found",
            },
        )
    except GeminiAPIKeyMissingError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Gemini API key is not configured",
            },
        )
    except GeminiAPIError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "message": "Failed to generate AI answer",
            },
        )
