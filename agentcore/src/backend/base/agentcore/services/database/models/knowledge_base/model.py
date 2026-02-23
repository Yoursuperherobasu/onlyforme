from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class KnowledgeBase(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "knowledge_base"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    org_id: UUID | None = Field(default=None, foreign_key="organization.id", nullable=True)
    dept_id: UUID | None = Field(default=None, foreign_key="department.id", nullable=True)
    created_by: UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint("org_id", "dept_id", "name", name="uq_kb_org_dept_name"),
        Index("ix_knowledge_base_org_id", "org_id"),
        Index("ix_knowledge_base_dept_id", "dept_id"),
        Index("ix_knowledge_base_created_by", "created_by"),
    )
