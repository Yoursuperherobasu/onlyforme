"""Human-in-the-Loop (HITL) API endpoints.

These endpoints allow the frontend (or any client) to:
  - List paused graph runs awaiting human input
  - Inspect the interrupt context for a paused run
  - Resume a paused run with a human decision
  - Cancel a paused run

A run is paused when a HumanApproval node (or RequestHumanReview tool) calls
LangGraph's interrupt().  The graph state is frozen in the MemorySaver
checkpointer, identified by thread_id (== session_id used in arun()).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from langgraph.types import Command
from loguru import logger
from sqlmodel import col, select

from agentcore.api.utils import CurrentActiveUser, DbSession, build_graph_from_db_no_cache
from agentcore.graph_langgraph.checkpointer import get_checkpointer
from agentcore.services.database.models.agent.model import Agent
from agentcore.services.database.models.hitl_request.model import (
    HITLRequest,
    HITLRequestRead,
    HITLResumeRequest,
    HITLStatus,
)

router = APIRouter(prefix="/v1/hitl", tags=["Human-in-the-Loop"])


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _restore_checkpoint_to_memory(thread_id: str, checkpoint_data: str | None) -> None:
    """Restore a serialized checkpoint from the DB back into the MemorySaver.

    If ``checkpoint_data`` is None the function is a no-op; the MemorySaver may
    still have the checkpoint from the current process run (no restart since the
    original run).  If it is set, we deserialize and inject the entries so the
    compiled graph can find the checkpoint even after a server restart.
    """
    if not checkpoint_data:
        logger.debug(
            f"[HITL] No checkpoint_data stored for thread_id={thread_id!r} "
            "— relying on in-process MemorySaver"
        )
        return

    try:
        import base64
        import pickle

        payload = pickle.loads(base64.b64decode(checkpoint_data))
        storage_data: dict = payload.get("storage", {})
        blobs_data: dict = payload.get("blobs", {})

        checkpointer = get_checkpointer()

        # Restore storage entries for this thread
        for checkpoint_ns, entries in storage_data.items():
            checkpointer.storage[thread_id][checkpoint_ns].update(entries)

        # Restore blob entries for this thread
        for key, value in blobs_data.items():
            checkpointer.blobs[key] = value

        logger.info(
            f"[HITL] Restored checkpoint for thread_id={thread_id!r} from DB "
            f"({len(checkpoint_data)} chars)"
        )
    except Exception as _err:
        logger.warning(f"[HITL] Could not restore checkpoint: {_err}")


async def _get_pending_request(thread_id: str, session) -> HITLRequest:
    """Fetch the most-recent PENDING HITLRequest or raise 404.

    Filters to PENDING status so that historical resolved rows for the same
    thread_id (e.g. from previous test runs) are never returned by mistake.
    """
    stmt = (
        select(HITLRequest)
        .where(HITLRequest.thread_id == thread_id)
        .where(HITLRequest.status == HITLStatus.PENDING)
        .order_by(col(HITLRequest.requested_at).desc())
        .limit(1)
    )
    result = await session.exec(stmt)
    req = result.first()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending HITL request found for thread_id={thread_id!r}",
        )
    return req


async def _enrich_with_agent_names(rows: list[HITLRequest], session) -> list[dict]:
    """Batch-load agent names and merge into HITLRequestRead dicts."""
    agent_ids = {r.agent_id for r in rows}
    agent_map: dict[UUID, str] = {}
    if agent_ids:
        agent_rows = (
            await session.exec(select(Agent).where(Agent.id.in_(agent_ids)))
        ).all()
        agent_map = {a.id: a.name for a in agent_rows}

    return [
        {
            **HITLRequestRead.model_validate(r, from_attributes=True).model_dump(),
            "agent_name": agent_map.get(r.agent_id),
        }
        for r in rows
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=list[HITLRequestRead])
async def list_pending_hitl(
    current_user: CurrentActiveUser,
    session: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[dict]:
    """Return HITL requests, optionally filtered by status.

    Query params:
        status: "pending" (default) — only PENDING requests
                "all"              — all requests regardless of status

    Only returns requests whose agent was created by the current user.
    Admin/superuser see all requests.
    """
    stmt = select(HITLRequest).order_by(col(HITLRequest.requested_at).desc())

    if status_filter != "all":
        stmt = stmt.where(HITLRequest.status == HITLStatus.PENDING)

    if not getattr(current_user, "is_superuser", False):
        # Include records where user_id matches OR user_id is NULL
        # (NULL can happen if the persistence path didn't have user context)
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                HITLRequest.user_id == current_user.id,
                HITLRequest.user_id.is_(None),
            )
        )

    result = await session.exec(stmt)
    rows = result.all()
    return await _enrich_with_agent_names(rows, session)


@router.get("/{thread_id}/state", response_model=HITLRequestRead)
async def get_hitl_state(
    thread_id: str,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Return the interrupt context for a paused run.

    The ``interrupt_data`` field contains the question, context, and available
    actions that should be shown to the human reviewer.
    """
    req = await _get_pending_request(thread_id, session)
    enriched = await _enrich_with_agent_names([req], session)
    return enriched[0]


