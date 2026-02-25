from uuid import UUID

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.trigger_config.crud import (
    create_trigger_config,
    delete_trigger_config,
    get_trigger_config_by_id,
    get_trigger_execution_logs,
    get_triggers_by_agent_id,
    toggle_trigger,
    update_trigger_config,
)
from agentcore.services.database.models.trigger_config.model import (
    TriggerConfigCreate,
    TriggerConfigRead,
    TriggerConfigUpdate,
    TriggerExecutionLogRead,
    TriggerTypeEnum,
)

router = APIRouter(prefix="/triggers", tags=["Triggers"])


class TriggerCreateRequest(BaseModel):
    trigger_type: TriggerTypeEnum
    trigger_config: dict
    environment: str = "dev"
    version: str | None = None
    deployment_id: UUID | None = None


class TriggerUpdateRequest(BaseModel):
    trigger_config: dict | None = None
    is_active: bool | None = None
    environment: str | None = None
    version: str | None = None


@router.get("/{agent_id}", status_code=200)
async def list_triggers_for_agent(
    *,
    session: DbSession,
    agent_id: UUID,
    active_only: bool = False,
    current_user: CurrentActiveUser,
) -> list[TriggerConfigRead]:
    """List all trigger configurations for an agent."""
    triggers = await get_triggers_by_agent_id(session, agent_id, active_only=active_only)
    return [TriggerConfigRead.model_validate(t) for t in triggers]


@router.post("/{agent_id}", status_code=201)
async def create_trigger(
    *,
    session: DbSession,
    agent_id: UUID,
    request: TriggerCreateRequest,
    current_user: CurrentActiveUser,
) -> TriggerConfigRead:
    """Create a new trigger configuration for an agent."""
    data = TriggerConfigCreate(
        agent_id=agent_id,
        deployment_id=request.deployment_id,
        trigger_type=request.trigger_type,
        trigger_config=request.trigger_config,
        environment=request.environment,
        version=request.version,
        created_by=current_user.id,
    )
    record = await create_trigger_config(session, data)

    # Register with the appropriate service
    try:
        await _register_trigger(record)
    except Exception as e:
        logger.warning(f"Failed to register trigger {record.id} with service: {e}")

    return TriggerConfigRead.model_validate(record)


@router.patch("/{trigger_id}", status_code=200)
async def update_trigger(
    *,
    session: DbSession,
    trigger_id: UUID,
    request: TriggerUpdateRequest,
    current_user: CurrentActiveUser,
) -> TriggerConfigRead:
    """Update a trigger configuration."""
    data = TriggerConfigUpdate(**request.model_dump(exclude_unset=True))
    record = await update_trigger_config(session, trigger_id, data)
    if not record:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Re-register with updated config
    try:
        await _unregister_trigger(trigger_id, record.trigger_type)
        if record.is_active:
            await _register_trigger(record)
    except Exception as e:
        logger.warning(f"Failed to re-register trigger {trigger_id}: {e}")

    return TriggerConfigRead.model_validate(record)


@router.delete("/{trigger_id}", status_code=204)
async def delete_trigger(
    *,
    session: DbSession,
    trigger_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a trigger configuration."""
    record = await get_trigger_config_by_id(session, trigger_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Unregister from service
    try:
        await _unregister_trigger(trigger_id, record.trigger_type)
    except Exception as e:
        logger.warning(f"Failed to unregister trigger {trigger_id}: {e}")

    deleted = await delete_trigger_config(session, trigger_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trigger not found")


@router.post("/{trigger_id}/toggle", status_code=200)
async def toggle_trigger_endpoint(
    *,
    session: DbSession,
    trigger_id: UUID,
    current_user: CurrentActiveUser,
) -> TriggerConfigRead:
    """Toggle a trigger's active status."""
    record = await toggle_trigger(session, trigger_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Register or unregister based on new state
    try:
        if record.is_active:
            await _register_trigger(record)
        else:
            await _unregister_trigger(trigger_id, record.trigger_type)
    except Exception as e:
        logger.warning(f"Failed to toggle trigger {trigger_id} registration: {e}")

    return TriggerConfigRead.model_validate(record)


@router.get("/{trigger_id}/logs", status_code=200)
async def get_trigger_logs(
    *,
    session: DbSession,
    trigger_id: UUID,
    limit: int = 50,
    current_user: CurrentActiveUser,
) -> list[TriggerExecutionLogRead]:
    """Get execution logs for a trigger."""
    logs = await get_trigger_execution_logs(session, trigger_id, limit=limit)
    return [TriggerExecutionLogRead.model_validate(log) for log in logs]


# ── Helper functions ─────────────────────────────────────────────────────


async def _register_trigger(record) -> None:
    """Register a trigger with the appropriate backend service."""
    from agentcore.services.deps import get_scheduler_service, get_trigger_service

    trigger_type = record.trigger_type
    config = record.trigger_config or {}

    if trigger_type == TriggerTypeEnum.SCHEDULE:
        scheduler = get_scheduler_service()
        cron_expr = config.get("cron_expression")
        interval_minutes = config.get("interval_minutes")
        if cron_expr:
            await scheduler.add_schedule(
                trigger_config_id=record.id,
                cron_expr=cron_expr,
                agent_id=record.agent_id,
                environment=record.environment,
                version=record.version or "",
            )
        elif interval_minutes:
            await scheduler.add_schedule(
                trigger_config_id=record.id,
                cron_expr=None,
                agent_id=record.agent_id,
                environment=record.environment,
                version=record.version or "",
                interval_minutes=interval_minutes,
            )

    elif trigger_type == TriggerTypeEnum.FOLDER_MONITOR:
        trigger_service = get_trigger_service()
        await trigger_service.register_folder_monitor(record)



async def _unregister_trigger(trigger_id: UUID, trigger_type: TriggerTypeEnum) -> None:
    """Unregister a trigger from its backend service."""
    from agentcore.services.deps import get_scheduler_service, get_trigger_service

    if trigger_type == TriggerTypeEnum.SCHEDULE:
        scheduler = get_scheduler_service()
        await scheduler.remove_schedule(trigger_id)
    else:
        trigger_service = get_trigger_service()
        await trigger_service.unregister(trigger_id)
