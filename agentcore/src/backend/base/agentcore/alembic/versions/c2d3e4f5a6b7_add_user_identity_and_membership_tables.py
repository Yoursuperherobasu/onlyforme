"""add user identity fields and membership tables

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-02-17 23:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("email", sa.String(), nullable=True))
    op.add_column("user", sa.Column("display_name", sa.String(), nullable=True))
    op.add_column("user", sa.Column("entra_object_id", sa.String(), nullable=True))
    op.add_column("user", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_entra_object_id", "user", ["entra_object_id"], unique=True)

    op.create_table(
        "user_organization_membership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'invited'")),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["invited_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "org_id", name="uq_uom_user_org"),
    )
    op.create_index("ix_uom_user_id", "user_organization_membership", ["user_id"], unique=False)
    op.create_index("ix_uom_org_id", "user_organization_membership", ["org_id"], unique=False)
    op.create_index("ix_uom_role_id", "user_organization_membership", ["role_id"], unique=False)

    op.create_table(
        "user_department_membership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'active'")),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "department_id"],
            ["department.org_id", "department.id"],
            name="fk_udm_org_department",
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "org_id", "department_id", name="uq_udm_user_org_department"),
    )
    op.create_index("ix_udm_user_id", "user_department_membership", ["user_id"], unique=False)
    op.create_index("ix_udm_org_id", "user_department_membership", ["org_id"], unique=False)
    op.create_index("ix_udm_department_id", "user_department_membership", ["department_id"], unique=False)
    op.create_index("ix_udm_role_id", "user_department_membership", ["role_id"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_udm_role_id", table_name="user_department_membership")
    op.drop_index("ix_udm_department_id", table_name="user_department_membership")
    op.drop_index("ix_udm_org_id", table_name="user_department_membership")
    op.drop_index("ix_udm_user_id", table_name="user_department_membership")
    op.drop_table("user_department_membership")

    op.drop_index("ix_uom_role_id", table_name="user_organization_membership")
    op.drop_index("ix_uom_org_id", table_name="user_organization_membership")
    op.drop_index("ix_uom_user_id", table_name="user_organization_membership")
    op.drop_table("user_organization_membership")

    op.drop_index("ix_user_entra_object_id", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_column("user", "deleted_at")
    op.drop_column("user", "entra_object_id")
    op.drop_column("user", "display_name")
    op.drop_column("user", "email")
