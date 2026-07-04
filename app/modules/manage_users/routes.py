"""
Manage Users module API routes.
"""

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.manage_users import service
from app.modules.manage_users.schema import (
    ManageUsersListSuccessResponse,
    UpdateManageUserRequest,
    UpdateManageUserSuccessResponse,
    UpdateUserStatusRequest,
    UpdateUserStatusSuccessResponse,
)
from app.modules.manage_users.utils import DEFAULT_PAGE, DEFAULT_PER_PAGE, require_admin_user

router = APIRouter(
    prefix="/v1",
    tags=["Manage Users"],
)


@router.get(
    "/manage-users",
    status_code=status.HTTP_200_OK,
    response_model=ManageUsersListSuccessResponse,
)
def get_manage_users(
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    """Return a paginated list of all users (administrator only)."""
    return service.list_users(
        db,
        current_user,
        page=page,
        per_page=per_page,
        search=search,
    )


@router.put(
    "/manage-users/{user_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=UpdateUserStatusSuccessResponse,
)
def update_manage_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    """Activate, deactivate, or delete a user account (administrator only)."""
    try:
        return service.update_user_status(db, current_user, user_id, payload)
    except service.ManageUsersValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except service.SelfActionNotAllowedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.SELF_ACTION_NOT_ALLOWED},
        )
    except service.UserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.USER_NOT_FOUND},
        )
    except service.AccountAlreadyActiveError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.ACCOUNT_ALREADY_ACTIVATED},
        )
    except service.AccountAlreadyDeactivatedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.ACCOUNT_ALREADY_DEACTIVATED},
        )
    except service.AccountAlreadyDeletedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.ACCOUNT_ALREADY_DELETED},
        )


@router.put(
    "/manage-users/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UpdateManageUserSuccessResponse,
)
def update_manage_user(
    user_id: int,
    payload: UpdateManageUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    """Update any user's profile fields (administrator only)."""
    try:
        return service.update_user(db, current_user, user_id, payload)
    except service.ManageUsersValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except service.EmailAlreadyInUseError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.EMAIL_ALREADY_EXISTS},
        )
    except service.MobileAlreadyInUseError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.MOBILE_ALREADY_EXISTS},
        )
    except service.UserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.USER_NOT_FOUND},
        )
