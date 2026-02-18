"""Create agent_registry_rating table for per-user star ratings

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-19

Changes:
  - NEW TABLE: agent_registry_rating (per-user star ratings)
      - id (UUID PK)
      - registry_id (FK → agent_registry.id)
      - user_id (FK → user.id)
      - score (FLOAT, 1.0–5.0)
      - review (TEXT, nullable)
      - created_at, updated_at
      - UNIQUE(registry_id, user_id)

The rating and rating_count on agent_registry are denormalized aggregates
computed from this table. The count next to the star (e.g. "4.8 (1240)")
shows how many people have rated the agent.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create agent_registry_rating table ──────────────────────
    op.create_table(
        "agent_registry_rating",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("registry_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["registry_id"], ["agent_registry.id"], name="fk_registry_rating_registry"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_registry_rating_user"),
        sa.UniqueConstraint("registry_id", "user_id", name="uq_registry_rating_user"),
    )
    op.create_index("ix_registry_rating_registry", "agent_registry_rating", ["registry_id"], unique=False)
    op.create_index("ix_registry_rating_user", "agent_registry_rating", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_registry_rating_user", table_name="agent_registry_rating")
    op.drop_index("ix_registry_rating_registry", table_name="agent_registry_rating")
    op.drop_table("agent_registry_rating")
