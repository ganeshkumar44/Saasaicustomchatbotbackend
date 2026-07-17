"""add_contact_submissions_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-17 14:00:00.000000

Adds contact_submissions table for public landing-page contact forms.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import app.models  # noqa: F401
    from app.core.database import Base

    bind = op.get_bind()
    Base.metadata.tables["contact_submissions"].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    op.drop_table("contact_submissions")
