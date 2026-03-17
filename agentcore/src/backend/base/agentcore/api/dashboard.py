from __future__ import annotations

from datetime import datetime, timezone, date, time, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.agent.model import Agent
from agentcore.services.database.models.agent_bundle.model import AgentBundle, BundleTypeEnum
from agentcore.services.database.models.agent_deployment_prod.model import AgentDeploymentProd
from agentcore.services.database.models.agent_deployment_uat.model import AgentDeploymentUAT
from agentcore.services.database.models.approval_request.model import ApprovalRequest
from agentcore.services.database.models.agent_registry.model import AgentRegistryRating
from agentcore.services.database.models.hitl_request.model import HITLRequest
from agentcore.services.database.models.department.model import Department
from agentcore.services.database.models.orch_conversation.model import OrchConversationTable
from agentcore.services.database.models.role.model import Role
from agentcore.services.database.models.user.model import User
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardKpi(BaseModel):
    id: str
    label: str
    value: float | int
    unit: str | None = None


class DashboardSectionResponse(BaseModel):
    section: str
    kpis: list[DashboardKpi]


class TimeseriesPoint(BaseModel):
    date: str
    value: int


class PendingSeriesResponse(BaseModel):
    range: str
    series: list[TimeseriesPoint]


class HitlSeriesResponse(BaseModel):
    range: str
    series: list[TimeseriesPoint]


async def _resolve_super_admin_user_id(
    *,
    session: DbSession,
    org_id: UUID | None,
) -> UUID | None:
    if not org_id:
        return None
    stmt = (
        select(User)
        .join(UserOrganizationMembership, UserOrganizationMembership.user_id == User.id)
        .join(Role, Role.id == UserOrganizationMembership.role_id)
        .where(
            UserOrganizationMembership.org_id == org_id,
            UserOrganizationMembership.status == "active",
            func.lower(Role.name) == "super_admin",
        )
        .order_by(User.create_at.asc())
    )
    rows = (await session.exec(stmt)).all()
    return rows[0].id if rows else None


async def _designated_super_admin_org_ids(
    session: DbSession,
    current_user: CurrentActiveUser,
) -> set[UUID]:
    role = str(getattr(current_user, "role", "")).lower()
    if role != "super_admin":
        return set()
    rows = (
        await session.exec(
            select(UserOrganizationMembership.org_id).where(
                UserOrganizationMembership.user_id == current_user.id,
                UserOrganizationMembership.status == "active",
            )
        )
    ).all()
    org_ids = {r if isinstance(r, UUID) else r[0] for r in rows}
    if not org_ids:
        return set()
    allowed: set[UUID] = set()
    for org_id in org_ids:
        super_admin_id = await _resolve_super_admin_user_id(session=session, org_id=org_id)
        if super_admin_id == current_user.id:
            allowed.add(org_id)
    return allowed


async def _department_admin_dept_ids(
    session: DbSession,
    current_user: CurrentActiveUser,
) -> set[UUID]:
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        return set()
    rows = (
        await session.exec(
            select(Department.id).where(Department.admin_user_id == current_user.id)
        )
    ).all()
    return {r if isinstance(r, UUID) else r[0] for r in rows}