@router.post("/{thread_id}/resume")
async def resume_hitl(
    thread_id: str,
    body: HITLResumeRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    """Resume a paused graph run with the human's decision.

    The graph is resumed by calling ``compiled_app.ainvoke(Command(resume=...))``.
    If another HITL node is encountered downstream, the response will contain
    ``"status": "interrupted"`` with the new ``interrupt_data``.

    Body:
        action: The action the human chose (must match one of the actions in interrupt_data)
        feedback: Optional free-text feedback from the reviewer
        edited_value: Optional edited value (for "Edit" action paths)
    """
    hitl_req = await _get_pending_request(thread_id, session)

    if hitl_req.status != HITLStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is not pending — current status: {hitl_req.status.value}",
        )

    decision = {
        "action": body.action,
        "feedback": body.feedback or "",
        "edited_value": body.edited_value or "",
    }

    try:
        # Rebuild the LangGraph compiled app for this agent.
        graph = await build_graph_from_db_no_cache(
            agent_id=hitl_req.agent_id,
            session=session,
            user_id=str(current_user.id),
            session_id=hitl_req.session_id or thread_id,
        )

        lg_config = {"configurable": {"thread_id": thread_id}}

        # Restore checkpoint from DB into MemorySaver so that the compiled graph
        # can find it even after a server restart (MemorySaver is in-process only).
        await _restore_checkpoint_to_memory(thread_id, hitl_req.checkpoint_data)

        # Verify the checkpoint is present before attempting resume.
        _pre_state = await graph.compiled_app.aget_state(lg_config)
        if not _pre_state.next:
            logger.warning(
                f"[HITL] No interrupted checkpoint found for thread_id={thread_id!r} "
                "after restore attempt — resume may run from scratch"
            )
        else:
            logger.info(
                f"[HITL] Checkpoint verified for thread_id={thread_id!r}: "
                f"next={_pre_state.next}"
            )

        # Hydrate upstream vertex objects from checkpoint state so that
        # _resolve_params() in vertex_wrapper.py can resolve edge-connected
        # inputs.  On resume, the graph is rebuilt from scratch (new vertex
        # objects with built=False), but LangGraph only re-executes from the
        # interrupted node onward — upstream vertices never run.  Without
        # hydration, _resolve_params() skips them (built=False) and downstream
        # components receive None for their inputs.
        #
        # IMPORTANT: Only hydrate vertices that are UPSTREAM (predecessors) of
        # the interrupted node.  The interrupted node itself and all downstream
        # nodes must NOT be hydrated — they need to re-execute fresh.
        # We use the predecessor_map to compute the full set of transitive
        # predecessors via BFS.
        try:
            checkpoint_values = _pre_state.values or {}
            vertices_results = checkpoint_values.get("vertices_results", {})
            predecessor_map = checkpoint_values.get("predecessor_map", {})
            next_nodes = set(_pre_state.next or ())

            # BFS: collect all transitive predecessors of the interrupted node(s)
            upstream: set[str] = set()
            queue = list(next_nodes)
            while queue:
                nid = queue.pop(0)
                for pred in predecessor_map.get(nid, []):
                    if pred not in upstream and pred not in next_nodes:
                        upstream.add(pred)
                        queue.append(pred)

            if vertices_results and upstream:
                hydrated = []
                for vid in upstream:
                    result = vertices_results.get(vid)
                    v = graph.get_vertex(vid)
                    if v and not v.built and result is not None:
                        v.built = True
                        v.built_result = result
                        v.built_object = result
                        hydrated.append(vid)
                        # Debug: log the type and structure of the hydrated result
                        if isinstance(result, dict):
                            detail = {k: type(val).__name__ for k, val in result.items()}
                        else:
                            detail = type(result).__name__
                        logger.info(
                            f"[HITL] Hydrated vertex {vid}: result_structure={detail}"
                        )
                if hydrated:
                    logger.info(
                        f"[HITL] Hydrated {len(hydrated)} upstream vertices "
                        f"from checkpoint: {hydrated}"
                    )
                else:
                    logger.debug(
                        f"[HITL] No upstream vertices to hydrate "
                        f"(next={next_nodes}, upstream={upstream})"
                    )
        except Exception as _hydrate_err:
            logger.warning(f"[HITL] Could not hydrate vertices from checkpoint: {_hydrate_err}")

        # Recover the original input content from the stored interrupt data
        # as a fallback — in case hydration didn't cover the input.
        try:
            if _pre_state.tasks and _pre_state.tasks[0].interrupts:
                interrupt_data = _pre_state.tasks[0].interrupts[0].value or {}
                decision["original_content"] = interrupt_data.get("context", "")
        except (IndexError, AttributeError):
            pass

        # Resume: pass Command(resume=decision) instead of initial_state.
        final_state = await graph.compiled_app.ainvoke(
            Command(resume=decision),
            config=lg_config,
        )

        # Check if the graph hit another interrupt() downstream.
        graph_state = await graph.compiled_app.aget_state(lg_config)
        if graph_state.next:
            next_interrupt_data: dict = {}
            if graph_state.tasks and graph_state.tasks[0].interrupts:
                next_interrupt_data = graph_state.tasks[0].interrupts[0].value or {}

            # Serialize the new checkpoint for the second interrupt so it too
            # can be restored after a server restart.
            from agentcore.graph_langgraph.nodes import save_hitl_checkpoint_after_interrupt
            await save_hitl_checkpoint_after_interrupt(thread_id)

            # Update this record as resolved, create a new pending record.
            _resolve_request(hitl_req, decision, body.action, current_user.id)
            session.add(hitl_req)

            new_req = HITLRequest(
                thread_id=thread_id,
                agent_id=hitl_req.agent_id,
                session_id=hitl_req.session_id,
                user_id=hitl_req.user_id,
                interrupt_data=next_interrupt_data,
                status=HITLStatus.PENDING,
            )
            session.add(new_req)
            await session.commit()

            logger.info(f"[HITL] Graph interrupted again at: {graph_state.next}")
            return {
                "status": "interrupted",
                "thread_id": thread_id,
                "interrupt_data": next_interrupt_data,
                "hitl_request_id": str(new_req.id),
            }

        # Run completed normally.
        _resolve_request(hitl_req, decision, body.action, current_user.id)
        session.add(hitl_req)
        await session.commit()

        # Extract the output text from the output vertex and check if
        # ChatOutput already stored its message to the conversation table.
        output_stored_by_component = False
        output_text: str | None = None
        for oid in getattr(graph, "_is_output_vertices", []):
            vertex = graph.get_vertex(oid)
            if not vertex or not vertex.built:
                continue
            comp = getattr(vertex, "custom_component", None)
            if comp and getattr(comp, "_stored_message_id", None):
                output_stored_by_component = True
            # Always extract the text — we need it for orch_conversation
            # even when ChatOutput already stored to the conversation table.
            if vertex.built_result is not None:
                result = vertex.built_result
                if isinstance(result, dict):
                    for v in result.values():
                        if v is not None and hasattr(v, "text"):
                            output_text = v.text
                            break
                elif hasattr(result, "text"):
                    output_text = result.text
            break  # Only check the first output vertex

        # Determine if this was an orchestrator run (orch metadata attached by nodes.py)
        orch_meta = (hitl_req.interrupt_data or {}).get("_orch_meta")

        # For orchestrator runs, store the LLM response as a separate
        # orch_conversation message.  ChatOutput stores to the conversation
        # table (Playground), but the Orch page reads from orch_conversation.
        if orch_meta and output_text:
            await _store_orch_agent_response(
                agent_id=str(hitl_req.agent_id),
                output_text=output_text,
                orch_meta=orch_meta,
            )

        await _store_hitl_confirmation(
            thread_id=thread_id,
            agent_id=str(hitl_req.agent_id),
            action=body.action,
            output_text=output_text if not output_stored_by_component and not orch_meta else None,
            orch_meta=orch_meta,
        )

        logger.info(f"[HITL] Run {thread_id!r} resumed and completed successfully.")
        return {
            "status": "completed",
            "thread_id": thread_id,
            "action": body.action,
            "output_text": output_text,
        }

    except Exception as exc:
        logger.exception(f"[HITL] Error resuming thread {thread_id!r}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume run: {exc}",
        ) from exc


