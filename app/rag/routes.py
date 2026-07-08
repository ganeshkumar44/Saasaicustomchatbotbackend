"""
Temporary RAG development endpoints.

These routes are for internal testing only and will be replaced or removed
when RAG is integrated into the public widget chat flow.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.rag import rag_service
from app.rag.schema import (
    ContextRequest,
    ContextResponse,
    RAGTestSearchRequest,
    RAGTestSearchResponse,
)
from app.rag.search_service import QueryRequiredError

router = APIRouter(
    prefix="/v1",
    tags=["RAG (Temporary Test)"],
)


@router.post(
    "/rag/test-search",
    status_code=status.HTTP_200_OK,
    response_model=RAGTestSearchResponse,
    summary="Temporary RAG search test endpoint",
    description=(
        "Development-only endpoint for testing knowledge base retrieval. "
        "This endpoint is temporary and will be removed after widget chat RAG integration."
    ),
)
def test_rag_search(
    payload: RAGTestSearchRequest,
    db: Session = Depends(get_db),
):
    """Search the knowledge base and return top relevant chunks."""
    try:
        results = rag_service.search_knowledge_base(
            db,
            payload.chatbot_id,
            payload.query,
        )
        return RAGTestSearchResponse(results=results)
    except QueryRequiredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Query is required",
            },
        )


@router.post(
    "/rag/test-context",
    status_code=status.HTTP_200_OK,
    response_model=ContextResponse,
    summary="Temporary RAG context builder test endpoint",
    description=(
        "Development-only endpoint for testing merged RAG context before "
        "AI answer generation. This endpoint is temporary."
    ),
)
def test_rag_context(
    payload: ContextRequest,
    db: Session = Depends(get_db),
):
    """Build merged context from top knowledge base chunks for a question."""
    try:
        return rag_service.build_context(
            db,
            payload.chatbot_id,
            payload.query,
        )
    except QueryRequiredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Query is required",
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
