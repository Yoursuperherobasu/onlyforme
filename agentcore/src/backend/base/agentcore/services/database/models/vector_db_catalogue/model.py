from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class VectorDBCatalogue(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "vector_db_catalogue"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID | None = Field(default=None, foreign_key="organization.id", nullable=True, index=True)
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    provider: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    deployment: str = Field(sa_column=Column(String(50), nullable=False))
    dimensions: str = Field(sa_column=Column(String(50), nullable=False))
    index_type: str = Field(sa_column=Column(String(100), nullable=False))
    status: str = Field(sa_column=Column(String(50), nullable=False))
    vector_count: str = Field(sa_column=Column(String(50), nullable=False))
    is_custom: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
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

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_vector_db_catalogue_org_name"),
    )
