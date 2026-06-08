from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.auth.schema import SignupRequest, SignupSuccessResponse, SignupUserData
from app.modules.auth.utils import hash_password


class PasswordMismatchError(Exception):
    """Raised when password and confirm_password do not match."""


class EmailAlreadyRegisteredError(Exception):
    """Raised when the email is already associated with an account."""


def auth_service():
    return {
        "status": True,
        "message": "Auth Service Running",
    }


def register_user(db: Session, payload: SignupRequest) -> SignupSuccessResponse:
    """Register a new user with hashed password and default role/settings."""
    if payload.password != payload.confirm_password:
        raise PasswordMismatchError()

    existing_user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if existing_user:
        raise EmailAlreadyRegisteredError()

    user = User(
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip(),
        email=payload.email.lower(),
        mobile=payload.mobile,
        password_hash=hash_password(payload.password),
        role="user",
        is_email_verified=False,
        is_mobile_verified=False,
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegisteredError() from exc

    db.refresh(user)

    return SignupSuccessResponse(
        message="User registered successfully",
        data=SignupUserData(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name or None,
            email=user.email,
        ),
    )
