from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.graphs import service
from app.modules.graphs.schema import ChartSuccessResponse
from app.modules.graphs.utils import DEFAULT_DATE_RANGE, InvalidDateRangeError

router = APIRouter(
    prefix="/v1",
    tags=["Graphs"],
)


@router.get(
    "/analysis/conversations-chart",
    status_code=status.HTTP_200_OK,
    response_model=ChartSuccessResponse,
)
def get_conversations_chart(
    date_range: str = Query(default=DEFAULT_DATE_RANGE, alias="range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return conversation counts grouped by the selected chart period."""
    try:
        return service.get_conversations_chart(db, current_user, date_range)
    except InvalidDateRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )


@router.get(
    "/analysis/users-chart",
    status_code=status.HTTP_200_OK,
    response_model=ChartSuccessResponse,
)
def get_users_chart(
    date_range: str = Query(default=DEFAULT_DATE_RANGE, alias="range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return unique visitor counts grouped by the selected chart period."""
    try:
        return service.get_users_chart(db, current_user, date_range)
    except InvalidDateRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
