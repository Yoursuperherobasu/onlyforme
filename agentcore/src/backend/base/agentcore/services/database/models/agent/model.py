
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    field_serializer,
    field_validator,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Text, UniqueConstraint, text
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from agentcore.schema.data import Data

if TYPE_CHECKING:
    from agentcore.services.database.models.folder.model import Folder
    from agentcore.services.database.models.user.model import User
    from agentcore.services.database.models.agent_deployment_prod.model import AgentDeploymentProd
    from agentcore.services.database.models.agent_deployment_uat.model import AgentDeploymentUAT
    from agentcore.services.database.models.organization.model import Organization
    from agentcore.services.database.models.project.model import Project


class AccessTypeEnum(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"

class LifecycleStatusEnum(str, Enum):
    """Lifecycle status of the agent."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"

class AgentBase(SQLModel):
    # Supresses warnings during migrations
    __mapper_args__ = {"confirm_deleted_rows": False}

    name: str = Field(index=True)
    description: str | None = Field(default=None, sa_column=Column(Text, index=True, nullable=True))
    data: dict | None = Field(default=None, nullable=True)
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=True)
    tags: list[str] | None = None
    locked: bool | None = Field(default=False, nullable=True)
    mcp_enabled: bool | None = Field(default=False, nullable=True, description="Can be exposed in the MCP server")
    action_name: str | None = Field(
        default=None, nullable=True, description="The name of the action associated with the agent"
    )
    action_description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="The description of the action associated with the agent",
    )
    access_type: AccessTypeEnum = Field(
        default=AccessTypeEnum.PRIVATE,
        sa_column=Column(
            SQLEnum(
                AccessTypeEnum,
                name="access_type_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'PRIVATE'"),
        ),
    )

    @field_validator("data")
    @classmethod
    def validate_json(cls, v):
        if not v:
            return v
        if not isinstance(v, dict):
            msg = "Agent data must be a valid JSON"
            raise ValueError(msg)  # noqa: TRY004

        # data must contain nodes and edges
        if "nodes" not in v:
            msg = "Agent data must have nodes"
            raise ValueError(msg)
        if "edges" not in v:
            msg = "Agent data must have edges"
            raise ValueError(msg)

        return v

    # updated_at can be serialized to JSON
    @field_serializer("updated_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            value = value.replace(microsecond=0)
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    @field_validator("updated_at", mode="before")
    @classmethod
    def validate_dt(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            # Strip timezone info if present
            if v.tzinfo is not None:
                return v.replace(tzinfo=None)
            return v
        # Parse string and return naive datetime
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt


class Agent(AgentBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    user_id: UUID | None = Field(index=True, foreign_key="user.id", nullable=True)
    user: "User" = Relationship(back_populates="agents")
    tags: list[str] | None = Field(sa_column=Column(JSON), default=[])
    locked: bool | None = Field(default=False, nullable=True)
    folder_id: UUID | None = Field(default=None, foreign_key="folder.id", nullable=True, index=True)
    fs_path: str | None = Field(default=None, nullable=True)
    folder: Optional["Folder"] = Relationship(back_populates="agents")
    
    # === NEW ENTERPRISE COLUMNS ===
    org_id: UUID | None = Field(
        default=None,
        foreign_key="organization.id",
        nullable=True,
        index=True,
        description="Tenant isolation — which organization owns this agent",
    )
    dept_id: UUID | None = Field(
        default=None,
        foreign_key="department.id",
        nullable=True,
        index=True,
        description="Which department owns this agent",
    )
    project_id: UUID | None = Field(
        default=None,
        foreign_key="project.id",
        nullable=True,
        index=True,
        description="Which project this agent belongs to (replaces folder_id)",
    )
    lifecycle_status: LifecycleStatusEnum = Field(
        default=LifecycleStatusEnum.DRAFT,
        sa_column=Column(
            SQLEnum(
                LifecycleStatusEnum,
                name="lifecycle_status_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'DRAFT'"),
        ),
        description="DRAFT / PUBLISHED / DEPRECATED / ARCHIVED",
    )
    cloned_from_deployment_id: UUID | None = Field(
        default=None,
        nullable=True,
        description="If cloned from Agent Catalogue, tracks which deployment was the source",
    )
    deleted_at: datetime | None = Field(default=None, nullable=True, description="Soft delete timestamp")

    # New relationships
    organization: Optional["Organization"] = Relationship()
    project: Optional["Project"] = Relationship(back_populates="agents")
    deployment_uat_records: list["AgentDeploymentUAT"] = Relationship(back_populates="agent")
    deployment_prod_records: list["AgentDeploymentProd"] = Relationship(back_populates="agent")

    def to_data(self):
        serialized = self.model_dump()
        data = {
            "id": serialized.pop("id"),
            "data": serialized.pop("data"),
            "name": serialized.pop("name"),
            "description": serialized.pop("description"),
            "updated_at": serialized.pop("updated_at"),
        }
        return Data(data=data)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_agent_name"),
    )


class AgentCreate(AgentBase):
    user_id: UUID | None = None
    folder_id: UUID | None = None
    fs_path: str | None = None


class AgentRead(AgentBase):
    id: UUID
    user_id: UUID | None = Field()
    folder_id: UUID | None = Field()
    tags: list[str] | None = Field(None, description="The tags of the agent")


class AgentHeader(BaseModel):
    """Model representing a header for an agent - Without the data."""

    id: UUID = Field(description="Unique identifier for the agent")
    name: str = Field(description="The name of the agent")
    folder_id: UUID | None = Field(
        None,
        description="The ID of the folder containing the agent. None if not associated with a folder",
    )
    description: str | None = Field(None, description="A description of the agent")
    data: dict | None = Field(None, description="The data of the agent")
    access_type: AccessTypeEnum | None = Field(None, description="The access type of the agent")
    tags: list[str] | None = Field(None, description="The tags of the agent")
    mcp_enabled: bool | None = Field(None, description="Flag indicating whether the agent is exposed in the MCP server")
    action_name: str | None = Field(None, description="The name of the action associated with the agent")
    action_description: str | None = Field(None, description="The description of the action associated with the agent")


class AgentUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    data: dict | None = None
    folder_id: UUID | None = None
    mcp_enabled: bool | None = None
    locked: bool | None = None
    action_name: str | None = None
    action_description: str | None = None
    access_type: AccessTypeEnum | None = None
    fs_path: str | None = None
