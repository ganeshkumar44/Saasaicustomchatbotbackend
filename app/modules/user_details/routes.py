from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_auth_context, AuthContext
from app.modules.auth.utils import get_token_identifier
from app.modules.login_history import service as login_history_service
from app.modules.login_history.schema import UserLoginHistorySuccessResponse
from app.modules.auth.model import User
from app.modules.user_details import service
from app.modules.user_plan.schema import UserPlanBillingSuccessResponse
from app.modules.user_plan.service import UserPlanNotFoundError, get_user_plan_details
from app.modules.user_details.schema import (
    ActivateAccountRequest,
    ActivateAccountSuccessResponse,
    DeactivateAccountRequest,
    DeactivateAccountSuccessResponse,
    DeleteAccountRequest,
    DeleteAccountSuccessResponse,
    RemoveProfilePictureSuccessResponse,
    UpdatePasswordRequest,
    UpdatePasswordSuccessResponse,
    UpdateUserDetailsRequest,
    UpdateUserDetailsSuccessResponse,
    UserDetailsSuccessResponse,
)

router = APIRouter(
    prefix="/v1",
    tags=["User Details"],
)


def _optional_form_value(value) -> str | None:
    """Normalize optional multipart form values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _update_user_details_json_openapi_schema() -> dict:
    """Build an inline OpenAPI schema for JSON update-user-details requests."""
    schema = UpdateUserDetailsRequest.model_json_schema()
    schema.pop("$defs", None)
    schema.pop("title", None)
    return schema


_UPDATE_USER_DETAILS_OPENAPI_BODY = {
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
                        "profile_image": {
                            "type": "string",
                            "format": "binary",
                        },
                    },
                }
            },
            "application/json": {
                "schema": _update_user_details_json_openapi_schema(),
            },
        }
    }
}


@router.get(
    "/user-details",
    status_code=status.HTTP_200_OK,
    response_model=UserDetailsSuccessResponse,
)
def get_user_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the complete profile of the currently logged-in user."""
    return service.get_user_details(db, current_user)


@router.get(
    "/user/plans",
    status_code=status.HTTP_200_OK,
    response_model=UserPlanBillingSuccessResponse,
)
def get_user_subscription_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's current subscription billing details."""
    try:
        return UserPlanBillingSuccessResponse(
            message=messages.USER_SUBSCRIPTION_DETAILS_RETRIEVED_SUCCESS,
            data=get_user_plan_details(db, current_user.id),
        )
    except UserPlanNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": exc.message,
            },
        )


@router.get(
    "/user-details/login-history",
    status_code=status.HTTP_200_OK,
    response_model=UserLoginHistorySuccessResponse,
)
def get_user_login_history(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Return the authenticated user's login history for the last five days."""
    current_jwt_id = get_token_identifier(auth.payload, auth.token)
    return login_history_service.get_user_login_history(
        db,
        auth.user,
        current_jwt_id=current_jwt_id,
    )


@router.put(
    "/update-password",
    status_code=status.HTTP_200_OK,
    response_model=UpdatePasswordSuccessResponse,
)
def update_password(
    payload: UpdatePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the authenticated user's password."""
    try:
        return service.update_password(db, current_user, payload)
    except service.UserDetailsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.CurrentPasswordInvalidError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.CURRENT_PASSWORD_INVALID,
            },
        )
    except service.NewPasswordSameAsCurrentError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.NEW_PASSWORD_SAME_AS_CURRENT,
            },
        )
    except service.NewPasswordTooSimilarError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.NEW_PASSWORD_TOO_SIMILAR,
            },
        )


@router.put(
    "/update-user-details",
    status_code=status.HTTP_200_OK,
    response_model=UpdateUserDetailsSuccessResponse,
    openapi_extra=_UPDATE_USER_DETAILS_OPENAPI_BODY,
)
async def update_user_details(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the authenticated user's profile information."""
    content_type = request.headers.get("content-type", "")
    profile_image = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        profile_image = form.get("profile_image")
        if profile_image is not None and not getattr(profile_image, "filename", None):
            profile_image = None

        payload = UpdateUserDetailsRequest(
            first_name=str(form.get("first_name") or ""),
            last_name=str(form.get("last_name") or ""),
            email=str(form.get("email") or ""),
            mobile=str(form.get("mobile") or ""),
            company=_optional_form_value(form.get("company")),
            website=_optional_form_value(form.get("website")),
            language=str(form.get("language") or ""),
            bio=_optional_form_value(form.get("bio")),
        )
    else:
        body = await request.json()
        payload = UpdateUserDetailsRequest(**body)

    try:
        return await service.update_user_details(
            db,
            current_user,
            payload,
            profile_image,  # type: ignore[arg-type]
        )
    except service.UserDetailsValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.ProfileImageUploadError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.EmailAlreadyInUseError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.EMAIL_ALREADY_EXISTS,
            },
        )
    except service.MobileAlreadyInUseError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.MOBILE_ALREADY_EXISTS,
            },
        )


@router.delete(
    "/remove-profile-picture",
    status_code=status.HTTP_200_OK,
    response_model=RemoveProfilePictureSuccessResponse,
)
def remove_profile_picture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the authenticated user's profile picture."""
    try:
        return service.remove_profile_picture(db, current_user)
    except service.UserProfileNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.USER_PROFILE_NOT_FOUND,
            },
        )
    except service.ProfilePictureNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.PROFILE_PICTURE_NOT_FOUND,
            },
        )
    except service.ProfileImageDeleteError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": exc.message,
            },
        )


@router.delete(
    "/delete-account",
    status_code=status.HTTP_200_OK,
    response_model=DeleteAccountSuccessResponse,
)
def delete_account(
    payload: DeleteAccountRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the authenticated user's account or another account (admin)."""
    try:
        return service.delete_account(db, current_user, payload)
    except service.UnauthorizedAccountActionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.UNAUTHORIZED_ACTION,
            },
        )
    except service.TargetUserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.USER_NOT_FOUND,
            },
        )
    except service.AccountAlreadyDeletedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.ACCOUNT_ALREADY_DELETED,
            },
        )


@router.put(
    "/deactivate-account",
    status_code=status.HTTP_200_OK,
    response_model=DeactivateAccountSuccessResponse,
)
def deactivate_account(
    payload: DeactivateAccountRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate the authenticated user's account or another account (admin)."""
    try:
        return service.deactivate_account(db, current_user, payload)
    except service.UnauthorizedAccountActionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.UNAUTHORIZED_ACTION,
            },
        )
    except service.TargetUserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.USER_NOT_FOUND,
            },
        )
    except service.AccountAlreadyDeactivatedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.ACCOUNT_ALREADY_DEACTIVATED,
            },
        )
    except service.AccountAlreadyDeletedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.ACCOUNT_ALREADY_DELETED,
            },
        )


@router.put(
    "/activate-account",
    status_code=status.HTTP_200_OK,
    response_model=ActivateAccountSuccessResponse,
)
def activate_account(
    payload: ActivateAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate a user account (administrator only)."""
    try:
        return service.activate_account(db, current_user, payload)
    except service.AdminAccessRequiredError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": messages.ADMIN_ACCESS_REQUIRED,
            },
        )
    except service.TargetUserNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": messages.USER_NOT_FOUND,
            },
        )
    except service.AccountAlreadyActiveError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.ACCOUNT_ALREADY_ACTIVATED,
            },
        )
