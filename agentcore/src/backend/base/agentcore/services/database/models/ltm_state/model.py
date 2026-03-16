from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class LTMStateBase(SQLModel):
    agent_id: UUID = Field(index=True, unique=True)
    last_processed_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    message_count_since_last: int = Field(default=0)
    last_run_at: datetime | None = Field(default=None)
    enabled: bool = Field(default=True)


class LTMStateTable(LTMStateBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "ltm_state"
    id: UUID = Field(default_factory=uuid4, primary_key=True)


class LTMStateRead(LTMStateBase):
    id: UUID


class LTMStateCreate(LTMStateBase):
    pass


class LTMStateUpdate(SQLModel):
    last_processed_timestamp: datetime | None = None
    message_count_since_last: int | None = None
    last_run_at: datetime | None = None
    enabled: bool | None = None
