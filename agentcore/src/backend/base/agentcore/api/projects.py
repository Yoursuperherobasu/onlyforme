import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

import orjson
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession, cascade_delete_agent, custom_params, remove_api_keys
from agentcore.api.agent import create_agent
from agentcore.api.v1_schemas import AgentListCreate
from agentcore.helpers.agent import generate_unique_agent_name
from agentcore.helpers.folders import generate_unique_folder_name
from agentcore.initial_setup.constants import STARTER_FOLDER_NAME
from agentcore.services.database.models.agent.model import Agent, AgentCreate, AgentRead
from agentcore.services.database.models.project.constants import DEFAULT_FOLDER_NAME as DEFAULT_PROJECT_NAME
from agentcore.services.database.models.project.model import (
    Project,
    ProjectCreate,
    ProjectRead,
    ProjectReadWithAgents,
    ProjectUpdate,
)
from agentcore.services.database.models.project.pagination_model import ProjectWithPaginatedAgents
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership

router = APIRouter(prefix="/projects", tags=["Projects"])


def _is_admin_role(role: str | None) -> bool:
    return role in {"super_admin", "department_admin", "root"}


async def _get_scope_memberships(session: DbSession, user_id: UUID) -> tuple[set[UUID], set[UUID]]:
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
            select(UserDepartmentMembership.department_id).where(
                UserDepartmentMembership.user_id == user_id,
                UserDepartmentMembership.status == "active",
            )
        )
    ).all()
    return set(org_rows), set(dept_rows)


async def _build_project_visibility_statement(session: DbSession, current_user: CurrentActiveUser):
    own_condition = or_(Project.user_id == current_user.id, Project.owner_user_id == current_user.id)
    role = getattr(current_user, "role", None)

    if role in {"super_admin", "root"}:
        org_ids, _ = await _get_scope_memberships(session, current_user.id)
        if org_ids:
            org_user_subquery = (
                select(UserOrganizationMembership.user_id).where(
                    UserOrganizationMembership.org_id.in_(list(org_ids)),
                    UserOrganizationMembership.status.in_(["accepted", "active"]),
                )
            )
            return select(Project).where(
                or_(
                    own_condition,
                    Project.org_id.in_(list(org_ids)),
                    Project.user_id.in_(org_user_subquery),
                    Project.owner_user_id.in_(org_user_subquery),
                )
            )
        return select(Project).where(own_condition)

    if role == "department_admin":
        _, dept_ids = await _get_scope_memberships(session, current_user.id)
        if dept_ids:
            dept_user_subquery = (
                select(UserDepartmentMembership.user_id).where(
                    UserDepartmentMembership.department_id.in_(list(dept_ids)),
                    UserDepartmentMembership.status == "active",
                )
            )
            return select(Project).where(
                or_(
                    own_condition,
                    Project.dept_id.in_(list(dept_ids)),
                    Project.user_id.in_(dept_user_subquery),
                    Project.owner_user_id.in_(dept_user_subquery),
                )
            )
        return select(Project).where(own_condition)

    return select(Project).where(own_condition)


async def _can_access_project(session: DbSession, current_user: CurrentActiveUser, project: Project) -> bool:
    role = getattr(current_user, "role", None)
    if project.user_id == current_user.id or project.owner_user_id == current_user.id:
        return True

    if role in {"super_admin", "root"}:
        org_ids, _ = await _get_scope_memberships(session, current_user.id)
        if project.org_id and project.org_id in org_ids:
            return True
        owner_id = project.owner_user_id or project.user_id
        if owner_id and org_ids:
            owner_membership = (
                await session.exec(
                    select(UserOrganizationMembership.id).where(
                        UserOrganizationMembership.user_id == owner_id,
                        UserOrganizationMembership.org_id.in_(list(org_ids)),
                        UserOrganizationMembership.status.in_(["accepted", "active"]),
                    )
                )
            ).first()
            if owner_membership:
                return True

    if role == "department_admin":
        _, dept_ids = await _get_scope_memberships(session, current_user.id)
        if project.dept_id and project.dept_id in dept_ids:
            return True
        owner_id = project.owner_user_id or project.user_id
        if owner_id and dept_ids:
            owner_membership = (
                await session.exec(
                    select(UserDepartmentMembership.id).where(
                        UserDepartmentMembership.user_id == owner_id,
                        UserDepartmentMembership.department_id.in_(list(dept_ids)),
                        UserDepartmentMembership.status == "active",
                    )
                )
            ).first()
            if owner_membership:
                return True

    return False


