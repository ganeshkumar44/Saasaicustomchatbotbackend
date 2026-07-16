from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.chatbot.service import (
    ChatbotNotFoundError,
    ChatbotPermissionError,
    SuperAdminChatbotProtectedError,
)
from app.modules.chatbot_analysis import service
from app.modules.chatbot_analysis.schema import (
    ChatbotAnalyticsSuccessResponse,
    MergedChatbotAnalyticsSuccessResponse,
)
from app.modules.graphs import service as graphs_service
from app.modules.graphs.schema import (
    ChartSuccessResponse,
    ResolutionChartSuccessResponse,
    ResponseTimeChartSuccessResponse,
)
from app.modules.graphs.utils import DEFAULT_DATE_RANGE, InvalidDateRangeError
from fastapi import Query

router = APIRouter(
    prefix="/v1",
    tags=["Chatbot Analysis"],
)


def _chatbot_access_error_response(exc: Exception) -> JSONResponse | None:
    if isinstance(exc, ChatbotNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.CHATBOT_NOT_FOUND},
        )
    if isinstance(exc, ChatbotPermissionError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.UNAUTHORIZED_CHATBOT_ACCESS},
        )
    if isinstance(exc, SuperAdminChatbotProtectedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.SUPERADMIN_CHATBOT_PROTECTED},
        )
    if isinstance(exc, service.ChatbotAnalyticsNotAvailableError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    return None


@router.get(
    "/analysis/details",
    status_code=status.HTTP_200_OK,
    response_model=ChatbotAnalyticsSuccessResponse,
)
def get_chatbot_analytics_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return chatbot analytics from the chat_analysis table for the dashboard."""
    return service.get_chatbot_analytics_details(db, current_user)


@router.get(
    "/analysis/merge-details",
    status_code=status.HTTP_200_OK,
    response_model=MergedChatbotAnalyticsSuccessResponse,
)
def get_merged_chatbot_analytics_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return merged chatbot analytics for the dashboard overview page."""
    return service.get_merged_chatbot_analytics_details(db, current_user)


@router.get(
    "/chatbots/{chatbot_id}/analytics",
    status_code=status.HTTP_200_OK,
    response_model=MergedChatbotAnalyticsSuccessResponse,
)
def get_single_chatbot_analytics(
    chatbot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return analytics for a single chatbot using the global analytics response shape."""
    try:
        return service.get_single_chatbot_analytics(db, current_user, chatbot_id)
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        service.ChatbotAnalyticsNotAvailableError,
    ) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.get(
    "/chatbots/{chatbot_id}/analytics/conversations-chart",
    status_code=status.HTTP_200_OK,
    response_model=ChartSuccessResponse,
)
def get_chatbot_conversations_chart(
    chatbot_id: int,
    date_range: str = Query(default=DEFAULT_DATE_RANGE, alias="range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return conversation chart data scoped to one chatbot."""
    try:
        return graphs_service.get_conversations_chart(
            db,
            current_user,
            date_range,
            chatbot_id=chatbot_id,
        )
    except InvalidDateRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        service.ChatbotAnalyticsNotAvailableError,
    ) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.get(
    "/chatbots/{chatbot_id}/analytics/users-chart",
    status_code=status.HTTP_200_OK,
    response_model=ChartSuccessResponse,
)
def get_chatbot_users_chart(
    chatbot_id: int,
    date_range: str = Query(default=DEFAULT_DATE_RANGE, alias="range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return users chart data scoped to one chatbot."""
    try:
        return graphs_service.get_users_chart(
            db,
            current_user,
            date_range,
            chatbot_id=chatbot_id,
        )
    except InvalidDateRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        service.ChatbotAnalyticsNotAvailableError,
    ) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.get(
    "/chatbots/{chatbot_id}/analytics/resolution-chart",
    status_code=status.HTTP_200_OK,
    response_model=ResolutionChartSuccessResponse,
)
def get_chatbot_resolution_chart(
    chatbot_id: int,
    date_range: str = Query(default=DEFAULT_DATE_RANGE, alias="range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return resolution chart data scoped to one chatbot."""
    try:
        return graphs_service.get_resolution_chart(
            db,
            current_user,
            date_range,
            chatbot_id=chatbot_id,
        )
    except InvalidDateRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        service.ChatbotAnalyticsNotAvailableError,
    ) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise


@router.get(
    "/chatbots/{chatbot_id}/analytics/response-time-chart",
    status_code=status.HTTP_200_OK,
    response_model=ResponseTimeChartSuccessResponse,
)
def get_chatbot_response_time_chart(
    chatbot_id: int,
    date_range: str = Query(default=DEFAULT_DATE_RANGE, alias="range"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return response-time chart data scoped to one chatbot."""
    try:
        return graphs_service.get_response_time_chart(
            db,
            current_user,
            date_range,
            chatbot_id=chatbot_id,
        )
    except InvalidDateRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except (
        ChatbotNotFoundError,
        ChatbotPermissionError,
        SuperAdminChatbotProtectedError,
        service.ChatbotAnalyticsNotAvailableError,
    ) as exc:
        response = _chatbot_access_error_response(exc)
        if response is not None:
            return response
        raise
