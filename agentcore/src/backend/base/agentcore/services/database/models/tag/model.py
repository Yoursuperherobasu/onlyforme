from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlmodel import Column, Field, SQLModel


class TagCategoryEnum(str, Enum):
    ARCHITECTURE = "architecture"
    USE_CASE = "use_case"
    LIFECYCLE = "lifecycle"
    DOMAIN = "domain"
    CUSTOM = "custom"


# ── Predefined tags shipped with the system ──────────────────────────────
PREDEFINED_TAGS: list[dict] = [
    # Architecture
    {"name": "rag", "category": TagCategoryEnum.ARCHITECTURE, "description": "Retrieval-Augmented Generation"},
    {"name": "hitl", "category": TagCategoryEnum.ARCHITECTURE, "description": "Human-in-the-Loop"},
    {"name": "multi-agent", "category": TagCategoryEnum.ARCHITECTURE, "description": "Multi-Agent orchestration"},
    {"name": "single-agent", "category": TagCategoryEnum.ARCHITECTURE, "description": "Single agent workflow"},
    {"name": "agentic", "category": TagCategoryEnum.ARCHITECTURE, "description": "Agentic AI pattern"},
    {"name": "mcp", "category": TagCategoryEnum.ARCHITECTURE, "description": "Model Context Protocol"},
    {"name": "a2a", "category": TagCategoryEnum.ARCHITECTURE, "description": "Agent-to-Agent communication"},
    # Use Case
    {"name": "chatbot", "category": TagCategoryEnum.USE_CASE, "description": "Conversational chatbot"},
    {"name": "data-pipeline", "category": TagCategoryEnum.USE_CASE, "description": "Data processing pipeline"},
    {"name": "automation", "category": TagCategoryEnum.USE_CASE, "description": "Task automation"},
    {"name": "code-assistant", "category": TagCategoryEnum.USE_CASE, "description": "Code generation / assistance"},
    {"name": "summarization", "category": TagCategoryEnum.USE_CASE, "description": "Content summarization"},
    {"name": "classification", "category": TagCategoryEnum.USE_CASE, "description": "Text / data classification"},
    # Lifecycle
    {"name": "production", "category": TagCategoryEnum.LIFECYCLE, "description": "Production-ready"},
    {"name": "experimental", "category": TagCategoryEnum.LIFECYCLE, "description": "Experimental / POC"},
    {"name": "deprecated", "category": TagCategoryEnum.LIFECYCLE, "description": "Deprecated, avoid use"},
    # Domain
    {"name": "finance", "category": TagCategoryEnum.DOMAIN, "description": "Finance domain"},
    {"name": "healthcare", "category": TagCategoryEnum.DOMAIN, "description": "Healthcare domain"},
    {"name": "hr", "category": TagCategoryEnum.DOMAIN, "description": "Human Resources domain"},
    {"name": "legal", "category": TagCategoryEnum.DOMAIN, "description": "Legal domain"},
    {"name": "customer-support", "category": TagCategoryEnum.DOMAIN, "description": "Customer support"},
]


# ── Tag table ────────────────────────────────────────────────────────────
class TagBase(SQLModel):
    name: str = Field(sa_column=Column(String(60), nullable=False))
    category: TagCategoryEnum = Field(default=TagCategoryEnum.CUSTOM)
    description: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    is_predefined: bool = Field(default=False)


class Tag(TagBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "tag"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID | None = Field(default=None, foreign_key="organization.id", nullable=True, index=True)
    created_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint("name", "org_id", name="uq_tag_name_org"),
    )


class TagCreate(SQLModel):
    name: str = Field(max_length=60)
    category: TagCategoryEnum = TagCategoryEnum.CUSTOM
    description: str | None = None


class TagRead(TagBase):
    id: UUID
    org_id: UUID | None = None
    created_at: datetime | None = None
    usage_count: int | None = None  # populated at query time


# ── Junction: Project ↔ Tag ──────────────────────────────────────────────
class ProjectTag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "project_tag"

    project_id: UUID = Field(foreign_key="project.id", primary_key=True)
    tag_id: UUID = Field(foreign_key="tag.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


# ── Junction: Agent ↔ Tag ────────────────────────────────────────────────
class AgentTag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "agent_tag"

    agent_id: UUID = Field(foreign_key="agent.id", primary_key=True)
    tag_id: UUID = Field(foreign_key="tag.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
