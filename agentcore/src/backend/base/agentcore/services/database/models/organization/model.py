from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field, SQLModel


class Organization(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))
    owner_user_id: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    created_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    deleted_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
