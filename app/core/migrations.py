"""
Programmatic Alembic migration runner for application startup.

On deploy / app restart, ``run_pending_migrations()`` applies any pending
revision files (``alembic upgrade head``) so live PostgreSQL stays in sync
with the ORM without a separate manual CLI step.

Developers still create revisions locally:

    alembic revision --autogenerate -m "describe change"

Production / live only *applies* committed files under ``alembic/versions/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)

_ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def _build_alembic_config() -> Config:
    """Load ``alembic.ini`` from the project root (same path as CLI)."""
    if not _ALEMBIC_INI.is_file():
        raise FileNotFoundError(
            f"Alembic config not found at {_ALEMBIC_INI}. "
            "Ensure alembic.ini exists in the project root."
        )
    cfg = Config(str(_ALEMBIC_INI))
    # env.py resolves the real URL from DATABASE_URL / DB_* via get_database_url().
    return cfg


def run_pending_migrations() -> None:
    """
    Apply all pending Alembic revisions up to ``head``.

    Safe to call on every startup:
      - Already at head → no-op (Alembic skips applied revisions).
      - Pending revisions → runs only what is missing.
      - Uses ``checkfirst`` in the baseline revision for missing tables.

    Controlled by ``AUTO_RUN_MIGRATIONS`` in ``.env`` (default: enabled).
    """
    settings = get_settings()
    if not settings.AUTO_RUN_MIGRATIONS:
        logger.info("AUTO_RUN_MIGRATIONS is disabled; skipping Alembic upgrade.")
        return

    logger.info("Running Alembic migrations (upgrade head)...")
    cfg = _build_alembic_config()
    command.upgrade(cfg, "head")
    logger.info("Alembic migrations complete (database at head).")
