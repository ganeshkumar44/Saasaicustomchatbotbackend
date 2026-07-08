"""
JWT token creation, validation, and blacklist management.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.auth.model import TokenBlacklist

logger = logging.getLogger(__name__)


class InvalidTokenError(Exception):
    """Raised when a JWT is missing, malformed, or otherwise invalid."""


class TokenExpiredError(InvalidTokenError):
    """Raised when a JWT has expired."""


class TokenBlacklistedError(InvalidTokenError):
    """Raised when a JWT has been invalidated via sign-out."""


def _get_jwt_settings() -> dict[str, str | int]:
    """Read JWT configuration from application settings."""
    settings = get_settings()
    return {
        "secret_key": settings.JWT_SECRET_KEY,
        "algorithm": settings.JWT_ALGORITHM,
        "expire_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    }


def get_token_identifier(payload: dict[str, Any], raw_token: str) -> str:
    """
    Return the blacklist identifier for a token.

    New tokens use the JWT ``jti`` claim. Legacy tokens without ``jti`` fall
    back to a SHA-256 hash of the raw token string.
    """
    jti = payload.get("jti")
    if jti:
        return str(jti)
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, email: str, role: str) -> str:
    """Generate a signed JWT access token for the authenticated user."""
    jwt_settings = _get_jwt_settings()
    secret_key = str(jwt_settings["secret_key"])
    if not secret_key:
        raise ValueError("JWT_SECRET_KEY is not configured.")

    expire_minutes = int(jwt_settings["expire_minutes"])
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expire_minutes)
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": expires_at,
        "iat": now,
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=str(jwt_settings["algorithm"]),
    )


def get_jti_from_access_token(token: str) -> str | None:
    """Return the JWT identifier from a freshly issued access token."""
    try:
        payload = _decode_jwt_payload(token)
    except InvalidTokenError:
        return None

    jti = payload.get("jti")
    return str(jti) if jti else None


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token without blacklist checks."""
    jwt_settings = _get_jwt_settings()
    secret_key = str(jwt_settings["secret_key"])
    if not secret_key:
        raise InvalidTokenError()

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[str(jwt_settings["algorithm"])],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    if "user_id" not in payload:
        raise InvalidTokenError()

    return payload


def is_token_blacklisted(db: Session, jti: str) -> bool:
    """Return True when the token identifier is present in the active blacklist."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        select(TokenBlacklist.id).where(
            TokenBlacklist.jti == jti,
            TokenBlacklist.expires_at > now,
        )
    ).scalar_one_or_none()
    return result is not None


def blacklist_token(
    db: Session,
    user_id: int,
    jti: str,
    expires_at: datetime,
) -> None:
    """Persist a token identifier in the blacklist until its natural expiry."""
    existing = db.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == jti)
    ).scalar_one_or_none()
    if existing is not None:
        logger.info(
            "Token already blacklisted for user_id=%s jti=%s",
            user_id,
            jti,
        )
        return

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    entry = TokenBlacklist(
        user_id=user_id,
        jti=jti,
        expires_at=expires_at,
    )
    db.add(entry)
    db.commit()
    logger.info("Token blacklisted for user_id=%s jti=%s", user_id, jti)


def decode_access_token(token: str, db: Session | None = None) -> dict[str, Any]:
    """
    Decode and validate a JWT access token, including blacklist verification.
    """
    payload = _decode_jwt_payload(token)
    jti = get_token_identifier(payload, token)

    check_db = db
    close_db = False
    if check_db is None:
        check_db = SessionLocal()
        close_db = True

    try:
        if is_token_blacklisted(check_db, jti):
            logger.warning("Blacklisted token rejected jti=%s", jti)
            raise TokenBlacklistedError()
    finally:
        if close_db:
            check_db.close()

    return payload
