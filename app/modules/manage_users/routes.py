"""
Manage Users module API routes.
"""

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.manage_users import service
from app.modules.manage_users.schema import (
    ManageUserDetailSuccessResponse,
    ManageUsersListSuccessResponse,
    UpdateManageUserRequest,
    UpdateManageUserSuccessResponse,
    UpdateUserRoleRequest,
    UpdateUserRoleSuccessResponse,
    UpdateUserStatusRequest,
    UpdateUserStatusSuccessResponse,
)
from app.modules.manage_users.utils import DEFAULT_PAGE, DEFAULT_PER_PAGE
from app.modules.user_details.utils import require_admin_user, require_superadmin

router = APIRouter(
    prefix="/v1",
    tags=["Manage Users"],
)


def _optional_form_value(value) -> str | None:
    """Normalize optional multipart form values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _update_manage_user_json_openapi_schema() -> dict:
    """Build an inline OpenAPI schema for JSON manage-user update requests."""
    schema = UpdateManageUserRequest.model_json_schema()
    schema.pop("$defs", None)
    schema.pop("title", None)
    return schema


_UPDATE_MANAGE_USER_OPENAPI_BODY = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": [
                        "first_name",
                        "last_name",
                        "email",
                        "mobile",
                        "language",
                        "role",
                    ],
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "mobile": {"type": "string"},
                        "company": {"type": "string"},
                        "website": {"type": "string"},
                        "language": {"type": "string"},
                        "bio": {"type": "string"},
                        "role": {"type": "string"},
                        "profile_image": {
                            "type": "string",
                            "format": "binary",
                        },
                    },
                }
            },
            "application/json": {
                "schema": _update_manage_user_json_openapi_schema(),
            },
        }
    }
}


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


@router.get(
    "/manage-users/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=ManageUserDetailSuccessResponse,
)
def get_manage_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    """Return complete profile details for a single user (administrator only)."""
    try:
        return service.get_user_detail(db, current_user, user_id)
    except service.UserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.USER_NOT_FOUND},
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
    except service.CannotManageSuperAdminError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.CANNOT_MANAGE_SUPERADMIN},
        )


@router.put(
    "/manage-users/{user_id}/role",
    status_code=status.HTTP_200_OK,
    response_model=UpdateUserRoleSuccessResponse,
)
def update_manage_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Promote or demote a user's role (SuperAdmin only)."""
    try:
        return service.update_user_role(db, current_user, user_id, payload)
    except service.ManageUsersValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except service.CannotModifySuperAdminError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.CANNOT_MODIFY_SUPERADMIN},
        )
    except service.UserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.USER_NOT_FOUND},
        )


@router.put(
    "/manage-users/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UpdateManageUserSuccessResponse,
    openapi_extra=_UPDATE_MANAGE_USER_OPENAPI_BODY,
)
async def update_manage_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
):
    """Update any user's profile fields (administrator only)."""
    content_type = request.headers.get("content-type", "")
    profile_image = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        profile_image = form.get("profile_image")
        if profile_image is not None and not getattr(profile_image, "filename", None):
            profile_image = None

        payload = UpdateManageUserRequest(
            first_name=str(form.get("first_name") or ""),
            last_name=str(form.get("last_name") or ""),
            email=str(form.get("email") or ""),
            mobile=str(form.get("mobile") or ""),
            company=_optional_form_value(form.get("company")),
            website=_optional_form_value(form.get("website")),
            language=str(form.get("language") or ""),
            bio=_optional_form_value(form.get("bio")),
            role=str(form.get("role") or ""),
        )
    else:
        body = await request.json()
        payload = UpdateManageUserRequest(**body)

    try:
        return await service.update_user(
            db,
            current_user,
            user_id,
            payload,
            profile_image,  # type: ignore[arg-type]
        )
    except service.ManageUsersValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    except service.ProfileImageUploadError as exc:
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
    except service.RoleChangeForbiddenError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.ONLY_SUPERADMIN_CAN_ASSIGN_ADMIN},
        )
    except service.CannotManageSuperAdminError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": messages.CANNOT_MANAGE_SUPERADMIN},
        )
    except service.CannotModifySuperAdminError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": messages.SUPERADMIN_ROLE_PROTECTED},
        )
    except service.UserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": messages.USER_NOT_FOUND},
        )
