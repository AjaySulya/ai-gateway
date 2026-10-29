"""ensure huggingface provider_type enum value

The original migration (f6007268877e) was committed with empty upgrade()
and downgrade() bodies. Editing an already-applied migration does not re-run
it, so this revision repairs databases that recorded f6007268877e without
actually adding the enum value. It is idempotent: fresh databases already got
the value from f6007268877e, and environments where it was added manually are
unaffected.

Revision ID: c7f1d2e9a4b6
Revises: f6007268877e
Create Date: 2026-10-29

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7f1d2e9a4b6"
down_revision: str | None = "f6007268877e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'huggingface'")


def downgrade() -> None:
    # PostgreSQL has no ALTER TYPE ... DROP VALUE; see f6007268877e.
    pass
