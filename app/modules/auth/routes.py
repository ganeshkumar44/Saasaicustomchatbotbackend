from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth import service
from app.modules.auth.schema import (
    ForgotPasswordEmailRequest,
    ForgotPasswordEmailSuccessResponse,
    ForgotPasswordResetRequest,
    ForgotPasswordResetSuccessResponse,
    ForgotPasswordVerifyCodeRequest,
    ForgotPasswordVerifyCodeSuccessResponse,
    SignupRequest,
    SignupSuccessResponse,
    VerifyEmailRequest,
    VerifyEmailSuccessResponse,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

signup_router = APIRouter(
    prefix="/v1",
    tags=["Authentication"],
)


@router.get("/")
def auth_welcome():
    return {
        "status": True,
        "message": "Auth Module Working",
    }


@signup_router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignupSuccessResponse,
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    try:
        return service.register_user(db, payload)
    except service.PasswordMismatchError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Passwords do not match",
            },
        )
    except service.EmailAlreadyRegisteredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Email already registered",
            },
        )


@signup_router.post(
    "/signup-verification",
    status_code=status.HTTP_200_OK,
    response_model=VerifyEmailSuccessResponse,
)
def signup_verification(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        return service.verify_user_email(db, payload)
    except service.EmailAlreadyVerifiedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Email is already verified",
            },
        )
    except service.ExpiredVerificationCodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Verification code has expired",
            },
        )
    except service.InvalidVerificationCodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Invalid verification code",
            },
        )


@signup_router.post(
    "/verify-forgot-password-email",
    status_code=status.HTTP_200_OK,
    response_model=ForgotPasswordEmailSuccessResponse,
)
def verify_forgot_password_email(
    payload: ForgotPasswordEmailRequest,
    db: Session = Depends(get_db),
):
    try:
        return service.request_forgot_password_code(db, payload)
    except service.EmailNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Email not found",
            },
        )


@signup_router.post(
    "/verify-forgot-password-uniquecode",
    status_code=status.HTTP_200_OK,
    response_model=ForgotPasswordVerifyCodeSuccessResponse,
)
def verify_forgot_password_uniquecode(
    payload: ForgotPasswordVerifyCodeRequest,
    db: Session = Depends(get_db),
):
    try:
        return service.verify_forgot_password_code(db, payload)
    except service.ExpiredVerificationCodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Verification code has expired",
            },
        )
    except service.InvalidVerificationCodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Invalid verification code",
            },
        )


@signup_router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    response_model=ForgotPasswordResetSuccessResponse,
)
def forgot_password(payload: ForgotPasswordResetRequest, db: Session = Depends(get_db)):
    try:
        return service.reset_forgot_password(db, payload)
    except service.ForgotPasswordNotVerifiedError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Please verify your verification code first",
            },
        )
    except service.PasswordMismatchError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Passwords do not match",
            },
        )
    except service.EmailNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Email not found",
            },
        )
