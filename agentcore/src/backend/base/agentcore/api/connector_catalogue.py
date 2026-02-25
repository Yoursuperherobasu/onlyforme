from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, tuple_
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.department.model import Department
from agentcore.services.database.models.organization.model import Organization
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership
from agentcore.services.database.models.connector_catalogue.model import ConnectorCatalogue

router = APIRouter(prefix="/connector-catalogue", tags=["Connector Catalogue"])


# ---------- Encryption helpers ----------

_FERNET_KEY = None


def _derive_encryption_key() -> str:
    """Derive a deterministic Fernet key from WEBUI_SECRET_KEY.

    This ensures the same key is used across server restarts, so
    previously encrypted passwords remain decryptable.
    Same approach as Model Registry (registry_model.py).
    """
    import base64
    import hashlib
    import os

    # Allow explicit override via env var
    explicit = os.getenv("CONNECTOR_ENCRYPTION_KEY", "")
    if explicit:
        return explicit

    # Derive deterministically from the platform secret
    raw = os.getenv("WEBUI_SECRET_KEY", "default-agentcore-connector-key")
    derived = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(derived).decode()


def _get_fernet():
    global _FERNET_KEY
    if _FERNET_KEY is None:
        from cryptography.fernet import Fernet

        key = _derive_encryption_key()
        _FERNET_KEY = Fernet(key.encode() if isinstance(key, str) else key)
    return _FERNET_KEY


def _encrypt_password(password: str) -> str:
    return _get_fernet().encrypt(password.encode()).decode()


def _decrypt_password(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


# ---------- Payloads ----------

class ConnectorPayload(BaseModel):
    name: str
    description: str | None = None
    provider: str  # postgresql, oracle, sqlserver, mysql
    host: str
    port: int
    database_name: str
    schema_name: str = "public"
    username: str
    password: str
    ssl_enabled: bool = False
    is_custom: bool = False
    org_id: UUID | None = None
    dept_id: UUID | None = None


class ConnectorUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    provider: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    schema_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool | None = None
    is_custom: bool | None = None
    org_id: UUID | None = None
    dept_id: UUID | None = None


class TestConnectionPayload(BaseModel):
    provider: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    schema_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool | None = None


# ---------- RBAC helpers (same pattern as VectorDB) ----------

def _is_root_user(current_user: CurrentActiveUser) -> bool:
    return str(getattr(current_user, "role", "")).lower() == "root"


async def _get_scope_memberships(session: DbSession, user_id: UUID) -> tuple[set[UUID], list[tuple[UUID, UUID]]]:
    org_rows = (
        await session.exec(
            select(UserOrganizationMembership.org_id).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.status.in_(["accepted", "active"]),
            )
        )
    ).all()
    dept_rows = (
        await session.exec(
            select(UserDepartmentMembership.org_id, UserDepartmentMembership.department_id).where(
                UserDepartmentMembership.user_id == user_id,
                UserDepartmentMembership.status == "active",
            )
        )
    ).all()
    org_ids = {r if isinstance(r, UUID) else r[0] for r in org_rows}
    return org_ids, [(row[0], row[1]) for row in dept_rows]


async def _visibility_filters(session: DbSession, current_user: CurrentActiveUser):
    if _is_root_user(current_user):
        return []
    org_ids, dept_pairs = await _get_scope_memberships(session, current_user.id)
    filters = [and_(ConnectorCatalogue.org_id.is_(None), ConnectorCatalogue.dept_id.is_(None))]
    if org_ids:
        filters.append(and_(ConnectorCatalogue.org_id.in_(list(org_ids)), ConnectorCatalogue.dept_id.is_(None)))
    if dept_pairs:
        filters.append(tuple_(ConnectorCatalogue.org_id, ConnectorCatalogue.dept_id).in_(dept_pairs))
    return filters


async def _validate_scope_refs(session: DbSession, org_id: UUID | None, dept_id: UUID | None) -> None:
    if dept_id and not org_id:
        raise HTTPException(status_code=400, detail="dept_id requires org_id")
    if org_id:
        org = await session.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=400, detail="Invalid org_id")
    if dept_id:
        dept = (
            await session.exec(
                select(Department).where(Department.id == dept_id, Department.org_id == org_id)
            )
        ).first()
        if not dept:
            raise HTTPException(status_code=400, detail="Invalid dept_id for org_id")


# ---------- Serialization ----------

def _serialize_connector(row: ConnectorCatalogue) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description or "",
        "provider": row.provider,
        "host": row.host,
        "port": row.port,
        "database_name": row.database_name,
        "schema_name": row.schema_name,
        "username": row.username,
        "ssl_enabled": row.ssl_enabled,
        "status": row.status,
        "tables_metadata": row.tables_metadata,
        "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
        "isCustom": bool(row.is_custom),
        "org_id": str(row.org_id) if row.org_id else None,
        "dept_id": str(row.dept_id) if row.dept_id else None,
    }


# ---------- DB Connection helper ----------

