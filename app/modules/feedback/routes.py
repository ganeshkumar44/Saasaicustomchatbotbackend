"""Website feedback API routes."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.feedback import service
from app.modules.feedback.schema import (
    CreateFeedbackRequest,
    CreateFeedbackSuccessResponse,
)
from app.modules.login_history.utils import get_client_ip

router = APIRouter(
    prefix="/v1",
    tags=["Feedback"],
)


@router.post(
    "/feedback",
    status_code=status.HTTP_200_OK,
    response_model=CreateFeedbackSuccessResponse,
    summary="Submit website feedback",
)
def submit_feedback(
    payload: CreateFeedbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept authenticated website feedback and persist it."""
    try:
        return service.create_feedback(
            db,
            current_user,
            payload,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    except service.FeedbackValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
