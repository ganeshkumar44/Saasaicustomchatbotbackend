"""
Temporary AI development endpoints.

These routes are for internal testing only and will be replaced or removed
when AI answer generation is integrated into the public widget chat flow.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.ai import service
from app.modules.ai.schema import AITestAnswerRequest, AITestAnswerResponse
from app.modules.ai.exceptions import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiQuotaExceededError,
    OllamaModelUnavailableError,
    OllamaNotRunningError,
    OllamaProviderError,
    OpenAIAPIKeyMissingError,
    OpenAIAuthenticationError,
    OpenAINetworkError,
    OpenAIProviderError,
    OpenAIRateLimitError,
    OpenAIServiceUnavailableError,
    OpenAITimeoutError,
)
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
    except GeminiQuotaExceededError:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "AI_QUOTA_EXCEEDED",
                "message": messages.AI_QUOTA_EXCEEDED,
            },
        )
    except OllamaNotRunningError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error_code": "OLLAMA_NOT_RUNNING",
                "message": exc.message,
            },
        )
    except OllamaModelUnavailableError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error_code": "OLLAMA_MODEL_UNAVAILABLE",
                "message": exc.message,
            },
        )
    except OllamaProviderError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OLLAMA_PROVIDER_ERROR",
                "message": exc.message,
            },
        )
    except OpenAIAPIKeyMissingError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "OpenAI API key is not configured",
            },
        )
    except OpenAIAuthenticationError as exc:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error_code": "OPENAI_AUTHENTICATION_FAILED",
                "message": exc.message,
            },
        )
    except OpenAIRateLimitError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "OPENAI_RATE_LIMIT_EXCEEDED",
                "message": exc.message,
            },
        )
    except OpenAITimeoutError as exc:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "success": False,
                "error_code": "OPENAI_REQUEST_TIMEOUT",
                "message": exc.message,
            },
        )
    except OpenAINetworkError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OPENAI_NETWORK_ERROR",
                "message": exc.message,
            },
        )
    except OpenAIServiceUnavailableError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error_code": "OPENAI_SERVICE_UNAVAILABLE",
                "message": exc.message,
            },
        )
    except OpenAIProviderError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error_code": "OPENAI_PROVIDER_ERROR",
                "message": exc.message,
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
