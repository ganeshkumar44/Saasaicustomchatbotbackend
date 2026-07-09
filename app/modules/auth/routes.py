from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.modules.auth import service
from app.modules.auth.schema import (
    ForgotPasswordEmailRequest,
    ForgotPasswordEmailSuccessResponse,
    ForgotPasswordResetRequest,
    ForgotPasswordResetSuccessResponse,
    ForgotPasswordVerifyCodeRequest,
    ForgotPasswordVerifyCodeSuccessResponse,
    LoginRequest,
    LoginSuccessResponse,
    MeSuccessResponse,
    SignOutSuccessResponse,
    SignupRequest,
    SignupResendVerificationRequest,
    SignupResendVerificationResponse,
    SignupSuccessResponse,
    VerifyEmailRequest,
    VerifyEmailSuccessResponse,
)
from app.core.dependencies import AuthContext, get_auth_context, get_current_user
from app.modules.login_history.utils import build_login_client_info

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
    except service.SignupValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.EmailAlreadyRegisteredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.EMAIL_ALREADY_EXISTS,
            },
        )
    except service.MobileAlreadyRegisteredError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": messages.MOBILE_ALREADY_EXISTS,
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
    except service.VerificationValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.EmailAlreadyVerifiedError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.ExpiredVerificationCodeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.InvalidVerificationCodeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )


@signup_router.post(
    "/signup-resend-verification",
    status_code=status.HTTP_200_OK,
    response_model=SignupResendVerificationResponse,
)
def signup_resend_verification(
    payload: SignupResendVerificationRequest,
    db: Session = Depends(get_db),
):
    try:
        return service.resend_signup_verification(db, payload)
    except service.VerificationValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.SignupResendUserNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.EmailAlreadyVerifiedError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.VerificationCodeNotExpiredError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
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


@signup_router.post(
    "/signin",
    status_code=status.HTTP_200_OK,
    response_model=LoginSuccessResponse,
)
def signin(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        return service.login_user(
            db,
            payload,
            client_info=build_login_client_info(request),
        )
    except service.SigninValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.LoginUserNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.LoginInvalidPasswordError as exc:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.EmailNotVerifiedForLoginError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": exc.message,
            },
        )
    except service.AccountDisabledError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "message": exc.message,
            },
        )


@signup_router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=MeSuccessResponse,
)
def get_me(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_current_user_profile(db, current_user)


@signup_router.post(
    "/signout",
    status_code=status.HTTP_200_OK,
    response_model=SignOutSuccessResponse,
)
def signout(
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Invalidate the current JWT access token and end the user session."""
    try:
        return service.signout_user(db, auth.user, auth.token, auth.payload)
    except service.SignoutError:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": messages.INTERNAL_SERVER_ERROR,
            },
        )