@router.post("/", response_model=ProjectRead, status_code=201)
async def create_project(
    *,
    session: DbSession,
    project: ProjectCreate,
    current_user: CurrentActiveUser,
):
    try:
        new_project = Project.model_validate(project, from_attributes=True)
        new_project.user_id = current_user.id
        new_project.owner_user_id = current_user.id

        # Default project tenancy scope from user's memberships.
        org_ids, dept_ids = await _get_scope_memberships(session, current_user.id)
        if new_project.org_id is None and org_ids:
            new_project.org_id = sorted(org_ids, key=str)[0]
        if new_project.dept_id is None and dept_ids:
            new_project.dept_id = sorted(dept_ids, key=str)[0]
        # First check if the project.name is unique
        # there might be agents with name like: "Myagent", "Myagent (1)", "Myagent (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a agent with the same name, we add a number to the end of the name
        # based on the highest number found
        if (
            await session.exec(
                statement=select(Project).where(Project.name == new_project.name).where(Project.user_id == current_user.id)
            )
        ).first():
            project_results = await session.exec(
                select(Project).where(
                    Project.name.like(f"{new_project.name}%"),  # type: ignore[attr-defined]
                    Project.user_id == current_user.id,
                )
            )
            if project_results:
                project_names = [project.name for project in project_results]
                project_numbers = [int(name.split("(")[-1].split(")")[0]) for name in project_names if "(" in name]
                if project_numbers:
                    new_project.name = f"{new_project.name} ({max(project_numbers) + 1})"
                else:
                    new_project.name = f"{new_project.name} (1)"

        session.add(new_project)
        await session.commit()
        await session.refresh(new_project)

        if project.components_list:
            update_statement_components = (
                update(Agent).where(Agent.id.in_(project.components_list)).values(folder_id=new_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_components)
            await session.commit()

        if project.agents_list:
            update_statement_agents = (
                update(Agent).where(Agent.id.in_(project.agents_list)).values(folder_id=new_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_agents)
            await session.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return new_project


@router.get("/", response_model=list[ProjectRead], status_code=200)
async def read_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        statement = await _build_project_visibility_statement(session, current_user)
        projects = (await session.exec(statement)).all()
        projects = [project for project in projects if project.name != STARTER_FOLDER_NAME]
        return sorted(projects, key=lambda x: x.name != DEFAULT_PROJECT_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}", response_model=ProjectWithPaginatedAgents | ProjectReadWithAgents, status_code=200)
async def read_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    params: Annotated[Params | None, Depends(custom_params)],
    search: str = ""):
    try:
        project = (
            await session.exec(
                select(Project)
                .options(selectinload(Project.agents))
                .where(Project.id == project_id)
            )
        ).first()
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not project or not await _can_access_project(session, current_user, project):
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        if params and params.page and params.size:
            stmt = select(Agent).where(Agent.folder_id == project_id)

            if Agent.updated_at is not None:
                stmt = stmt.order_by(Agent.updated_at.desc())  # type: ignore[attr-defined]
            if search:
                stmt = stmt.where(Agent.name.like(f"%{search}%"))  # type: ignore[attr-defined]
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
                )
                paginated_agents = await apaginate(session, stmt, params=params)

            return ProjectWithPaginatedAgents(project=ProjectRead.model_validate(project), agents=paginated_agents)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not _is_admin_role(getattr(current_user, "role", None)):
        agents_from_current_user_in_project = [agent for agent in project.agents if agent.user_id == current_user.id]
        project.agents = agents_from_current_user_in_project
    return project


