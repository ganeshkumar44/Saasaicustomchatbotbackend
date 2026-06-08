"""
SQLAlchemy engine, session factory, and declarative base.

Import `Base` in every ORM model module so tables are registered with
`Base.metadata` before `create_all()` runs at application startup.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
settings.validate()

# Connection pool with pre-ping avoids stale connections after idle timeouts.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request.

    The session is always closed after the request completes, even on error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
