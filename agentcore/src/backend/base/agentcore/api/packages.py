"""Dependency governance API – read-only view of managed and transitive packages.

Data is synced from pyproject.toml + uv.lock into the database at application startup.
These endpoints simply read from the ``package`` table.

Endpoints:
    GET /packages/managed    – declared deps with resolved version
    GET /packages/transitive – transitive (indirect) deps with "required by" info
"""

from __future__ import annotations

from collections import deque
from typing import Any

from datetime import date

from fastapi import APIRouter, Query
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.package.model import Package

router = APIRouter(prefix="/packages", tags=["Packages"])
ACTIVE_END_DATE = date(9999, 12, 31)


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(".", "-")


def _compute_managed_reachable_transitives(
    managed_names: set[str],
    transitive_rows: list[Package],
) -> set[str]:
    """Return transitive package names reachable from managed packages."""
    children_by_parent: dict[str, set[str]] = {}
    for row in transitive_rows:
        child = _normalize(row.name)
        parent_names: set[str] = set()
        for detail in row.required_by_details or []:
            parent = detail.get("name")
            if parent:
                parent_names.add(_normalize(parent))
        for parent in row.required_by or []:
            parent_names.add(_normalize(parent))
        for parent in parent_names:
            children_by_parent.setdefault(parent, set()).add(child)

    reachable: set[str] = set()
    queue = deque(managed_names)
    seen: set[str] = set(managed_names)
    while queue:
        parent = queue.popleft()
        for child in children_by_parent.get(parent, set()):
            if child in reachable:
                continue
            reachable.add(child)
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return reachable


def _build_parent_map(transitive_rows: list[Package]) -> dict[str, set[str]]:
    """Build child->parents map from transitive rows."""
    parents_by_child: dict[str, set[str]] = {}
    for row in transitive_rows:
        child = _normalize(row.name)
        parent_names: set[str] = set()
        for detail in row.required_by_details or []:
            parent = detail.get("name")
            if parent:
                parent_names.add(_normalize(parent))
        for parent in row.required_by or []:
            parent_names.add(_normalize(parent))
        if parent_names:
            parents_by_child.setdefault(child, set()).update(parent_names)
    return parents_by_child


def _compute_managed_root_data(
    transitive_name: str,
    parents_by_child: dict[str, set[str]],
    managed_names: set[str],
    display_names: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Return managed roots and human-readable dependency paths for one transitive package."""
    child = _normalize(transitive_name)
    roots: set[str] = set()
    paths: list[str] = []

    stack: list[tuple[str, list[str]]] = [(child, [child])]
    seen_states: set[tuple[str, tuple[str, ...]]] = set()
    max_paths = 25

    while stack and len(paths) < max_paths:
        node, upward_path = stack.pop()
        state = (node, tuple(upward_path))
        if state in seen_states:
            continue
        seen_states.add(state)

        for parent in parents_by_child.get(node, set()):
            if parent in upward_path:
                continue
            next_path = upward_path + [parent]
            if parent in managed_names:
                roots.add(parent)
                root_to_child = list(reversed(next_path))
                formatted = " -> ".join(display_names.get(name, name) for name in root_to_child)
                paths.append(formatted)
                continue
            stack.append((parent, next_path))

    root_list = sorted(display_names.get(name, name) for name in roots)
    unique_paths = list(dict.fromkeys(paths))
    return root_list, unique_paths


@router.get("/managed")
async def get_managed_packages(
    current_user: CurrentActiveUser,
    session: DbSession,
    include_history: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Return declared dependencies with their resolved version."""
    conditions = [Package.package_type == "managed"]
    if not include_history:
        conditions.append(Package.end_date == ACTIVE_END_DATE)

    rows = (
        await session.exec(
            select(Package)
            .where(*conditions)
            .order_by(Package.name.asc(), Package.start_date.desc(), Package.synced_at.desc())
        )
    ).all()

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "version_spec": row.version_spec or "",
            "resolved_version": row.version,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(),
            "is_current": row.end_date == ACTIVE_END_DATE,
            "source": row.source or {},
        }
        for row in rows
    ]


@router.get("/transitive")
async def get_transitive_packages(
    current_user: CurrentActiveUser,
    session: DbSession,
    include_history: bool = Query(default=False),
    include_full_graph: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Return transitive deps with strict managed-closure scope by default."""
    conditions = [Package.package_type == "transitive"]
    if not include_history:
        conditions.append(Package.end_date == ACTIVE_END_DATE)

    rows = (
        await session.exec(
            select(Package)
            .where(*conditions)
            .order_by(Package.name.asc(), Package.start_date.desc(), Package.synced_at.desc())
        )
    ).all()

    current_managed_rows = (
        await session.exec(
            select(Package).where(
                Package.package_type == "managed",
                Package.end_date == ACTIVE_END_DATE,
            )
        )
    ).all()
    managed_names = {_normalize(row.name) for row in current_managed_rows}

    current_transitive_rows = (
        await session.exec(
            select(Package).where(
                Package.package_type == "transitive",
                Package.end_date == ACTIVE_END_DATE,
            )
        )
    ).all()
    reachable_transitives = _compute_managed_reachable_transitives(
        managed_names=managed_names,
        transitive_rows=current_transitive_rows,
    )
    parents_by_child = _build_parent_map(current_transitive_rows)
    display_names: dict[str, str] = {}
    for row in current_managed_rows:
        display_names[_normalize(row.name)] = row.name
    for row in current_transitive_rows:
        display_names[_normalize(row.name)] = row.name
    managed_by_norm = {_normalize(pkg.name): pkg for pkg in current_managed_rows}

    response_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized_name = _normalize(row.name)
        if not include_full_graph and normalized_name not in reachable_transitives:
            continue

        managed_root_names, dependency_paths = _compute_managed_root_data(
            transitive_name=row.name,
            parents_by_child=parents_by_child,
            managed_names=managed_names,
            display_names=display_names,
        )
        root_order = {root: idx for idx, root in enumerate(managed_root_names)}
        dependency_paths = sorted(
            dependency_paths,
            key=lambda path: (
                root_order.get(path.split(" -> ", 1)[0], 10_000),
                path,
            ),
        )
        managed_root_details = []
        for root_name in managed_root_names:
            root_norm = _normalize(root_name)
            managed_pkg = managed_by_norm.get(root_norm)
            if managed_pkg is None:
                continue
            managed_root_details.append(
                {"name": managed_pkg.name, "version": managed_pkg.version}
            )

        response_rows.append(
            {
                "id": str(row.id),
                "name": row.name,
                "resolved_version": row.version,
                # Backward-compatible fields (legacy UI support)
                "required_by": row.required_by or [],
                "required_by_details": row.required_by_details or [],
                # Strict governance fields
                "required_by_chain": managed_root_names,
                "required_by_chain_details": managed_root_details,
                "managed_roots": managed_root_names,
                "managed_root_details": managed_root_details,
                "dependency_paths": dependency_paths,
                "start_date": row.start_date.isoformat(),
                "end_date": row.end_date.isoformat(),
                "is_current": row.end_date == ACTIVE_END_DATE,
                "scope": "full_graph" if include_full_graph else "managed_closure",
                "source": row.source or {},
            }
        )

    return response_rows