@router.get("/sections/environment-lifecycle", response_model=DashboardSectionResponse, status_code=200)
async def get_lifecycle_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    org_id: UUID | None = Query(default=None, description="Optional org filter for super admin"),
):
    role = str(getattr(current_user, "role", "")).lower()
    if role not in {"super_admin", "root"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    org_ids: set[UUID] | None = None
    if role == "super_admin":
        org_ids = await _designated_super_admin_org_ids(session, current_user)
        if org_id and org_id not in org_ids:
            raise HTTPException(status_code=403, detail="org_id not in your scope")
        if org_id:
            org_ids = {org_id}

    uat_filters = []
    uat_in_uat_filters = [AgentDeploymentUAT.moved_to_prod.is_(False)]
    uat_promoted_filters = [AgentDeploymentUAT.moved_to_prod.is_(True)]
    prod_filters = [AgentDeploymentProd.is_enabled.is_(False)]

    if org_ids is not None:
        if not org_ids:
            return DashboardSectionResponse(
                section="environment_lifecycle",
                kpis=[
                    DashboardKpi(id="agents_in_uat", label="Agents in UAT", value=0),
                    DashboardKpi(id="uat_to_prod_conversion_rate", label="UAT to PROD Conversion Rate", value=0, unit="%"),
                    DashboardKpi(id="deprecated_agent_count", label="Deprecated Agent Count", value=0),
                ],
            )
        uat_filters.append(AgentDeploymentUAT.org_id.in_(list(org_ids)))
        uat_in_uat_filters.append(AgentDeploymentUAT.org_id.in_(list(org_ids)))
        uat_promoted_filters.append(AgentDeploymentUAT.org_id.in_(list(org_ids)))
        prod_filters.append(AgentDeploymentProd.org_id.in_(list(org_ids)))

    uat_total = (
        await session.exec(select(func.count()).where(*uat_filters))
    ).one()
    uat_in_uat = (
        await session.exec(select(func.count()).where(*uat_in_uat_filters))
    ).one()
    uat_promoted = (
        await session.exec(select(func.count()).where(*uat_promoted_filters))
    ).one()
    deprecated_count = (
        await session.exec(select(func.count()).where(*prod_filters))
    ).one()

    total = int(uat_total or 0)
    in_uat = int(uat_in_uat or 0)
    promoted = int(uat_promoted or 0)
    conversion_rate = round((promoted / total) * 100, 2) if in_uat > 0 and total > 0 else 0

    return DashboardSectionResponse(
        section="environment_lifecycle",
        kpis=[
            DashboardKpi(id="agents_in_uat", label="Agents in UAT", value=in_uat),
            DashboardKpi(
                id="uat_to_prod_conversion_rate",
                label="UAT to PROD Conversion Rate",
                value=conversion_rate,
                unit="%",
            ),
            DashboardKpi(
                id="deprecated_agent_count",
                label="Deprecated Agent Count",
                value=int(deprecated_count or 0),
            ),
        ],
    )


@router.get("/sections/governance-guardrail", response_model=DashboardSectionResponse, status_code=200)
async def get_governance_guardrail_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    org_id: UUID | None = Query(default=None, description="Optional org filter for super admin"),
):
    role = str(getattr(current_user, "role", "")).lower()
    if role not in {"super_admin", "root"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    org_ids: set[UUID] | None = None
    if role == "super_admin":
        org_ids = await _designated_super_admin_org_ids(session, current_user)
        if org_id and org_id not in org_ids:
            raise HTTPException(status_code=403, detail="org_id not in your scope")
        if org_id:
            org_ids = {org_id}

    agent_scope_filters = []
    if org_ids is not None:
        if not org_ids:
            return DashboardSectionResponse(
                section="governance_guardrail",
                kpis=[
                    DashboardKpi(id="escalation_to_human_review", label="Escalation to Human Review", value=0),
                    DashboardKpi(id="agents_without_guardrails_pct", label="% Agents Without Guardrails", value=0, unit="%"),
                ],
            )
        agent_scope_filters.append(Agent.org_id.in_(list(org_ids)))

    # Escalation to Human Review: count HITL requests scoped to org via HITLRequest.org_id or Agent.org_id.
    hitl_stmt = (
        select(func.count())
        .select_from(HITLRequest)
        .join(Agent, Agent.id == HITLRequest.agent_id, isouter=True)
    )
    if org_ids is not None:
        hitl_stmt = hitl_stmt.where(func.coalesce(HITLRequest.org_id, Agent.org_id).in_(list(org_ids)))
    escalation_count = (await session.exec(hitl_stmt)).one()

    # % Agents Without Guardrails: total agents vs agents with guardrail bundle.
    total_agents_stmt = select(func.count(func.distinct(Agent.id))).where(Agent.deleted_at.is_(None))
    if agent_scope_filters:
        total_agents_stmt = total_agents_stmt.where(*agent_scope_filters)
    total_agents = (await session.exec(total_agents_stmt)).one()

    guardrail_stmt = (
        select(func.count(func.distinct(AgentBundle.agent_id)))
        .select_from(AgentBundle)
        .join(Agent, Agent.id == AgentBundle.agent_id, isouter=True)
        .where(AgentBundle.bundle_type == BundleTypeEnum.GUARDRAIL)
    )
    if org_ids is not None:
        guardrail_stmt = guardrail_stmt.where(func.coalesce(AgentBundle.org_id, Agent.org_id).in_(list(org_ids)))
    guardrail_agents = (await session.exec(guardrail_stmt)).one()

    total = int(total_agents or 0)
    with_guardrails = int(guardrail_agents or 0)
    without_guardrails = max(total - with_guardrails, 0)
    without_pct = round((without_guardrails / total) * 100, 2) if total else 0

    return DashboardSectionResponse(
        section="governance_guardrail",
        kpis=[
            DashboardKpi(
                id="escalation_to_human_review",
                label="Escalation to Human Review",
                value=int(escalation_count or 0),
            ),
            DashboardKpi(
                id="agents_without_guardrails_pct",
                label="% Agents Without Guardrails",
                value=without_pct,
                unit="%",
            ),
        ],
    )


@router.get("/sections/department-usage", response_model=DashboardSectionResponse, status_code=200)
async def get_department_usage_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dept_ids = await _department_admin_dept_ids(session, current_user)
    if not dept_ids:
        return DashboardSectionResponse(
            section="department_usage",
            kpis=[
                DashboardKpi(id="active_agents_dept_uat", label="Active Agents in Dept (UAT)", value=0),
                DashboardKpi(id="active_agents_dept_prod", label="Active Agents in Dept (PROD)", value=0),
            ],
        )

    uat_active = (
        await session.exec(
            select(func.count())
            .where(
                AgentDeploymentUAT.dept_id.in_(list(dept_ids)),
                AgentDeploymentUAT.is_active.is_(True),
                AgentDeploymentUAT.moved_to_prod.is_(False),
            )
        )
    ).one()
    prod_active = (
        await session.exec(
            select(func.count())
            .where(
                AgentDeploymentProd.dept_id.in_(list(dept_ids)),
                AgentDeploymentProd.is_active.is_(True),
            )
        )
    ).one()

    return DashboardSectionResponse(
        section="department_usage",
        kpis=[
            DashboardKpi(
                id="active_agents_dept_uat",
                label="Active Agents in Dept (UAT)",
                value=int(uat_active or 0),
            ),
            DashboardKpi(
                id="active_agents_dept_prod",
                label="Active Agents in Dept (PROD)",
                value=int(prod_active or 0),
            ),
        ],
    )


@router.get("/sections/department-approval", response_model=DashboardSectionResponse, status_code=200)
async def get_department_approval_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dept_ids = await _department_admin_dept_ids(session, current_user)
    if not dept_ids:
        return DashboardSectionResponse(
            section="department_approval",
            kpis=[
                DashboardKpi(id="pending_approvals", label="Pending Approvals", value=0),
                DashboardKpi(id="rejection_rate", label="Rejection Rate", value=0, unit="%"),
                DashboardKpi(id="avg_approval_time", label="Avg Approval Time", value=0, unit="min"),
            ],
        )

    pending_count = (
        await session.exec(
            select(func.count())
            .where(
                ApprovalRequest.decision.is_(None),
                ApprovalRequest.dept_id.in_(list(dept_ids)),
            )
        )
    ).one()
    decided_count = (
        await session.exec(
            select(func.count())
            .where(
                ApprovalRequest.decision.is_not(None),
                ApprovalRequest.dept_id.in_(list(dept_ids)),
            )
        )
    ).one()
    rejected_count = (
        await session.exec(
            select(func.count())
            .where(
                ApprovalRequest.decision == "REJECTED",
                ApprovalRequest.dept_id.in_(list(dept_ids)),
            )
        )
    ).one()
    avg_seconds = (
        await session.exec(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        ApprovalRequest.reviewed_at - ApprovalRequest.requested_at,
                    )
                )
            )
            .where(
                ApprovalRequest.reviewed_at.is_not(None),
                ApprovalRequest.dept_id.in_(list(dept_ids)),
            )
        )
    ).one()
    decided = int(decided_count or 0)
    rejected = int(rejected_count or 0)
    rejection_rate = round((rejected / decided) * 100, 2) if decided else 0
    avg_minutes = round((float(avg_seconds) / 60), 2) if avg_seconds is not None else 0

    return DashboardSectionResponse(
        section="department_approval",
        kpis=[
            DashboardKpi(
                id="pending_approvals",
                label="Pending Approvals",
                value=int(pending_count or 0),
            ),
            DashboardKpi(
                id="rejection_rate",
                label="Rejection Rate",
                value=rejection_rate,
                unit="%",
            ),
            DashboardKpi(
                id="avg_approval_time",
                label="Avg Approval Time",
                value=avg_minutes,
                unit="min",
            ),
        ],
    )


