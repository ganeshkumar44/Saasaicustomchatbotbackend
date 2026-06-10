"""
Chatbot module helper utilities.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.chatbot.model import ChatbotSettings
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
    if "published_at" not in existing_columns:
        statements.append(
            "ALTER TABLE chatbots ADD COLUMN published_at TIMESTAMP WITH TIME ZONE"
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


DEFAULT_TYPING_INDICATOR = True
DEFAULT_PRIMARY_COLOR = "#000000"
DEFAULT_TEXT_COLOR = "#ffffff"
DEFAULT_WIDGET_POSITION = "bottom-right"
DEFAULT_SHOW_AVATAR = True
DEFAULT_CHAT_TITLE = "Chat with us"
DEFAULT_WELCOME_MESSAGE = (
    "Hi there! 👋 Welcome to our support chat. How can we assist you today?"
)
DEFAULT_INPUT_PLACEHOLDER = "Type your message..."


def get_widget_base_url() -> str:
    """Return the base URL used in generated embed code."""
    return get_settings().WIDGET_BASE_URL.rstrip("/")


def generate_public_key() -> str:
    """Generate a unique URL-safe public chatbot key."""
    return f"cb_{secrets.token_hex(6)}"


def generate_unique_public_key(db: Session) -> str:
    """Generate a public key that does not already exist in the database."""
    while True:
        public_key = generate_public_key()
        existing = db.execute(
            select(ChatbotSettings.id).where(ChatbotSettings.public_key == public_key)
        ).scalar_one_or_none()
        if existing is None:
            return public_key


def generate_embed_code(public_key: str) -> str:
    """Build the widget embed code for a published chatbot."""
    widget_url = f"{get_widget_base_url()}/static/widget.js"
    return (
        f"<script src='{widget_url}' "
        f"data-chatbot-key='{public_key}'></script>"
    )
