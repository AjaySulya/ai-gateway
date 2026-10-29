"""add huggingface provider type

Revision ID: f6007268877e
Revises: 2dad874df614
Create Date: 2026-09-27 21:10:43.514182

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6007268877e'
down_revision: str | None = '2dad874df614'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Alembic autogenerate does not detect a new value added to an existing
    # Postgres enum, so this has to be written by hand (see README).
    op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'huggingface'")


def downgrade() -> None:
    # PostgreSQL has no ALTER TYPE ... DROP VALUE. Removing a value requires
    # recreating the type and rewriting every dependent column, which isn't
    # safe to automate here.
    pass
