# Path: src/backend/agentcore/services/database/models/organization/model.py

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Column, Enum as SQLEnum, Text, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from agentcore.services.database.models.department.model import Department
    from agentcore.services.database.models.user.model import User


class OrgTierEnum(str, Enum):
    """Pricing/feature tier for the organization."""

    FREE = "free"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class OrgStatusEnum(str, Enum):
    """Status of the organization."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OrganizationBase(SQLModel):
    """Base model for Organization."""

    __mapper_args__ = {"confirm_deleted_rows": False}

    name: str = Field(max_length=255, unique=True, index=True, nullable=False, description="Organization display name")
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Optional details about the organization",
    )
    tier: OrgTierEnum = Field(
        default=OrgTierEnum.STANDARD,
        sa_column=Column(
            SQLEnum(
                OrgTierEnum,
                name="org_tier_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'standard'"),
        ),
        description="Pricing tier — controls feature limits",
    )
    status: OrgStatusEnum = Field(
        default=OrgStatusEnum.ACTIVE,
        sa_column=Column(
            SQLEnum(
                OrgStatusEnum,
                name="org_status_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'active'"),
        ),
        description="Organization status — suspending freezes all agents",
    )
    owner_user_id: UUID = Field(foreign_key="user.id", nullable=False, description="Who owns this organization")
    created_by: UUID = Field(foreign_key="user.id", nullable=False, description="Audit: who created this org")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_by: UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        description="Audit: who last modified",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Organization(OrganizationBase, table=True):  # type: ignore[call-arg]

    __tablename__ = "organization"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Relationships
    owner: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Organization.owner_user_id]"},
    )
    creator: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Organization.created_by]"},
    )
    departments: list["Department"] = Relationship(back_populates="organization")


class OrganizationCreate(SQLModel):
    """Model for creating a new organization."""

    name: str
    description: str | None = None
    tier: OrgTierEnum = OrgTierEnum.STANDARD
    owner_user_id: UUID
    created_by: UUID


class OrganizationRead(BaseModel):
    """Model for reading organization data."""

    id: UUID
    name: str
    description: str | None = None
    tier: OrgTierEnum
    status: OrgStatusEnum
    owner_user_id: UUID
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None = None
    updated_at: datetime


class OrganizationUpdate(BaseModel):
    """Model for updating an organization."""

    name: str | None = None
    description: str | None = None
    tier: OrgTierEnum | None = None
    status: OrgStatusEnum | None = None
    owner_user_id: UUID | None = None
    updated_by: UUID | None = None
