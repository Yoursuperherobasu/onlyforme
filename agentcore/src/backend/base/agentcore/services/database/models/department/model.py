from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class Department(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="organization.id", nullable=False, index=True)
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    code: str | None = Field(default=None, sa_column=Column(String(50), nullable=True))
    admin_user_id: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    status: str = Field(default="active", sa_column=Column(String(50), nullable=False))
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

    __table_args__ = (
        UniqueConstraint("org_id", "id", name="uq_department_org_id_id"),
        UniqueConstraint("org_id", "code", name="uq_department_org_id_code"),
    )
