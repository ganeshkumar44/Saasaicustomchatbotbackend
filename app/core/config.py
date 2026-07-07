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
        # PostgreSQL connection settings
        self.DB_HOST: str = os.getenv("DB_HOST", "localhost")
        self.DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
        self.DB_NAME: str = os.getenv("DB_NAME", "saas_aicustom_chatbot")
        self.DB_USER: str = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

        # SQLAlchemy connection pool tuning
        self.DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
        self.DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))

        # SMTP configuration for email verification
        self.SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER: str = os.getenv("SMTP_USER", "")
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
        self.SMTP_FROM: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))

        # JWT authentication settings
        self.JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )

        # Chatbot widget embed base URL
        self.WIDGET_BASE_URL: str = os.getenv(
            "WIDGET_BASE_URL", "http://127.0.0.1:8000"
        )

        # CORS allowed origins (comma-separated)
        cors_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        )
        self.CORS_ORIGINS: list[str] = [
            origin.strip() for origin in cors_origins.split(",") if origin.strip()
        ]

        # Default allowed domains saved to DB on chatbot publish (comma-separated)
        self.DEFAULT_ALLOWED_DOMAINS: str = os.getenv(
            "DEFAULT_ALLOWED_DOMAINS",
            cors_origins,
        )

        # ChromaDB persistent storage path
        self.CHROMA_DB_PATH: str = os.getenv(
            "CHROMA_DB_PATH",
            str(PROJECT_ROOT / "chroma_db"),
        )

        # Sentence Transformers embedding model
        self.EMBEDDING_MODEL_NAME: str = os.getenv(
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        )

        # Gemini AI settings
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.GEMINI_VISION_MODEL: str = os.getenv(
            "GEMINI_VISION_MODEL",
            os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        )
        self.GEMINI_VISION_ENABLED: bool = os.getenv(
            "GEMINI_VISION_ENABLED", "true"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.GEMINI_VISION_MAX_IMAGES_PER_DOCUMENT: int = int(
            os.getenv("GEMINI_VISION_MAX_IMAGES_PER_DOCUMENT", "5")
        )
        self.GEMINI_VISION_MIN_IMAGE_BYTES: int = int(
            os.getenv("GEMINI_VISION_MIN_IMAGE_BYTES", "4096")
        )
        self.GEMINI_VISION_MIN_IMAGE_DIMENSION: int = int(
            os.getenv("GEMINI_VISION_MIN_IMAGE_DIMENSION", "80")
        )
        self.GEMINI_VISION_REQUEST_INTERVAL_SECONDS: float = float(
            os.getenv("GEMINI_VISION_REQUEST_INTERVAL_SECONDS", "13")
        )

        # Ollama local AI settings
        self.OLLAMA_BASE_URL: str = os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.OLLAMA_REQUEST_TIMEOUT_SECONDS: int = int(
            os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120")
        )

        # OpenAI settings
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.OPENAI_REQUEST_TIMEOUT_SECONDS: int = int(
            os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "120")
        )

        # Website URL ingestion (Playwright crawler)
        self.URL_CRAWL_MAX_PAGES: int = int(os.getenv("URL_CRAWL_MAX_PAGES", "20"))
        self.URL_CRAWL_TIMEOUT_SECONDS: int = int(
            os.getenv("URL_CRAWL_TIMEOUT_SECONDS", "60")
        )
        self.URL_CRAWL_POST_RENDER_WAIT_MS: int = int(
            os.getenv("URL_CRAWL_POST_RENDER_WAIT_MS", "3000")
        )
        self.URL_FETCH_TIMEOUT_SECONDS: int = int(
            os.getenv("URL_FETCH_TIMEOUT_SECONDS", "30")
        )
        self.URL_PLAYWRIGHT_HEADLESS: bool = os.getenv(
            "URL_PLAYWRIGHT_HEADLESS", "true"
        ).strip().lower() in {"1", "true", "yes", "on"}

        # RAG retrieval and AI response quality settings
        self.RAG_INITIAL_TOP_K: int = int(os.getenv("RAG_INITIAL_TOP_K", "10"))
        self.RAG_FINAL_TOP_K: int = int(os.getenv("RAG_FINAL_TOP_K", "5"))
        self.RAG_CONVERSATION_MEMORY_MESSAGES: int = int(
            os.getenv("RAG_CONVERSATION_MEMORY_MESSAGES", "5")
        )
        self.RAG_VECTOR_SEARCH_WEIGHT: float = float(
            os.getenv("RAG_VECTOR_SEARCH_WEIGHT", "0.7")
        )
        self.RAG_BM25_SEARCH_WEIGHT: float = float(
            os.getenv("RAG_BM25_SEARCH_WEIGHT", "0.3")
        )
        self.RAG_BM25_MAX_CHUNKS: int = int(os.getenv("RAG_BM25_MAX_CHUNKS", "2000"))
        self.RAG_HYBRID_WEIGHT: float = float(os.getenv("RAG_HYBRID_WEIGHT", "0.7"))
        self.RAG_KEYWORD_OVERLAP_WEIGHT: float = float(
            os.getenv("RAG_KEYWORD_OVERLAP_WEIGHT", "0.3")
        )

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