@router.patch("/{project_id}", response_model=ProjectRead, status_code=200)
async def update_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: ProjectUpdate,  # Assuming ProjectUpdate is a Pydantic model defining updatable fields
    current_user: CurrentActiveUser,
):
    try:
        existing_project = (await session.exec(select(Project).where(Project.id == project_id))).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not existing_project or not await _can_access_project(session, current_user, existing_project):
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        if project.name and project.name != existing_project.name:
            existing_project.name = project.name
            session.add(existing_project)
            await session.commit()
            await session.refresh(existing_project)
            return existing_project

        project_data = existing_project.model_dump(exclude_unset=True)
        for key, value in project_data.items():
            if key not in {"components", "agents"}:
                setattr(existing_project, key, value)
        session.add(existing_project)
        await session.commit()
        await session.refresh(existing_project)

        concat_project_components = project.components + project.agents

        agents_ids = (await session.exec(select(Agent.id).where(Agent.folder_id == existing_project.id))).all()

        excluded_agents = list(set(agents_ids) - set(concat_project_components))

        my_collection_project = (
            await session.exec(select(Project).where(Project.name == DEFAULT_PROJECT_NAME))
        ).first()
        if my_collection_project:
            update_statement_my_collection = (
                update(Agent).where(Agent.id.in_(excluded_agents)).values(folder_id=my_collection_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_my_collection)
            await session.commit()

        if concat_project_components:
            update_statement_components = (
                update(Agent).where(Agent.id.in_(concat_project_components)).values(folder_id=existing_project.id)  # type: ignore[attr-defined]
            )
            await session.exec(update_statement_components)
            await session.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return existing_project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    try:
        project = (await session.exec(select(Project).where(Project.id == project_id))).first()
        if not project or not await _can_access_project(session, current_user, project):
            raise HTTPException(status_code=404, detail="Project not found")

        if _is_admin_role(getattr(current_user, "role", None)):
            agents = (await session.exec(select(Agent).where(Agent.folder_id == project_id))).all()
        else:
            agents = (
                await session.exec(select(Agent).where(Agent.folder_id == project_id, Agent.user_id == current_user.id))
            ).all()
        if len(agents) > 0:
            for agent in agents:
                await cascade_delete_agent(session, agent.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    try:
        await session.delete(project)
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{project_id}", status_code=200)
async def download_file(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    """Download all agents from project as a zip file."""
    try:
        query = select(Project).where(Project.id == project_id)
        result = await session.exec(query)
        project = result.first()

        if not project or not await _can_access_project(session, current_user, project):
            raise HTTPException(status_code=404, detail="Project not found")

        agents_query = select(Agent).where(Agent.folder_id == project_id)
        agents_result = await session.exec(agents_query)
        agents = [AgentRead.model_validate(agent, from_attributes=True) for agent in agents_result.all()]

        if not agents:
            raise HTTPException(status_code=404, detail="No agents found in project")

        agents_without_api_keys = [remove_api_keys(agent.model_dump()) for agent in agents]
        zip_stream = io.BytesIO()

        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            for agent in agents_without_api_keys:
                agent_json = json.dumps(jsonable_encoder(agent))
                zip_file.writestr(f"{agent['name']}.json", agent_json.encode("utf-8"))

        zip_stream.seek(0)

        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_{project.name}_agents.zip"

        # URL encode filename handle non-ASCII (ex. Cyrillic)
        encoded_filename = quote(filename)

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )

    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload/", response_model=list[AgentRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentActiveUser,
):
    """Upload agents from a file."""
    contents = await file.read()
    data = orjson.loads(contents)

    if not data:
        raise HTTPException(status_code=400, detail="No agents found in the file")

    project_name = await generate_unique_folder_name(data["folder_name"], current_user.id, session)

    data["folder_name"] = project_name

    project = ProjectCreate(name=data["folder_name"], description=data["folder_description"])

    new_project = Project.model_validate(project, from_attributes=True)
    new_project.id = None
    new_project.user_id = current_user.id
    session.add(new_project)
    await session.commit()
    await session.refresh(new_project)

    del data["folder_name"]
    del data["folder_description"]

    if "agents" in data:
        agent_list = AgentListCreate(agents=[AgentCreate(**agent) for agent in data["agents"]])
    else:
        raise HTTPException(status_code=400, detail="No agents found in the data")
    # Now we set the user_id for all agents
    for agent in agent_list.agents:
        agent_name = await generate_unique_agent_name(agent.name, current_user.id, session)
        agent.name = agent_name
        agent.user_id = current_user.id
        agent.folder_id = new_project.id

    return await create_agent(session=session, agent_list=agent_list, current_user=current_user)
