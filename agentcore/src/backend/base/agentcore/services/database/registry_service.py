"""Agent Registry service — auto-list / delist logic.

Business rule:
    An agent appears in ``agent_registry`` when it has a deployment (UAT **or**
    PROD) where **all four** conditions are met:

        • ``is_active  = True``
        • ``is_enabled = True``
        • ``status     = PUBLISHED``
        • ``visibility = PUBLIC``

    Each (agent, env) pair maps to at most **one** registry row.  When none of
    that agent's deployments in the given environment satisfy the conditions the
    corresponding registry entry is removed (delisted).

This module exposes helpers that should be called from the publish endpoint
and from any action endpoint that mutates ``is_active``, ``visibility``, or
``status``:

    • ``sync_agent_registry``    – re-evaluate and upsert/remove the registry entry
    • ``delist_from_registry``   – unconditionally remove the registry row(s)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from agentcore.services.database.models.agent_deployment_prod.model import (
    AgentDeploymentProd,
    DeploymentPRODStatusEnum,
    ProdDeploymentVisibilityEnum,
)
from agentcore.services.database.models.agent_deployment_uat.model import (
    AgentDeploymentUAT,
    DeploymentUATStatusEnum,
    DeploymentVisibilityEnum,
)
from agentcore.services.database.models.agent_registry.model import (
    AgentRegistry,
    RegistryDeploymentEnvEnum,
    RegistryVisibilityEnum,
)


# ═══════════════════════════════════════════════════════════════════════════
# Sync (upsert / remove)
# ═══════════════════════════════════════════════════════════════════════════


async def sync_agent_registry(
    session: AsyncSession,
    *,
    agent_id: UUID,
    org_id: UUID,
    acted_by: UUID,
    deployment_env: RegistryDeploymentEnvEnum,
) -> AgentRegistry | None:
    """Evaluate the deployment state for *one* environment and upsert / remove
    the corresponding registry entry.

    Logic:
        1. Find the **latest** deployment (UAT or PROD) for this agent where
           ``is_active=True``, ``is_enabled=True``, ``status=PUBLISHED``,
           ``visibility=PUBLIC``.
        2. If one exists → upsert the ``agent_registry`` row (create or update).
        3. If none exists → delete any existing registry row for that env (delist).

    Args:
        session:        The current async DB session (caller manages commit).
        agent_id:       The agent whose registry presence should be re-evaluated.
        org_id:         Organization the agent belongs to.
        acted_by:       User ID performing the action (used for ``listed_by``).
        deployment_env: Which environment to evaluate — UAT or PROD.

    Returns:
        The upserted ``AgentRegistry`` row, or ``None`` if the agent was delisted.
    """

    # ── 1. Find the best candidate deployment ─────────────────────
    candidate = await _find_qualifying_deployment(session, agent_id, deployment_env)

    # ── 2. Fetch existing registry row (if any) for this env ──────
    existing = (
        await session.exec(
            select(AgentRegistry).where(
                AgentRegistry.agent_id == agent_id,
                AgentRegistry.deployment_env == deployment_env,
            )
        )
    ).first()

    now = datetime.now(timezone.utc)
    env_label = deployment_env.value  # "UAT" or "PROD"

    # ── 3a. Candidate found → upsert ─────────────────────────────
    if candidate is not None:
        if existing is not None:
            existing.agent_deployment_id = candidate.id
            existing.title = candidate.agent_name
            existing.summary = candidate.agent_description
            existing.visibility = RegistryVisibilityEnum.PUBLIC
            existing.updated_at = now
            session.add(existing)
            logger.info(
                f"Registry UPDATED [{env_label}] for agent {agent_id} → "
                f"deployment {candidate.id} v{candidate.version_number}"
            )
            return existing

        registry_entry = AgentRegistry(
            org_id=org_id,
            agent_id=agent_id,
            agent_deployment_id=candidate.id,
            deployment_env=deployment_env,
            title=candidate.agent_name,
            summary=candidate.agent_description,
            visibility=RegistryVisibilityEnum.PUBLIC,
            listed_by=acted_by,
            listed_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(registry_entry)
        logger.info(
            f"Registry LISTED [{env_label}] agent {agent_id} → "
            f"deployment {candidate.id} v{candidate.version_number}"
        )
        return registry_entry

    # ── 3b. No qualifying deployment → delist ─────────────────────
    if existing is not None:
        await session.delete(existing)
        logger.info(
            f"Registry DELISTED [{env_label}] agent {agent_id} "
            f"(no active+public {env_label} deployment)"
        )

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Delist (unconditional remove)
# ═══════════════════════════════════════════════════════════════════════════


async def delist_from_registry(
    session: AsyncSession,
    *,
    agent_id: UUID,
    deployment_env: RegistryDeploymentEnvEnum | None = None,
) -> bool:
    """Unconditionally remove registry entry/entries for an agent.

    Args:
        agent_id:       The agent to delist.
        deployment_env: If provided, remove only the row for that env.
                        If ``None``, remove **all** env rows for the agent.

    Returns:
        ``True`` if at least one row was deleted, ``False`` otherwise.
    """
    stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
    if deployment_env is not None:
        stmt = stmt.where(AgentRegistry.deployment_env == deployment_env)

    rows = (await session.exec(stmt)).all()
    if rows:
        for row in rows:
            await session.delete(row)
        envs = ", ".join(r.deployment_env.value for r in rows)
        logger.info(f"Registry DELISTED agent {agent_id} [{envs}] (explicit delist)")
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


async def _find_qualifying_deployment(
    session: AsyncSession,
    agent_id: UUID,
    deployment_env: RegistryDeploymentEnvEnum,
):
    """Return the latest deployment matching all four listing conditions,
    or ``None`` if no qualifying row exists.
    """
    if deployment_env == RegistryDeploymentEnvEnum.PROD:
        stmt = (
            select(AgentDeploymentProd)
            .where(
                AgentDeploymentProd.agent_id == agent_id,
                AgentDeploymentProd.is_active == True,  # noqa: E712
                AgentDeploymentProd.is_enabled == True,  # noqa: E712
                AgentDeploymentProd.status == DeploymentPRODStatusEnum.PUBLISHED,
                AgentDeploymentProd.visibility == ProdDeploymentVisibilityEnum.PUBLIC,
            )
            .order_by(col(AgentDeploymentProd.version_number).desc())
            .limit(1)
        )
    else:
        stmt = (
            select(AgentDeploymentUAT)
            .where(
                AgentDeploymentUAT.agent_id == agent_id,
                AgentDeploymentUAT.is_active == True,  # noqa: E712
                AgentDeploymentUAT.is_enabled == True,  # noqa: E712
                AgentDeploymentUAT.status == DeploymentUATStatusEnum.PUBLISHED,
                AgentDeploymentUAT.visibility == DeploymentVisibilityEnum.PUBLIC,
            )
            .order_by(col(AgentDeploymentUAT.version_number).desc())
            .limit(1)
        )

    return (await session.exec(stmt)).first()


