from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint, Column, Text, DateTime
from sqlmodel import Field, SQLModel


class Permission(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    key: str = Field(index=True, max_length=200)
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    __table_args__ = (UniqueConstraint("key", name="uq_permission_key"),)


class PermissionCreate(SQLModel):
    key: str
    name: str
    description: str | None = None


class PermissionRead(SQLModel):
    id: UUID
    key: str
    name: str
    description: str | None = None
