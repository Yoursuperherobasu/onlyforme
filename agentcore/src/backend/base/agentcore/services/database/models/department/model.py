# Path: src/backend/agentcore/services/database/models/department/model.py

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Column, Enum as SQLEnum, Text, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from agentcore.services.database.models.organization.model import Organization
    from agentcore.services.database.models.project.model import Project
    from agentcore.services.database.models.user.model import User


class DeptStatusEnum(str, Enum):
    """Status of the department."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class DepartmentBase(SQLModel):
    """Base model for Department."""

    __mapper_args__ = {"confirm_deleted_rows": False}

    org_id: UUID = Field(foreign_key="organization.id", nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False, description="Department name")
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Optional details about the department",
    )
    code: str | None = Field(
        default=None,
        max_length=50,
        nullable=True,
        description="Short code for UI badges (e.g., AI-ENG)",
    )
    parent_dept_id: UUID | None = Field(
        default=None,
        foreign_key="department.id",
        nullable=True,
        description="Sub-department hierarchy. NULL = top-level dept.",
    )
    admin_user_id: UUID = Field(
        foreign_key="user.id",
        nullable=False,
        index=True,
        description="Who approves PROD deploys for agents in this dept",
    )
    status: DeptStatusEnum = Field(
        default=DeptStatusEnum.ACTIVE,
        sa_column=Column(
            SQLEnum(
                DeptStatusEnum,
                name="dept_status_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'active'"),
        ),
    )
    created_by: UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Department(DepartmentBase, table=True):  # type: ignore[call-arg]

    __tablename__ = "department"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Relationships
    organization: Optional["Organization"] = Relationship(back_populates="departments")
    admin: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Department.admin_user_id]"},
    )
    parent: Optional["Department"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Department.id"},
    )
    children: list["Department"] = Relationship(back_populates="parent")
    projects: list["Project"] = Relationship(back_populates="department")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_department_org_name"),
    )


class DepartmentCreate(SQLModel):
    """Model for creating a new department."""

    org_id: UUID
    name: str
    description: str | None = None
    code: str | None = None
    parent_dept_id: UUID | None = None
    admin_user_id: UUID
    created_by: UUID


class DepartmentRead(BaseModel):
    """Model for reading department data."""

    id: UUID
    org_id: UUID
    name: str
    description: str | None = None
    code: str | None = None
    parent_dept_id: UUID | None = None
    admin_user_id: UUID
    status: DeptStatusEnum
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None = None
    updated_at: datetime


class DepartmentUpdate(BaseModel):
    """Model for updating a department."""

    name: str | None = None
    description: str | None = None
    code: str | None = None
    parent_dept_id: UUID | None = None
    admin_user_id: UUID | None = None
    status: DeptStatusEnum | None = None
    updated_by: UUID | None = None
