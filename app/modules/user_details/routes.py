from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.user_details import service
from app.modules.user_details.schema import (
    ActivateAccountRequest,
    ActivateAccountSuccessResponse,
    DeactivateAccountRequest,
    DeactivateAccountSuccessResponse,
    DeleteAccountRequest,
    DeleteAccountSuccessResponse,
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


@router.put(
    "/update-user-details",
    status_code=status.HTTP_200_OK,
    response_model=UpdateUserDetailsSuccessResponse,
)
def update_user_details(
    payload: UpdateUserDetailsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the authenticated user's profile information."""
    try:
        return service.update_user_details(db, current_user, payload)
    except service.UserDetailsValidationError as exc:
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