@router.post("/{thread_id}/cancel")
async def cancel_hitl(
    thread_id: str,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict[str, str]:
    """Cancel a pending HITL request without resuming the graph.

    The frozen graph state remains in the checkpointer but the DB record is
    marked as cancelled.  The run cannot be resumed after cancellation.
    """
    hitl_req = await _get_pending_request(thread_id, session)

    if hitl_req.status != HITLStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is not pending — current status: {hitl_req.status.value}",
        )

    hitl_req.status = HITLStatus.CANCELLED
    hitl_req.decided_at = datetime.now(timezone.utc)
    hitl_req.decided_by_user_id = current_user.id
    session.add(hitl_req)
    await session.commit()

    logger.info(f"[HITL] Run {thread_id!r} cancelled by user {current_user.id}.")
    return {"status": "cancelled", "thread_id": thread_id}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _store_orch_agent_response(
    agent_id: str,
    output_text: str,
    orch_meta: dict,
) -> None:
    """Store the LLM/ChatOutput response to orch_conversation after HITL resume.

    During normal orchestrator runs, the orch endpoint extracts the response text
    and stores it to orch_conversation.  During HITL resume, ChatOutput stores to
    the conversation table (Playground) but NOT orch_conversation.  This function
    fills that gap so the Orchestration page shows the full AI response.
    """
    try:
        from uuid import UUID as _UUID
        from agentcore.services.database.models.orch_conversation.model import OrchConversationTable
        from agentcore.services.database.models.orch_conversation.crud import orch_add_message
        from agentcore.services.deps import session_scope

        async with session_scope() as db:
            orch_msg = OrchConversationTable(
                sender="agent",
                sender_name="AI",
                session_id=orch_meta.get("session_id"),
                text=output_text,
                agent_id=_UUID(agent_id) if agent_id else None,
                user_id=_UUID(orch_meta["user_id"]) if orch_meta.get("user_id") else None,
                deployment_id=_UUID(orch_meta["deployment_id"]) if orch_meta.get("deployment_id") else None,
                files=[],
                properties={},
                category="message",
                content_blocks=[],
            )
            await orch_add_message(orch_msg, db)
        logger.info(f"[HITL] Stored orch agent response ({len(output_text)} chars)")
    except Exception as _err:
        logger.warning(f"[HITL] Could not store orch agent response: {_err}")


