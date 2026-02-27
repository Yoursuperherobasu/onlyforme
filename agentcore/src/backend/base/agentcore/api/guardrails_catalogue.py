from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, tuple_
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.department.model import Department
from agentcore.services.database.models.guardrail_catalogue.model import GuardrailCatalogue
from agentcore.services.database.models.model_registry.model import ModelRegistry
from agentcore.services.database.models.organization.model import Organization
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership
from agentcore.services.guardrails import invalidate_nemo_guardrail_cache, is_nemo_runtime_config_ready

router = APIRouter(prefix="/guardrails-catalogue", tags=["Guardrails Catalogue"])


class GuardrailPayload(BaseModel):
    name: str
    description: str | None = None
    provider: str | None = None
    modelRegistryId: UUID | None = None
    category: str
    status: str = "active"
    rulesCount: int = 0
    isCustom: bool = False
    runtimeConfig: dict[str, Any] | None = None
    org_id: UUID | None = None
    dept_id: UUID | None = None


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
    filters = [and_(GuardrailCatalogue.org_id.is_(None), GuardrailCatalogue.dept_id.is_(None))]

    if org_ids:
        filters.append(and_(GuardrailCatalogue.org_id.in_(list(org_ids)), GuardrailCatalogue.dept_id.is_(None)))

    if dept_pairs:
        filters.append(tuple_(GuardrailCatalogue.org_id, GuardrailCatalogue.dept_id).in_(dept_pairs))

    return filters


async def _validate_scope_refs(session: DbSession, payload: GuardrailPayload) -> None:
    if payload.dept_id and not payload.org_id:
        raise HTTPException(status_code=400, detail="dept_id requires org_id")

    if payload.org_id:
        org = await session.get(Organization, payload.org_id)
        if not org:
            raise HTTPException(status_code=400, detail="Invalid org_id")

    if payload.dept_id:
        dept = (
            await session.exec(
                select(Department).where(
                    Department.id == payload.dept_id,
                    Department.org_id == payload.org_id,
                )
            )
        ).first()
        if not dept:
            raise HTTPException(status_code=400, detail="Invalid dept_id for org_id")


def _validate_runtime_config_shape(payload: GuardrailPayload) -> None:
    runtime_config = payload.runtimeConfig
    if runtime_config is None:
        return
    if not isinstance(runtime_config, dict):
        raise HTTPException(status_code=400, detail="runtimeConfig must be a JSON object")

    for key in ("config_yml", "configYml", "config.yml", "rails_co", "railsCo", "rails.co", "prompts_yml"):
        if key not in runtime_config:
            continue
        value = runtime_config.get(key)
        if value is not None and not isinstance(value, str):
            raise HTTPException(status_code=400, detail=f"runtimeConfig.{key} must be a string")

    files = runtime_config.get("files")
    if files is None:
        return
    if not isinstance(files, dict):
        raise HTTPException(status_code=400, detail="runtimeConfig.files must be an object")
    invalid_entry = next(
        ((k, v) for k, v in files.items() if not isinstance(k, str) or not isinstance(v, str)),
        None,
    )
    if invalid_entry:
        raise HTTPException(status_code=400, detail="runtimeConfig.files must map string path to string content")


