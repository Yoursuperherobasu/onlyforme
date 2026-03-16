from __future__ import annotations

import hmac
import os
import re
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import select

from agentcore.api.utils import DbSession
from agentcore.services.database.models.package.model import Package

router = APIRouter(prefix="/package-inventory", tags=["Package Inventory"])

ACTIVE_END_DATE = date(9999, 12, 31)
_VALID_SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


class RequiredByDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=100)


class ManagedPackageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=100)
    version_spec: str | None = Field(default=None, max_length=255)
    source: dict[str, Any] | None = None


class TransitivePackageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=100)
    required_by_details: list[RequiredByDetail] = Field(default_factory=list)
    source: dict[str, Any] | None = None


class PackageSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(min_length=3, max_length=64)
    snapshot_id: str | None = Field(default=None, max_length=100)
    build_id: str | None = Field(default=None, max_length=100)
    commit_sha: str | None = Field(default=None, max_length=64)
    release_id: UUID | None = None
    captured_at: datetime | None = None
    managed: list[ManagedPackageInput] = Field(default_factory=list)
    transitive: list[TransitivePackageInput] = Field(default_factory=list)


@router.post("/snapshots")
async def ingest_snapshot(
    payload: PackageSnapshotInput,
    session: DbSession,
    api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    expected_api_key = os.getenv("PACKAGE_INVENTORY_API_KEY")
    if not expected_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Package inventory API key is not configured in backend environment "
                "(PACKAGE_INVENTORY_API_KEY)."
            ),
        )
    if not api_key or not hmac.compare_digest(api_key, expected_api_key):
        raise HTTPException(status_code=401, detail="Invalid package inventory API key.")

    service_name = payload.service_name.strip().lower()
    if not _VALID_SERVICE_RE.match(service_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "service_name must be lowercase and hyphen-separated "
                "(3-64 chars, alphanumeric plus '-')"
            ),
        )
    if not payload.managed and not payload.transitive:
        raise HTTPException(status_code=400, detail="Snapshot must include at least one package.")

    now = payload.captured_at.astimezone(timezone.utc) if payload.captured_at else datetime.now(timezone.utc)
    today = now.date()

    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for item in payload.managed:
        key = (_normalize(item.name), "managed")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        rows.append(
            {
                "name": item.name.strip(),
                "service_name": service_name,
                "version": item.version.strip(),
                "version_spec": (item.version_spec or "").strip() or None,
                "package_type": "managed",
                "snapshot_id": payload.snapshot_id,
                "build_id": payload.build_id,
                "commit_sha": payload.commit_sha,
                "release_id": payload.release_id,
                "required_by": None,
                "required_by_details": None,
                "source": item.source or None,
            }
        )

    for item in payload.transitive:
        key = (_normalize(item.name), "transitive")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        required_by_details = [
            {"name": d.name.strip(), "version": d.version.strip()}
            for d in item.required_by_details
            if d.name.strip()
        ]
        required_by = sorted({_normalize(d["name"]) for d in required_by_details})
        rows.append(
            {
                "name": item.name.strip(),
                "service_name": service_name,
                "version": item.version.strip(),
                "version_spec": None,
                "package_type": "transitive",
                "snapshot_id": payload.snapshot_id,
                "build_id": payload.build_id,
                "commit_sha": payload.commit_sha,
                "release_id": payload.release_id,
                "required_by": required_by or None,
                "required_by_details": required_by_details or None,
                "source": item.source or None,
            }
        )

    current_rows = (
        await session.exec(
            select(Package).where(
                Package.service_name == service_name,
                Package.end_date == ACTIVE_END_DATE,
            )
        )
    ).all()
    current_map = {
        (_normalize(row.name), row.package_type): row
        for row in current_rows
    }

    incoming_keys: set[tuple[str, str]] = set()
    inserted = 0
    updated = 0
    unchanged = 0
    closed = 0

    for row in rows:
        key = (_normalize(row["name"]), row["package_type"])
        incoming_keys.add(key)
        existing = current_map.get(key)

        if existing is None:
            session.add(
                Package(
                    name=row["name"],
                    service_name=row["service_name"],
                    version=row["version"],
                    version_spec=row["version_spec"],
                    package_type=row["package_type"],
                    snapshot_id=row["snapshot_id"],
                    build_id=row["build_id"],
                    commit_sha=row["commit_sha"],
                    release_id=row["release_id"],
                    required_by=row["required_by"],
                    required_by_details=row["required_by_details"],
                    start_date=today,
                    end_date=ACTIVE_END_DATE,
                    source=row["source"],
                    synced_at=now,
                )
            )
            inserted += 1
            continue

        same_payload = (
            existing.version == row["version"]
            and (existing.version_spec or None) == (row["version_spec"] or None)
            and (existing.snapshot_id or None) == (row["snapshot_id"] or None)
            and (existing.build_id or None) == (row["build_id"] or None)
            and (existing.commit_sha or None) == (row["commit_sha"] or None)
            and existing.release_id == row["release_id"]
            and (existing.required_by or None) == (row["required_by"] or None)
            and (existing.required_by_details or None) == (row["required_by_details"] or None)
            and (existing.source or None) == (row["source"] or None)
        )
        if same_payload:
            existing.synced_at = now
            unchanged += 1
            continue

        # Keep one active version per day to avoid same-day close/re-open ambiguity.
        if existing.start_date == today:
            existing.version = row["version"]
            existing.version_spec = row["version_spec"]
            existing.snapshot_id = row["snapshot_id"]
            existing.build_id = row["build_id"]
            existing.commit_sha = row["commit_sha"]
            existing.release_id = row["release_id"]
            existing.required_by = row["required_by"]
            existing.required_by_details = row["required_by_details"]
            existing.source = row["source"]
            existing.synced_at = now
            updated += 1
            continue

        existing.end_date = today
        existing.synced_at = now
        session.add(
            Package(
                name=row["name"],
                service_name=row["service_name"],
                version=row["version"],
                version_spec=row["version_spec"],
                package_type=row["package_type"],
                snapshot_id=row["snapshot_id"],
                build_id=row["build_id"],
                commit_sha=row["commit_sha"],
                release_id=row["release_id"],
                required_by=row["required_by"],
                required_by_details=row["required_by_details"],
                start_date=today,
                end_date=ACTIVE_END_DATE,
                source=row["source"],
                synced_at=now,
            )
        )
        updated += 1

    for key, existing in current_map.items():
        if key in incoming_keys:
            continue
        existing.end_date = today
        existing.synced_at = now
        closed += 1

    await session.commit()

    return {
        "service_name": service_name,
        "snapshot_id": payload.snapshot_id,
        "received": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "closed": closed,
    }
