"""
Shared FastAPI authentication dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import messages
from app.core.database import get_db
from app.core.security import (
    InvalidTokenError,
    TokenBlacklistedError,
    TokenExpiredError,
    decode_access_token,
)
from app.modules.auth.model import User

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    """Authenticated request context including the validated user and token."""

    user: User
    token: str
    payload: dict[str, Any]


def _raise_unauthorized(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "success": False,
            "message": message,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    """
    Validate the Bearer token, ensure it is not blacklisted, and return context.
    """
    if credentials is None or not credentials.credentials.strip():
        logger.warning("Authentication failed: missing bearer token")
        _raise_unauthorized(messages.TOKEN_REQUIRED)

    token = credentials.credentials.strip()

    try:
        payload = decode_access_token(token, db=db)
        user = db.get(User, payload["user_id"])
    except TokenExpiredError:
        logger.warning("Authentication failed: token expired")
        _raise_unauthorized(messages.TOKEN_EXPIRED)
    except TokenBlacklistedError:
        logger.warning("Authentication failed: token blacklisted")
        _raise_unauthorized(messages.TOKEN_BLACKLISTED)
    except (InvalidTokenError, KeyError, TypeError):
        logger.warning("Authentication failed: invalid token")
        _raise_unauthorized(messages.INVALID_TOKEN)

    if not user or not user.is_active:
        logger.warning(
            "Authentication failed: user not found or inactive user_id=%s",
            payload.get("user_id"),
        )
        _raise_unauthorized(messages.UNAUTHORIZED)

    return AuthContext(user=user, token=token, payload=payload)


def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> User:
    """FastAPI dependency that returns the authenticated user."""
    return auth.user
