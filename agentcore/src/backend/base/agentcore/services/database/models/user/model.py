from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from agentcore.schema.serialize import UUIDstr

if TYPE_CHECKING:
    from agentcore.services.database.models.agent.model import Agent
    from agentcore.services.database.models.folder.model import Folder


class UserOptin(BaseModel):
    github_starred: bool = Field(default=False)
    dialog_dismissed: bool = Field(default=False)
    discord_clicked: bool = Field(default=False)
    # Add more opt-in actions as needed


class User(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(index=True, unique=True)
    password: str = Field()
    profile_image: str | None = Field(default=None, nullable=True)
    is_active: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    role: str = Field(default="developer", max_length=50)
    create_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime | None = Field(default=None, nullable=True)
    store_api_key: str | None = Field(default=None, nullable=True)
    agents: list["Agent"] = Relationship(back_populates="user")
    # [VARIABLE REMOVED] variables relationship removed — migrating to Azure Key Vault
    folders: list["Folder"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    optins: dict[str, Any] | None = Field(
        sa_column=Column(JSON, default=lambda: UserOptin().model_dump(), nullable=True)
    )


class UserCreate(SQLModel):
    username: str = Field()
    password: str = Field()
    role: str = Field(default="developer", max_length=50)
    optins: dict[str, Any] | None = None


class UserRead(SQLModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field()
    profile_image: str | None = Field()
    store_api_key: str | None = Field(nullable=True)
    is_active: bool = Field()
    is_superuser: bool = Field()
    role: str = Field()
    create_at: datetime = Field()
    updated_at: datetime = Field()
    last_login_at: datetime | None = Field(nullable=True)
    optins: dict[str, Any] | None = Field(default=None)


class UserUpdate(SQLModel):
    username: str | None = None
    profile_image: str | None = None
    password: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    role: str | None = None
    last_login_at: datetime | None = None
    optins: dict[str, Any] | None = None
