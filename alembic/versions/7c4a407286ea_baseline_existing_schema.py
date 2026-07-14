"""baseline_existing_schema

Revision ID: 7c4a407286ea
Revises:
Create Date: 2026-07-14 23:34:16.796674

Baselines the PostgreSQL schema for Alembic.

Behaviour:
  - Greenfield DB: creates all tables from ``Base.metadata`` (checkfirst=True).
  - Existing DB: tables already present → no recreation; no drops.
  - Legacy orphan tables (e.g. ``test_connection``) are left untouched.

Future schema changes must use:
  alembic revision --autogenerate -m "description"
  alembic upgrade head
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c4a407286ea"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create missing tables only; never drop existing tables or data."""
    # Import models so every table is registered before create_all(checkfirst).
    import app.models  # noqa: F401
    from app.core.database import Base

    bind = op.get_bind()
    # checkfirst=True ⇒ CREATE only when the table is missing (production-safe).
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    """
    No-op on purpose.

    Dropping the full application schema from the baseline would destroy
    production data. Use a dedicated destructive migration if ever required.
    """
    pass
