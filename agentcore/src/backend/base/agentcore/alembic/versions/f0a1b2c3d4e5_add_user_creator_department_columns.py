"""add creator/department columns to user

Revision ID: f0a1b2c3d4e5
Revises: c4d9e2f8a1b0
Create Date: 2026-02-16 22:24:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "c4d9e2f8a1b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("creator_email", sa.String(), nullable=True))
    op.add_column("user", sa.Column("creator_role", sa.String(length=50), nullable=True))
    op.add_column("user", sa.Column("department_admin_email", sa.String(), nullable=True))
    op.add_column("user", sa.Column("department_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "department_name")
    op.drop_column("user", "department_admin_email")
    op.drop_column("user", "creator_role")
    op.drop_column("user", "creator_email")