def _test_db_connection(provider: str, host: str, port: int, database_name: str,
                        schema_name: str, username: str, password: str,
                        ssl_enabled: bool) -> dict:
    """Test a database connection and optionally fetch schema metadata."""
    start = time.time()

    if provider == "postgresql":
        import psycopg2
        conn_params = {
            "host": host,
            "port": port,
            "dbname": database_name,
            "user": username,
            "password": password,
            "connect_timeout": 10,
        }
        if ssl_enabled:
            conn_params["sslmode"] = "require"

        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        cur.execute("SELECT 1")

        # Fetch table/column metadata
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name NOT LIKE 'pg_%%'
              AND table_name NOT LIKE 'sql_%%'
            ORDER BY table_name, ordinal_position
        """, (schema_name,))
        columns = cur.fetchall()

        tables = {}
        for tbl, col, dtype, nullable, default in columns:
            if tbl not in tables:
                tables[tbl] = {"table_name": tbl, "columns": []}
            tables[tbl]["columns"].append({
                "name": col,
                "type": dtype,
                "nullable": nullable == "YES",
            })

        # Get row counts
        for tbl in tables:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{schema_name}"."{tbl}"')
                tables[tbl]["row_count"] = cur.fetchone()[0]
            except Exception:
                tables[tbl]["row_count"] = None

        cur.close()
        conn.close()
        latency_ms = round((time.time() - start) * 1000, 2)

        return {
            "success": True,
            "message": f"Connected successfully. Found {len(tables)} tables.",
            "latency_ms": latency_ms,
            "tables_metadata": list(tables.values()),
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not yet supported. Supported: postgresql",
        )


# ---------- Endpoints ----------

@router.get("")
@router.get("/")
async def list_connectors(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> list[dict]:
    filters = await _visibility_filters(session, current_user)
    query = select(ConnectorCatalogue).order_by(ConnectorCatalogue.name.asc())
    if filters:
        query = query.where(or_(*filters))
    rows = (await session.exec(query)).all()
    return [_serialize_connector(row) for row in rows]


@router.post("")
@router.post("/")
async def create_connector(
    payload: ConnectorPayload,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    await _validate_scope_refs(session, payload.org_id, payload.dept_id)
    now = datetime.now(timezone.utc)

    row = ConnectorCatalogue(
        name=payload.name,
        description=payload.description,
        provider=payload.provider.lower(),
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        schema_name=payload.schema_name,
        username=payload.username,
        password_encrypted=_encrypt_password(payload.password),
        ssl_enabled=payload.ssl_enabled,
        status="disconnected",
        is_custom=payload.is_custom,
        org_id=payload.org_id,
        dept_id=payload.dept_id,
        created_by=current_user.id,
        updated_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _serialize_connector(row)


@router.patch("/{connector_id}")
async def update_connector(
    connector_id: UUID,
    payload: ConnectorUpdatePayload,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    row = await session.get(ConnectorCatalogue, connector_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    await _validate_scope_refs(session, payload.org_id, payload.dept_id)
    now = datetime.now(timezone.utc)

    if payload.name is not None:
        row.name = payload.name
    if payload.description is not None:
        row.description = payload.description
    if payload.provider is not None:
        row.provider = payload.provider.lower()
    if payload.host is not None:
        row.host = payload.host
    if payload.port is not None:
        row.port = payload.port
    if payload.database_name is not None:
        row.database_name = payload.database_name
    if payload.schema_name is not None:
        row.schema_name = payload.schema_name
    if payload.username is not None:
        row.username = payload.username
    if payload.password is not None:
        row.password_encrypted = _encrypt_password(payload.password)
    if payload.ssl_enabled is not None:
        row.ssl_enabled = payload.ssl_enabled
    if payload.is_custom is not None:
        row.is_custom = payload.is_custom
    row.org_id = payload.org_id
    row.dept_id = payload.dept_id
    row.updated_by = current_user.id
    row.updated_at = now

    await session.commit()
    await session.refresh(row)
    return _serialize_connector(row)


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    row = await session.get(ConnectorCatalogue, connector_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    await session.delete(row)
    await session.commit()
    return {"message": "Connector deleted successfully"}


@router.post("/{connector_id}/test-connection")
async def test_connector_connection(
    connector_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    override: TestConnectionPayload | None = None,
) -> dict:
    """Test connectivity to the configured database and refresh schema metadata."""
    row = await session.get(ConnectorCatalogue, connector_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    provider = override.provider if override and override.provider else row.provider
    host = override.host if override and override.host else row.host
    port = override.port if override and override.port else row.port
    database_name = override.database_name if override and override.database_name else row.database_name
    schema_name = override.schema_name if override and override.schema_name else row.schema_name
    username = override.username if override and override.username else row.username
    password = override.password if override and override.password else _decrypt_password(row.password_encrypted)
    ssl_enabled = override.ssl_enabled if override and override.ssl_enabled is not None else row.ssl_enabled

    try:
        result = _test_db_connection(provider, host, port, database_name, schema_name, username, password, ssl_enabled)
        now = datetime.now(timezone.utc)
        row.status = "connected"
        row.tables_metadata = result.get("tables_metadata")
        row.last_tested_at = now
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return result
    except HTTPException:
        raise
    except Exception as e:
        now = datetime.now(timezone.utc)
        row.status = "error"
        row.last_tested_at = now
        row.updated_at = now
        await session.commit()
        return {
            "success": False,
            "message": f"Connection failed: {e!s}",
            "latency_ms": None,
            "tables_metadata": None,
        }


@router.post("/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Manually disconnect a connector (set status to 'disconnected')."""
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    row = await session.get(ConnectorCatalogue, connector_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    now = datetime.now(timezone.utc)
    row.status = "disconnected"
    row.updated_at = now
    row.updated_by = current_user.id
    await session.commit()
    await session.refresh(row)
    return {"message": "Connector disconnected", "status": "disconnected"}


@router.get("/{connector_id}/schema")
async def get_connector_schema(
    connector_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Return cached schema metadata for a connector."""
    row = await session.get(ConnectorCatalogue, connector_id)
    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    return {
        "connector_id": str(row.id),
        "connector_name": row.name,
        "provider": row.provider,
        "database_name": row.database_name,
        "schema_name": row.schema_name,
        "status": row.status,
        "tables_metadata": row.tables_metadata or [],
        "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
    }
