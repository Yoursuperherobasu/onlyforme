"""Add email_monitor to trigger_type_enum

Revision ID: q4r5s6t7u8v9
Revises: p2q3r4s5t6u7
Create Date: 2026-03-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "q4r5s6t7u8v9"
down_revision: str | Sequence[str] | None = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 'email_monitor' value to the trigger_type_enum PostgreSQL enum."""
    from alembic import op

    op.execute("ALTER TYPE trigger_type_enum ADD VALUE IF NOT EXISTS 'email_monitor'")


def downgrade() -> None:
    """PostgreSQL cannot remove enum values — no-op."""
    pass
