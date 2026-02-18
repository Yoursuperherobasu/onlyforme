# Path: src/backend/agentcore/services/database/models/project/model.py

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column, Enum as SQLEnum, Text, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from agentcore.services.database.models.agent.model import Agent
    from agentcore.services.database.models.department.model import Department
    from agentcore.services.database.models.organization.model import Organization
    from agentcore.services.database.models.user.model import User


class ProjectStatusEnum(str, Enum):
    """Status of the project."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProjectBase(SQLModel):
    """Base model for Project (replaces Folder)."""

    __mapper_args__ = {"confirm_deleted_rows": False}

    org_id: UUID = Field(foreign_key="organization.id", nullable=False, index=True)
    dept_id: UUID = Field(foreign_key="department.id", nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False, index=True, description="Project name")
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Optional details",
    )
    parent_project_id: UUID | None = Field(
        default=None,
        foreign_key="project.id",
        nullable=True,
        description="Sub-project hierarchy. NULL = top-level.",
    )
    owner_user_id: UUID = Field(
        foreign_key="user.id",
        nullable=False,
        index=True,
        description="Who owns this project",
    )
    tags: dict | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Searchable labels for filtering",
    )
    status: ProjectStatusEnum = Field(
        default=ProjectStatusEnum.ACTIVE,
        sa_column=Column(
            SQLEnum(
                ProjectStatusEnum,
                name="project_status_enum",
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


class Project(ProjectBase, table=True):  # type: ignore[call-arg]

    __tablename__ = "project"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Relationships
    organization: Optional["Organization"] = Relationship()
    department: Optional["Department"] = Relationship(back_populates="projects")
    owner: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Project.owner_user_id]"},
    )
    parent: Optional["Project"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Project.id"},
    )
    children: list["Project"] = Relationship(back_populates="parent")
    agents: list["Agent"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete, delete-orphan"},
    )

    __table_args__ = (
        UniqueConstraint("dept_id", "name", name="uq_project_dept_name"),
    )


class ProjectCreate(SQLModel):
    """Model for creating a new project."""

    org_id: UUID
    dept_id: UUID
    name: str
    description: str | None = None
    parent_project_id: UUID | None = None
    owner_user_id: UUID
    tags: dict | None = None
    created_by: UUID


class ProjectRead(BaseModel):
    """Model for reading project data."""

    id: UUID
    org_id: UUID
    dept_id: UUID
    name: str
    description: str | None = None
    parent_project_id: UUID | None = None
    owner_user_id: UUID
    tags: dict | None = None
    status: ProjectStatusEnum
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None = None
    updated_at: datetime


class ProjectUpdate(BaseModel):
    """Model for updating a project."""

    name: str | None = None
    description: str | None = None
    parent_project_id: UUID | None = None
    owner_user_id: UUID | None = None
    tags: dict | None = None
    status: ProjectStatusEnum | None = None
    updated_by: UUID | None = None