def _extract_runtime_string(runtime_config: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = runtime_config.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            normalized = value.strip()
            if normalized and normalized not in {".", "..."}:
                return normalized
    return None


def _normalize_runtime_config_payload(runtime_config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(runtime_config, dict):
        return None

    config_yml = _extract_runtime_string(runtime_config, ("config_yml", "configYml", "config.yml"))
    rails_co = _extract_runtime_string(runtime_config, ("rails_co", "railsCo", "rails.co"))
    prompts_yml = _extract_runtime_string(runtime_config, ("prompts_yml", "promptsYml", "prompts.yml"))
    files = runtime_config.get("files")

    normalized_files: dict[str, str] | None = None
    if isinstance(files, dict):
        parsed_files = {k.strip(): v for k, v in files.items() if isinstance(k, str) and isinstance(v, str) and k.strip()}
        if parsed_files:
            normalized_files = parsed_files

    normalized: dict[str, Any] = {}
    if config_yml:
        normalized["config_yml"] = config_yml
    if rails_co:
        normalized["rails_co"] = rails_co
    if prompts_yml:
        normalized["prompts_yml"] = prompts_yml
    if normalized_files:
        normalized["files"] = normalized_files

    return normalized or None


def _serialize_guardrail(row: GuardrailCatalogue, model_row: ModelRegistry | None = None) -> dict:
    model_provider = row.provider
    model_name: str | None = None
    model_display_name: str | None = None
    if model_row:
        model_provider = model_row.provider or row.provider
        model_name = model_row.model_name
        model_display_name = model_row.display_name

    model_registry_ready_id = row.model_registry_id if model_row else None

    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description or "",
        "provider": model_provider,
        "modelRegistryId": str(row.model_registry_id) if row.model_registry_id else None,
        "modelName": model_name,
        "modelDisplayName": model_display_name,
        "category": row.category,
        "status": row.status,
        "rulesCount": int(row.rules_count or 0),
        "isCustom": bool(row.is_custom),
        "runtimeConfig": row.runtime_config,
        "runtimeReady": is_nemo_runtime_config_ready(row.runtime_config, model_registry_ready_id),
        "org_id": str(row.org_id) if row.org_id else None,
        "dept_id": str(row.dept_id) if row.dept_id else None,
    }


async def _resolve_guardrail_model_registry(
    session: DbSession,
    model_registry_id: UUID | None,
) -> ModelRegistry:
    if model_registry_id is None:
        raise HTTPException(status_code=400, detail="modelRegistryId is required")

    model_row = await session.get(ModelRegistry, model_registry_id)
    if not model_row:
        raise HTTPException(status_code=400, detail="Invalid modelRegistryId")
    if not bool(model_row.is_active):
        raise HTTPException(status_code=400, detail="Selected model registry entry is inactive")
    return model_row


@router.get("")
@router.get("/")
async def list_guardrails_catalogue(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> list[dict]:
    filters = await _visibility_filters(session, current_user)
    query = select(GuardrailCatalogue).order_by(GuardrailCatalogue.name.asc())
    if filters:
        query = query.where(or_(*filters))

    rows = (await session.exec(query)).all()
    model_ids = {row.model_registry_id for row in rows if row.model_registry_id}
    model_by_id: dict[UUID, ModelRegistry] = {}
    if model_ids:
        model_rows = (
            await session.exec(select(ModelRegistry).where(ModelRegistry.id.in_(list(model_ids))))
        ).all()
        model_by_id = {model.id: model for model in model_rows}

    return [_serialize_guardrail(row, model_by_id.get(row.model_registry_id)) for row in rows]


@router.post("")
@router.post("/")
async def create_guardrail_catalogue(
    payload: GuardrailPayload,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    await _validate_scope_refs(session, payload)
    model_row = await _resolve_guardrail_model_registry(session, payload.modelRegistryId)
    _validate_runtime_config_shape(payload)
    normalized_runtime_config = _normalize_runtime_config_payload(payload.runtimeConfig)
    if payload.status == "active" and not normalized_runtime_config:
        raise HTTPException(
            status_code=400,
            detail="Active guardrails require runtimeConfig with at least config_yml.",
        )
    if payload.status == "active" and not is_nemo_runtime_config_ready(normalized_runtime_config, model_row.id):
        raise HTTPException(
            status_code=400,
            detail="runtimeConfig is incomplete. Provide a valid config_yml (rails_co is optional).",
        )
    now = datetime.now(timezone.utc)
    row = GuardrailCatalogue(
        name=payload.name,
        description=payload.description,
        provider=model_row.provider,
        model_registry_id=model_row.id,
        category=payload.category,
        status=payload.status,
        rules_count=payload.rulesCount,
        is_custom=payload.isCustom,
        runtime_config=normalized_runtime_config,
        org_id=payload.org_id,
        dept_id=payload.dept_id,
        created_by=current_user.id,
        updated_by=current_user.id,
        created_at=now,
        updated_at=now,
        published_by=current_user.id if payload.status == "active" else None,
        published_at=now if payload.status == "active" else None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    invalidate_nemo_guardrail_cache(row.id)
    return _serialize_guardrail(row, model_row)


@router.patch("/{guardrail_id}")
async def update_guardrail_catalogue(
    guardrail_id: UUID,
    payload: GuardrailPayload,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    row = await session.get(GuardrailCatalogue, guardrail_id)
    if not row:
        raise HTTPException(status_code=404, detail="Guardrail not found")

    await _validate_scope_refs(session, payload)
    model_row = await _resolve_guardrail_model_registry(session, payload.modelRegistryId)
    _validate_runtime_config_shape(payload)
    normalized_runtime_config = _normalize_runtime_config_payload(payload.runtimeConfig)
    if payload.status == "active" and not normalized_runtime_config:
        raise HTTPException(
            status_code=400,
            detail="Active guardrails require runtimeConfig with at least config_yml.",
        )
    if payload.status == "active" and not is_nemo_runtime_config_ready(normalized_runtime_config, model_row.id):
        raise HTTPException(
            status_code=400,
            detail="runtimeConfig is incomplete. Provide a valid config_yml (rails_co is optional).",
        )
    now = datetime.now(timezone.utc)

    row.name = payload.name
    row.description = payload.description
    row.provider = model_row.provider
    row.model_registry_id = model_row.id
    row.category = payload.category
    row.status = payload.status
    row.rules_count = payload.rulesCount
    row.is_custom = payload.isCustom
    row.runtime_config = normalized_runtime_config
    row.org_id = payload.org_id
    row.dept_id = payload.dept_id
    row.updated_by = current_user.id
    row.updated_at = now
    if payload.status == "active":
        row.published_by = current_user.id
        row.published_at = now

    await session.commit()
    await session.refresh(row)
    invalidate_nemo_guardrail_cache(row.id)
    return _serialize_guardrail(row, model_row)


@router.delete("/{guardrail_id}")
async def delete_guardrail_catalogue(
    guardrail_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    if not _is_root_user(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Root admin only.")

    row = await session.get(GuardrailCatalogue, guardrail_id)
    if not row:
        raise HTTPException(status_code=404, detail="Guardrail not found")

    await session.delete(row)
    await session.commit()
    invalidate_nemo_guardrail_cache(guardrail_id)
    return {"message": "Guardrail deleted successfully"}
