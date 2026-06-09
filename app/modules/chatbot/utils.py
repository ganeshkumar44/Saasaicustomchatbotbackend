"""
Chatbot module helper utilities.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.model import User
from app.modules.auth.utils import InvalidTokenError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Return the authenticated user for chatbot builder endpoints.

    Raises 401 with a consistent error shape when the request is unauthenticated
    or the token is invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Authentication required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user = db.get(User, payload["user_id"])
    except (InvalidTokenError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Authentication required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Authentication required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def apply_chatbot_migrations(db_engine: Engine) -> None:
    """
    Align an existing chatbots table with the current ORM schema.

    create_all() only creates new tables; it does not alter existing ones.
    """
    inspector = inspect(db_engine)
    if "chatbots" not in inspector.get_table_names():
        return

    columns = inspector.get_columns("chatbots")
    existing_columns = {column["name"] for column in columns}
    nullable_columns = {
        column["name"]: column.get("nullable", True) for column in columns
    }
    statements: list[str] = []

    if "user_id" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN user_id INTEGER NOT NULL "
            "REFERENCES users(id) ON DELETE CASCADE"
        )
    if "chatbot_name" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN chatbot_name VARCHAR(255)"
        )
    if "description" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN description VARCHAR(1000)"
        )
    if "personality" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN personality VARCHAR(255)"
        )
    if "language" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN language VARCHAR(50)"
        )
    if "ai_model" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN ai_model VARCHAR(100)"
        )
    if "status" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN status VARCHAR(50) "
            "NOT NULL DEFAULT 'draft'"
        )
    if "created_at" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN created_at "
            "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
        )
    if "updated_at" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN updated_at "
            "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
        )

    # Draft builder fields must allow NULL until the user completes each step.
    for column_name in (
        "chatbot_name",
        "description",
        "personality",
        "language",
        "ai_model",
    ):
        if column_name in existing_columns and not nullable_columns.get(column_name, True):
            statements.append(
                f"ALTER TABLE chatbots ALTER COLUMN {column_name} DROP NOT NULL"
            )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
