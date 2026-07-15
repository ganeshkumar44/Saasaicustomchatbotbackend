"""add_chatbot_prompt_table

Revision ID: a1b2c3d4e5f6
Revises: 7c4a407286ea
Create Date: 2026-07-15 20:00:00.000000

Adds chatbot_prompt table for per-chatbot prompt configuration.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7c4a407286ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import app.models  # noqa: F401
    from app.core.database import Base

    bind = op.get_bind()
    Base.metadata.tables["chatbot_prompt"].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    op.drop_table("chatbot_prompt")
