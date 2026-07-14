"""
Alembic environment for the NexGenChat FastAPI backend.

Configuration goals:
  - Load ``.env`` via the existing Settings / python-dotenv path
  - Use the same PostgreSQL URL as ``app.core.database`` (or ``DATABASE_URL``)
  - Target ``Base.metadata`` after importing all ORM models from ``app.models``
  - Support online (DB-connected) and offline SQL generation modes
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so ``app.*`` imports work when the
# Alembic CLI is invoked from any working directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load Settings early (this also loads the project-root ``.env`` via dotenv).
from app.core.config import get_settings  # noqa: E402

# Import all ORM models so every table is present on Base.metadata.
# Without this, autogenerate would see an empty metadata and drop/create wrong.
import app.models  # noqa: E402, F401
from app.core.database import Base  # noqa: E402

# Alembic Config object (provides access to values in alembic.ini).
config = context.config

# Interpret the config file for Python logging when present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata used by ``alembic revision --autogenerate``.
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):  # noqa: ANN001, A002
    """
    Filter objects considered during autogenerate.

    Production safety:
      - Tables that exist in PostgreSQL but are NOT mapped in SQLAlchemy
        (for example legacy ``test_connection``) must NEVER be dropped by
        autogenerate. Returning ``False`` when ``reflected and compare_to is None``
        for tables keeps those orphan tables untouched.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def get_database_url() -> str:
    """
    Resolve the PostgreSQL URL for migrations.

    Priority:
      1. ``DATABASE_URL`` environment variable (explicit override)
      2. ``Settings.database_url`` built from ``DB_*`` keys in ``.env``
         (same source as ``app.core.database.engine``)
    """
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    settings = get_settings()
    settings.validate()
    return settings.database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Configures the context with just a URL (no Engine). Useful for generating
    SQL scripts without a live database connection.
    """
    url = get_database_url()
    # Keep alembic.ini sqlalchemy.url in sync when tools read it later.
    config.set_main_option("sqlalchemy.url", url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Compare types / server defaults so column alterations are detected.
        compare_type=True,
        compare_server_default=True,
        # Include object naming for index / constraint diffs.
        include_schemas=False,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    url = get_database_url()
    # Override alembic.ini placeholder so the Engine uses the real credentials.
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        # NullPool avoids holding pooled connections across CLI runs.
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=False,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
