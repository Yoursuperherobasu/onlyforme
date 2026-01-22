"""Fix timestamp columns to use DateTime instead of TIMESTAMP(timezone=True)

Revision ID: 8f3a1b2c4d5e
Revises: 2a32c0912c60, 79e675cb6752, d9a6ea21edcd
Create Date: 2026-01-21

This migration fixes the mismatch between the models (DateTime) and the database
(TIMESTAMP(timezone=True)) for the apikey and variable tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "8f3a1b2c4d5e"
down_revision: tuple[str, ...] = ("2a32c0912c60", "79e675cb6752", "d9a6ea21edcd")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def get_column_type(inspector: Inspector, table_name: str, column_name: str):
    """Get the current type of a column."""
    columns = inspector.get_columns(table_name)
    for col in columns:
        if col["name"] == column_name:
            return col["type"]
    return None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # Fix apikey.created_at
    if "apikey" in tables:
        col_type = get_column_type(inspector, "apikey", "created_at")
        if col_type is not None and hasattr(col_type, 'timezone') and col_type.timezone:
            # Column is TIMESTAMP(timezone=True), change to DateTime
            op.alter_column(
                "apikey",
                "created_at",
                type_=sa.DateTime(),
                existing_type=sa.TIMESTAMP(timezone=True),
                existing_nullable=False,
            )
    
    # Fix variable.created_at and variable.updated_at
    if "variable" in tables:
        col_type = get_column_type(inspector, "variable", "created_at")
        if col_type is not None and hasattr(col_type, 'timezone') and col_type.timezone:
            op.alter_column(
                "variable",
                "created_at",
                type_=sa.DateTime(),
                existing_type=sa.TIMESTAMP(timezone=True),
                existing_nullable=True,
            )
        
        col_type = get_column_type(inspector, "variable", "updated_at")
        if col_type is not None and hasattr(col_type, 'timezone') and col_type.timezone:
            op.alter_column(
                "variable",
                "updated_at",
                type_=sa.DateTime(),
                existing_type=sa.TIMESTAMP(timezone=True),
                existing_nullable=True,
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # Revert apikey.created_at
    if "apikey" in tables:
        op.alter_column(
            "apikey",
            "created_at",
            type_=sa.TIMESTAMP(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=False,
        )
    
    # Revert variable.created_at and variable.updated_at  
    if "variable" in tables:
        op.alter_column(
            "variable",
            "created_at",
            type_=sa.TIMESTAMP(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
        op.alter_column(
            "variable",
            "updated_at",
            type_=sa.TIMESTAMP(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