def _range_to_days(range_key: str) -> int:
    if range_key == "7d":
        return 7
    if range_key == "30d":
        return 30
    if range_key == "12w":
        return 84
    raise HTTPException(status_code=400, detail="Unsupported range")


def _coerce_tz_offset_minutes(tz_offset_minutes: int | None) -> int:
    if tz_offset_minutes is None:
        return 0
    if tz_offset_minutes > 840:
        return 840
    if tz_offset_minutes < -840:
        return -840
    return int(tz_offset_minutes)


def _apply_tz_offset(dt: datetime, tz_offset_minutes: int) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt + timedelta(minutes=tz_offset_minutes)


def _normalize_day(value: date | datetime | str, tz_offset_minutes: int) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return _apply_tz_offset(value, tz_offset_minutes).date()
    parsed = datetime.fromisoformat(str(value))
    return _apply_tz_offset(parsed, tz_offset_minutes).date()


def _local_range_window(days: int, tz_offset_minutes: int) -> tuple[date, datetime, datetime]:
    now_utc = datetime.now(timezone.utc)
    local_now = _apply_tz_offset(now_utc, tz_offset_minutes)
    today_local = local_now.date()
    start_day = today_local - timedelta(days=days - 1)
    # Convert local day bounds back to UTC naive for DB comparisons.
    start_dt = (datetime.combine(start_day, time.min) - timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    end_dt = (datetime.combine(today_local + timedelta(days=1), time.min) - timedelta(minutes=tz_offset_minutes)).replace(tzinfo=None)
    return start_day, start_dt, end_dt


@router.get("/sections/department-approval/pending-series", response_model=PendingSeriesResponse, status_code=200)
async def get_department_approval_pending_series(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    range_key: str = Query(default="7d", alias="range"),
    tz_offset_minutes: int | None = Query(default=None),
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dept_ids = await _department_admin_dept_ids(session, current_user)
    days = _range_to_days(range_key)
    tz_minutes = _coerce_tz_offset_minutes(tz_offset_minutes)
    start_day, start_dt, end_dt = _local_range_window(days, tz_minutes)

    if not dept_ids:
        series = [
            TimeseriesPoint(date=(start_day + timedelta(days=i)).isoformat(), value=0)
            for i in range(days)
        ]
        return PendingSeriesResponse(range=range_key, series=series)

    baseline_pending = (
        await session.exec(
            select(func.count())
            .where(
                ApprovalRequest.dept_id.in_(list(dept_ids)),
                ApprovalRequest.requested_at < start_dt,
                (
                    ApprovalRequest.decision.is_(None)
                    | (ApprovalRequest.reviewed_at.is_not(None) & (ApprovalRequest.reviewed_at >= start_dt))
                ),
            )
        )
    ).one()

    created_rows = (
        await session.exec(
            select(ApprovalRequest.requested_at)
            .where(
                ApprovalRequest.dept_id.in_(list(dept_ids)),
                ApprovalRequest.requested_at >= start_dt,
                ApprovalRequest.requested_at < end_dt,
            )
        )
    ).all()
    decided_rows = (
        await session.exec(
            select(ApprovalRequest.reviewed_at)
            .where(
                ApprovalRequest.decision.is_not(None),
                ApprovalRequest.reviewed_at.is_not(None),
                ApprovalRequest.dept_id.in_(list(dept_ids)),
                ApprovalRequest.reviewed_at >= start_dt,
                ApprovalRequest.reviewed_at < end_dt,
            )
        )
    ).all()

    created_by_day: dict[date, int] = {}
    for row in created_rows:
        value = row[0] if isinstance(row, (list, tuple)) else row
        day = _normalize_day(value, tz_minutes)
        created_by_day[day] = created_by_day.get(day, 0) + 1

    decided_by_day: dict[date, int] = {}
    for row in decided_rows:
        value = row[0] if isinstance(row, (list, tuple)) else row
        day = _normalize_day(value, tz_minutes)
        decided_by_day[day] = decided_by_day.get(day, 0) + 1

    pending = int(baseline_pending or 0)
    series: list[TimeseriesPoint] = []
    for i in range(days):
        day = start_day + timedelta(days=i)
        pending += created_by_day.get(day, 0) - decided_by_day.get(day, 0)
        if pending < 0:
            pending = 0
        series.append(TimeseriesPoint(date=day.isoformat(), value=pending))

    return PendingSeriesResponse(range=range_key, series=series)


@router.get("/sections/department-hitl", response_model=DashboardSectionResponse, status_code=200)
async def get_department_hitl_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dept_ids = await _department_admin_dept_ids(session, current_user)
    if not dept_ids:
        return DashboardSectionResponse(
            section="department_hitl",
            kpis=[
                DashboardKpi(id="hitl_invocation_rate", label="HITL Invocation Rate", value=0, unit="%"),
                DashboardKpi(id="avg_hitl_response_time", label="Avg HITL Response Time", value=0, unit="min"),
            ],
        )

    total_agents = (
        await session.exec(
            select(func.count(func.distinct(Agent.id))).where(
                Agent.dept_id.in_(list(dept_ids)),
                Agent.deleted_at.is_(None),
            )
        )
    ).one()
    hitl_total = (
        await session.exec(
            select(func.count())
            .where(HITLRequest.dept_id.in_(list(dept_ids)))
        )
    ).one()

    decided_rows = (
        await session.exec(
            select(HITLRequest.requested_at, HITLRequest.decided_at)
            .where(
                HITLRequest.dept_id.in_(list(dept_ids)),
                HITLRequest.decided_at.is_not(None),
            )
        )
    ).all()

    total_agents_count = int(total_agents or 0)
    hitl_total_count = int(hitl_total or 0)
    invocation_rate = int(round((hitl_total_count / total_agents_count) * 100)) if total_agents_count else 0

    total_minutes = 0.0
    decided_count = 0
    for row in decided_rows:
        requested_at = row[0] if isinstance(row, (list, tuple)) else row.requested_at
        decided_at = row[1] if isinstance(row, (list, tuple)) else row.decided_at
        if not requested_at or not decided_at:
            continue
        delta = decided_at - requested_at
        total_minutes += max(delta.total_seconds(), 0) / 60.0
        decided_count += 1
    avg_minutes = int(round(total_minutes / decided_count)) if decided_count else 0

    return DashboardSectionResponse(
        section="department_hitl",
        kpis=[
            DashboardKpi(
                id="hitl_invocation_rate",
                label="HITL Invocation Rate",
                value=invocation_rate,
                unit="%",
            ),
            DashboardKpi(
                id="avg_hitl_response_time",
                label="Avg HITL Response Time",
                value=avg_minutes,
                unit="min",
            ),
        ],
    )


@router.get("/sections/department-hitl/invocation-series", response_model=HitlSeriesResponse, status_code=200)
async def get_department_hitl_invocation_series(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    range_key: str = Query(default="7d", alias="range"),
    tz_offset_minutes: int | None = Query(default=None),
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dept_ids = await _department_admin_dept_ids(session, current_user)
    days = _range_to_days(range_key)
    tz_minutes = _coerce_tz_offset_minutes(tz_offset_minutes)
    start_day, start_dt, end_dt = _local_range_window(days, tz_minutes)

    if not dept_ids:
        series = [
            TimeseriesPoint(date=(start_day + timedelta(days=i)).isoformat(), value=0)
            for i in range(days)
        ]
        return HitlSeriesResponse(range=range_key, series=series)

    total_agents = (
        await session.exec(
            select(func.count(func.distinct(Agent.id))).where(
                Agent.dept_id.in_(list(dept_ids)),
                Agent.deleted_at.is_(None),
            )
        )
    ).one()
    total_agents_count = int(total_agents or 0)

    rows = (
        await session.exec(
            select(HITLRequest.requested_at)
            .where(
                HITLRequest.dept_id.in_(list(dept_ids)),
                HITLRequest.requested_at >= start_dt,
                HITLRequest.requested_at < end_dt,
            )
        )
    ).all()
    counts_by_day: dict[date, int] = {}
    for row in rows:
        value = row[0] if isinstance(row, (list, tuple)) else row
        day = _normalize_day(value, tz_minutes)
        counts_by_day[day] = counts_by_day.get(day, 0) + 1

    series: list[TimeseriesPoint] = []
    for i in range(days):
        day = start_day + timedelta(days=i)
        count = counts_by_day.get(day, 0)
        rate = int(round((count / total_agents_count) * 100)) if total_agents_count else 0
        series.append(TimeseriesPoint(date=day.isoformat(), value=rate))

    return HitlSeriesResponse(range=range_key, series=series)


@router.get("/sections/department-hitl/response-time-series", response_model=HitlSeriesResponse, status_code=200)
async def get_department_hitl_response_time_series(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    range_key: str = Query(default="7d", alias="range"),
    tz_offset_minutes: int | None = Query(default=None),
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "department_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dept_ids = await _department_admin_dept_ids(session, current_user)
    days = _range_to_days(range_key)
    tz_minutes = _coerce_tz_offset_minutes(tz_offset_minutes)
    start_day, start_dt, end_dt = _local_range_window(days, tz_minutes)

    if not dept_ids:
        series = [
            TimeseriesPoint(date=(start_day + timedelta(days=i)).isoformat(), value=0)
            for i in range(days)
        ]
        return HitlSeriesResponse(range=range_key, series=series)

    rows = (
        await session.exec(
            select(HITLRequest.requested_at, HITLRequest.decided_at)
            .where(
                HITLRequest.dept_id.in_(list(dept_ids)),
                HITLRequest.decided_at.is_not(None),
                HITLRequest.requested_at >= start_dt,
                HITLRequest.requested_at < end_dt,
            )
        )
    ).all()

    totals: dict[date, float] = {}
    counts: dict[date, int] = {}
    for row in rows:
        requested_at = row[0] if isinstance(row, (list, tuple)) else row.requested_at
        decided_at = row[1] if isinstance(row, (list, tuple)) else row.decided_at
        if not requested_at or not decided_at:
            continue
        day = _normalize_day(requested_at, tz_minutes)
        delta = decided_at - requested_at
        minutes = max(delta.total_seconds(), 0) / 60.0
        totals[day] = totals.get(day, 0.0) + minutes
        counts[day] = counts.get(day, 0) + 1

    series: list[TimeseriesPoint] = []
    for i in range(days):
        day = start_day + timedelta(days=i)
        if counts.get(day, 0) == 0:
            series.append(TimeseriesPoint(date=day.isoformat(), value=0))
        else:
            avg = totals[day] / counts[day]
            series.append(TimeseriesPoint(date=day.isoformat(), value=int(round(avg))))

    return HitlSeriesResponse(range=range_key, series=series)


@router.get("/sections/developer-code", response_model=DashboardSectionResponse, status_code=200)
async def get_developer_code_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "developer":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    rows = (
        await session.exec(
            select(Agent.id, func.count(func.distinct(AgentDeploymentUAT.version_number)))
            .select_from(Agent)
            .join(AgentDeploymentUAT, AgentDeploymentUAT.agent_id == Agent.id, isouter=True)
            .where(
                Agent.user_id == current_user.id,
                Agent.deleted_at.is_(None),
            )
            .group_by(Agent.id)
        )
    ).all()
    if not rows:
        avg_versions = 0
    else:
        counts = [int(row[1] or 0) if isinstance(row, (list, tuple)) else int(row[1]) for row in rows]
        avg_versions = int(round(sum(counts) / len(counts))) if counts else 0

    return DashboardSectionResponse(
        section="developer_code",
        kpis=[
            DashboardKpi(
                id="version_count_per_agent",
                label="Avg. Version Count of Agents",
                value=avg_versions,
            ),
        ],
    )


@router.get("/sections/business-maturity", response_model=DashboardSectionResponse, status_code=200)
async def get_business_maturity_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "business_user":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    total_agents = (
        await session.exec(
            select(func.count(func.distinct(Agent.id))).where(
                Agent.user_id == current_user.id,
                Agent.deleted_at.is_(None),
            )
        )
    ).one()
    total_agents_count = int(total_agents or 0)

    guardrail_agents = (
        await session.exec(
            select(func.count(func.distinct(AgentBundle.agent_id)))
            .select_from(AgentBundle)
            .join(Agent, Agent.id == AgentBundle.agent_id, isouter=True)
            .where(
                Agent.user_id == current_user.id,
                AgentBundle.bundle_type == BundleTypeEnum.GUARDRAIL,
            )
        )
    ).one()
    guardrail_count = int(guardrail_agents or 0)
    guardrail_pct = int(round((guardrail_count / total_agents_count) * 100)) if total_agents_count else 0

    rag_agents = (
        await session.exec(
            select(func.count(func.distinct(AgentBundle.agent_id)))
            .select_from(AgentBundle)
            .join(Agent, Agent.id == AgentBundle.agent_id, isouter=True)
            .where(
                Agent.user_id == current_user.id,
                AgentBundle.bundle_type.in_([BundleTypeEnum.VECTOR_DB, BundleTypeEnum.KNOWLEDGE_BASE]),
            )
        )
    ).one()
    rag_count = int(rag_agents or 0)
    rag_pct = int(round((rag_count / total_agents_count) * 100)) if total_agents_count else 0

    hitl_agents = (
        await session.exec(
            select(func.count(func.distinct(HITLRequest.agent_id)))
            .where(HITLRequest.user_id == current_user.id)
        )
    ).one()
    hitl_count = int(hitl_agents or 0)
    hitl_pct = int(round((hitl_count / total_agents_count) * 100)) if total_agents_count else 0

    return DashboardSectionResponse(
        section="business_maturity",
        kpis=[
            DashboardKpi(id="agents_with_guardrails_pct", label="% Agents with Guardrails", value=guardrail_pct, unit="%"),
            DashboardKpi(id="agents_with_rag_pct", label="% Agents with RAG", value=rag_pct, unit="%"),
            DashboardKpi(id="agents_with_hitl_pct", label="% Agents with HITL", value=hitl_pct, unit="%"),
        ],
    )


@router.get("/sections/business-experience", response_model=DashboardSectionResponse, status_code=200)
async def get_business_experience_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "business_user":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    total_sessions = (
        await session.exec(
            select(func.count(func.distinct(OrchConversationTable.session_id))).where(
                OrchConversationTable.user_id == current_user.id,
            )
        )
    ).one()
    total_sessions_count = int(total_sessions or 0)

    hitl_sessions = (
        await session.exec(
            select(func.count(func.distinct(HITLRequest.session_id))).where(
                HITLRequest.user_id == current_user.id,
                HITLRequest.session_id.is_not(None),
            )
        )
    ).one()
    hitl_sessions_count = int(hitl_sessions or 0)
    escalation_pct = round((hitl_sessions_count / total_sessions_count) * 100, 2) if total_sessions_count else 0

    avg_rating = (
        await session.exec(
            select(func.avg(AgentRegistryRating.score))
        )
    ).one()
    avg_rating_value = round(float(avg_rating), 2) if avg_rating is not None else 0

    return DashboardSectionResponse(
        section="business_experience",
        kpis=[
            DashboardKpi(
                id="escalation_to_human",
                label="Escalation to Human",
                value=escalation_pct,
                unit="%",
            ),
            DashboardKpi(
                id="user_satisfaction_score",
                label="User Satisfaction Score",
                value=avg_rating_value,
                unit="/5",
            ),
        ],
    )


@router.get("/sections/root-maturity", response_model=DashboardSectionResponse, status_code=200)
async def get_root_maturity_kpis(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    role = str(getattr(current_user, "role", "")).lower()
    if role != "root":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    total_agents = (
        await session.exec(
            select(func.count(func.distinct(Agent.id))).where(
                Agent.deleted_at.is_(None),
            )
        )
    ).one()
    total_agents_count = int(total_agents or 0)

    guardrail_agents = (
        await session.exec(
            select(func.count(func.distinct(AgentBundle.agent_id)))
            .select_from(AgentBundle)
            .where(
                AgentBundle.bundle_type == BundleTypeEnum.GUARDRAIL,
            )
        )
    ).one()
    guardrail_count = int(guardrail_agents or 0)
    guardrail_pct = int(round((guardrail_count / total_agents_count) * 100)) if total_agents_count else 0

    rag_agents = (
        await session.exec(
            select(func.count(func.distinct(AgentBundle.agent_id)))
            .select_from(AgentBundle)
            .where(
                AgentBundle.bundle_type.in_([BundleTypeEnum.VECTOR_DB, BundleTypeEnum.KNOWLEDGE_BASE]),
            )
        )
    ).one()
    rag_count = int(rag_agents or 0)
    rag_pct = int(round((rag_count / total_agents_count) * 100)) if total_agents_count else 0

    hitl_agents = (
        await session.exec(
            select(func.count(func.distinct(HITLRequest.agent_id)))
        )
    ).one()
    hitl_count = int(hitl_agents or 0)
    hitl_pct = int(round((hitl_count / total_agents_count) * 100)) if total_agents_count else 0

    return DashboardSectionResponse(
        section="root_maturity",
        kpis=[
            DashboardKpi(id="agents_with_guardrails_pct", label="% Agents with Guardrails", value=guardrail_pct, unit="%"),
            DashboardKpi(id="agents_with_rag_pct", label="% Agents with RAG", value=rag_pct, unit="%"),
            DashboardKpi(id="agents_with_hitl_pct", label="% Agents with HITL", value=hitl_pct, unit="%"),
        ],
    )