async def _store_hitl_confirmation(
    thread_id: str,
    agent_id: str,
    action: str,
    output_text: str | None = None,
    orch_meta: dict | None = None,
) -> None:
    """Store a confirmation chat message after HITL resume.

    Writes to the correct table depending on context:
    - Playground runs  → ``conversation`` table (via ``astore_message``)
    - Orchestrator runs → ``orch_conversation`` table (via ``orch_add_message``)

    ``orch_meta`` is set by ``_persist_hitl_request`` in nodes.py when the graph
    was launched from the orchestrator.  It contains ``deployment_id``, ``user_id``,
    and ``session_id`` needed for the orch_conversation row.
    """
    try:
        is_reject = "reject" in action.lower()
        icon = "✗" if is_reject else "✓"
        text = f"{icon} **{action}** — Human review completed"
        if output_text:
            text += f"\n\n> {output_text}"

        if orch_meta:
            # Orchestrator run → write to orch_conversation
            from uuid import UUID as _UUID
            from agentcore.services.database.models.orch_conversation.model import OrchConversationTable
            from agentcore.services.database.models.orch_conversation.crud import orch_add_message
            from agentcore.services.deps import session_scope

            async with session_scope() as db:
                orch_msg = OrchConversationTable(
                    sender="agent",
                    sender_name="Agent",
                    session_id=orch_meta.get("session_id") or thread_id,
                    text=text,
                    agent_id=_UUID(agent_id) if agent_id else None,
                    user_id=_UUID(orch_meta["user_id"]) if orch_meta.get("user_id") else None,
                    deployment_id=_UUID(orch_meta["deployment_id"]) if orch_meta.get("deployment_id") else None,
                    files=[],
                    properties={},
                    category="message",
                    content_blocks=[],
                )
                await orch_add_message(orch_msg, db)
            logger.info(f"[HITL] Stored orch confirmation for thread_id={thread_id!r}, action={action!r}")
        else:
            # Playground run → write to conversation
            from agentcore.memory import astore_message
            from agentcore.schema.message import Message

            msg = Message(
                text=text,
                sender="Machine",
                sender_name="Agent",
                session_id=thread_id,
                agent_id=agent_id,
            )
            await astore_message(msg, agent_id=agent_id)
            logger.info(f"[HITL] Stored playground confirmation for thread_id={thread_id!r}, action={action!r}")
    except Exception as _err:
        logger.warning(f"[HITL] Could not store confirmation message: {_err}")




def _resolve_request(
    req: HITLRequest,
    decision: dict,
    action: str,
    decided_by: UUID,
) -> None:
    """Update a HITLRequest record with the human's decision."""
    action_lower = action.lower()
    if "reject" in action_lower:
        req.status = HITLStatus.REJECTED
    elif "edit" in action_lower:
        req.status = HITLStatus.EDITED
    else:
        req.status = HITLStatus.APPROVED

    req.decision = decision
    req.decided_by_user_id = decided_by
    req.decided_at = datetime.now(timezone.utc)
