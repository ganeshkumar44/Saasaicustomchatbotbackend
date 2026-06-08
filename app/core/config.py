"""
Application configuration loaded from environment variables.

All sensitive values (e.g. database password) must be set in a .env file
or exported in the environment — never hard-coded in source code.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Always load .env from the project root, regardless of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Centralized application settings backed by environment variables."""

    def __init__(self) -> None:
        self.DB_HOST: str = os.getenv("DB_HOST", "localhost")
        self.DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
        self.DB_NAME: str = os.getenv("DB_NAME", "saas_aicustom_chatbot")
        self.DB_USER: str = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

        self.DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
        self.DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))

    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy PostgreSQL connection URL."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def validate(self) -> None:
        """Raise a clear error when required settings are missing."""
        if not self.DB_PASSWORD or self.DB_PASSWORD == "your_postgres_password_here":
            raise ValueError(
                "DB_PASSWORD is not set. Open .env in the project root and set "
                "DB_PASSWORD to your PostgreSQL password (the same one you use in pgAdmin4)."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    return Settings()
