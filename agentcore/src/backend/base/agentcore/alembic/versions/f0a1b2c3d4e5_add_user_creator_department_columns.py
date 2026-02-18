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
    op.execute(sa.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS creator_email VARCHAR'))
    op.execute(sa.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS creator_role VARCHAR(50)'))
    op.execute(sa.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS department_admin_email VARCHAR'))
    op.execute(sa.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS department_name VARCHAR'))


def downgrade() -> None:
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS department_name'))
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS department_admin_email'))
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS creator_role'))
    op.execute(sa.text('ALTER TABLE "user" DROP COLUMN IF EXISTS creator_email'))

