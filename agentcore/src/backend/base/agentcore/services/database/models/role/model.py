from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint, Column, Text, DateTime
from sqlmodel import Field, SQLModel


class Role(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, max_length=100)
    description: str | None = Field(default=None, sa_column=Column(Text))
    is_system: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    __table_args__ = (UniqueConstraint("name", name="uq_role_name"),)


class RoleCreate(SQLModel):
    name: str
    description: str | None = None


class RoleUpdate(SQLModel):
    name: str | None = None
    description: str | None = None


class RoleRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    is_system: bool
