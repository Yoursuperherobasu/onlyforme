from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class RolePermission(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "role_permission"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    role_id: UUID = Field(foreign_key="role.id", index=True)
    permission_id: UUID = Field(foreign_key="permission.id", index=True)

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission_pair"),)
