"""Drop variable table — migrating to Azure Key Vault

Revision ID: a1b2c3d4e5f6
Revises: 8f3a1b2c4d5e
Create Date: 2026-02-08 03:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "8f3a1b2c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the variable table — secrets now managed via Azure Key Vault."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "variable" in existing_tables:
        op.drop_table("variable")


def downgrade() -> None:
    """Recreate variable table (restore only schema, data is not recoverable)."""
    op.create_table(
        "variable",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("value", sa.VARCHAR(), nullable=False),
        sa.Column("type", sa.VARCHAR(), nullable=True),
        sa.Column("default_fields", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
