"""Public contact API routes."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.contact import service
from app.modules.contact.schema import (
    CreateContactRequest,
    CreateContactSuccessResponse,
)
from app.modules.login_history.utils import get_client_ip

router = APIRouter(
    prefix="/v1",
    tags=["Contact"],
)


@router.post(
    "/contact",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateContactSuccessResponse,
    summary="Submit landing-page contact / demo request",
)
def submit_contact(
    payload: CreateContactRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Accept an unauthenticated contact form submission and persist it."""
    try:
        return service.create_contact_submission(
            db,
            payload,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    except service.ContactValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
