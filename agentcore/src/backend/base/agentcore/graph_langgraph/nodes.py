
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from agentcore.graph_langgraph.state import AgentCoreState

if TYPE_CHECKING:
    from agentcore.graph_langgraph.vertex_wrapper import LangGraphVertex


def create_node_function(vertex: LangGraphVertex):
    """Convert an AgentCore Vertex to a LangGraph node function.

    The returned async callable is used by ``StateGraph.add_node()`` so that
    LangGraph can execute the vertex as part of compiled graph execution
    (via ``compiled_app.ainvoke()`` / ``compiled_app.astream()``).

    The function handles the complete vertex lifecycle:
    1. Routing guard (``is_active()`` check)
    2. Frozen vertex cache restore
    3. Input parameter filtering for input vertices
    4. Dependency resolution from state
    5. Vertex build (component execution)
    6. Transaction logging to all applicable tables
    7. Frozen vertex cache save
    8. ``end_vertex`` event emission for Playground streaming
    """

    async def node_function(state: AgentCoreState) -> AgentCoreState:
        """Execute this vertex and update state."""
        graph = vertex.graph  # LangGraphAdapter instance

        # ------------------------------------------------------------------
        # 1. ROUTING GUARD — skip vertices marked INACTIVE by upstream routers.
        #    Works because LangGraph executes in topological order: routers
        #    run before their downstream vertices, so by the time we reach
        #    here the vertex state has already been set by mark_branch().
        # ------------------------------------------------------------------
        if not vertex.is_active():
            logger.debug(f"Skipping INACTIVE vertex: {vertex.id} ({vertex.display_name})")
            return state

        logger.debug(f"Executing node for vertex: {vertex.id} ({vertex.display_name})")
        start_time = time.time()

        # ------------------------------------------------------------------
        # 2. FROZEN VERTEX CACHE CHECK — restore from cache if available.
        # ------------------------------------------------------------------
        should_build = True
        if vertex.frozen:
            try:
                from agentcore.services.cache.utils import CacheMiss
                from agentcore.services.chat.service import ChatService
                from agentcore.services.deps import get_chat_service

                chat_service = get_chat_service()
                cached_result = await chat_service.get_cache(key=vertex.id)

                if not isinstance(cached_result, CacheMiss):
                    cached_vertex_dict = cached_result["result"]
                    vertex.built = cached_vertex_dict["built"]
                    vertex.artifacts = cached_vertex_dict["artifacts"]
                    vertex.built_object = cached_vertex_dict["built_object"]
                    vertex.built_result = cached_vertex_dict["built_result"]
                    vertex.results = cached_vertex_dict.get("results", {})

                    try:
                        vertex.finalize_build()
                        if vertex.result is not None:
                            vertex.result.used_frozen_result = True
                    except Exception:
                        logger.opt(exception=True).debug("Error finalizing cached build")
                        should_build = True
                    else:
                        should_build = False
            except Exception:
                logger.opt(exception=True).debug(f"Error checking frozen cache for {vertex.id}")
                should_build = True

        # ------------------------------------------------------------------
        # 3. INPUT VERTEX PARAMETER FILTERING
        # ------------------------------------------------------------------
        inputs_dict = state.get("input_data", {})
        input_vertex_ids = state.get("input_vertex_ids", [])
        if vertex.id in input_vertex_ids and inputs_dict:
            from agentcore.schema.schema import INPUT_FIELD_NAME

            input_components = inputs_dict.get("components", [])
            should_update = True
            if input_components:
                if vertex.id not in input_components and vertex.display_name not in input_components:
                    should_update = False

            if should_update and INPUT_FIELD_NAME in inputs_dict:
                vertex.update_raw_params({INPUT_FIELD_NAME: inputs_dict[INPUT_FIELD_NAME]}, overwrite=True)

        try:
            if should_build:
                # ----------------------------------------------------------
                # 4. DEPENDENCY RESOLUTION from state
                # ----------------------------------------------------------
                resolved_params = _resolve_vertex_dependencies(vertex, state)
                if resolved_params:
                    vertex.update_raw_params(resolved_params, overwrite=True)

                # ----------------------------------------------------------
                # 5. BUILD THE VERTEX (execute the component)
                # ----------------------------------------------------------
                await vertex.build(
                    user_id=state.get("user_id"),
                    inputs=inputs_dict,
                    files=state.get("files"),
                    event_manager=state.get("event_manager"),
                    fallback_to_env_vars=state.get("fallback_to_env_vars", False),
                )

            # Store results in state
            state["vertices_results"][vertex.id] = vertex.built_result
            state["artifacts"][vertex.id] = vertex.artifacts
            if vertex.outputs_logs:
                state["outputs_logs"][vertex.id] = vertex.outputs_logs

            # Track completion
            state["current_vertex"] = vertex.id
            state["completed_vertices"].append(vertex.id)

            elapsed_time = time.time() - start_time

            # Add event for streaming
            vertex_event = {
                "vertex_id": vertex.id,
                "display_name": vertex.display_name,
                "result": vertex.result,
                "timestamp": time.time(),
                "elapsed_time": elapsed_time,
                "status": "success",
            }
            state["events"].append(vertex_event)

            logger.debug(f"Vertex {vertex.id} completed in {elapsed_time:.2f}s")

            # ----------------------------------------------------------
            # 6. TRANSACTION LOGGING — all 4 tables + vertex build record
            # ----------------------------------------------------------
            from agentcore.graph_langgraph.transaction_logging import (
                log_all_transactions,
                log_vertex_build_record,
            )

            await log_all_transactions(vertex=vertex, graph=graph, status="success")

            data_dict = {}
            if vertex.built_result is not None:
                data_dict = {"result": str(vertex.built_result)}
            await log_vertex_build_record(vertex=vertex, graph=graph, valid=True, data_dict=data_dict)

            # ----------------------------------------------------------
            # 7. FROZEN VERTEX CACHE SAVE
            # ----------------------------------------------------------
            if vertex.frozen and should_build:
                try:
                    from agentcore.services.deps import get_chat_service

                    chat_service = get_chat_service()
                    vertex_dict = {
                        "built": vertex.built,
                        "results": vertex.results,
                        "artifacts": vertex.artifacts,
                        "built_object": vertex.built_object,
                        "built_result": vertex.built_result,
                    }
                    await chat_service.set_cache(key=vertex.id, value={"result": vertex_dict})
                except Exception:
                    logger.opt(exception=True).debug(f"Error saving frozen cache for {vertex.id}")

            # ----------------------------------------------------------
            # 8. EMIT end_vertex EVENT for Playground streaming
            # ----------------------------------------------------------
            event_manager = state.get("event_manager")
            if event_manager is not None:
                _emit_end_vertex_event(
                    vertex=vertex,
                    graph=graph,
                    event_manager=event_manager,
                    elapsed_time=elapsed_time,
                )

        except Exception as e:
            logger.exception(f"Error building vertex {vertex.id}: {e}")

            elapsed_time = time.time() - start_time
            error_event = {
                "vertex_id": vertex.id,
                "display_name": vertex.display_name,
                "timestamp": time.time(),
                "elapsed_time": elapsed_time,
                "status": "error",
                "error": str(e),
            }
            state["events"].append(error_event)

            # Error transaction logging
            from agentcore.graph_langgraph.transaction_logging import (
                log_all_transactions,
                log_vertex_build_record,
            )

            await log_all_transactions(vertex=vertex, graph=graph, status="error", error=str(e))
            await log_vertex_build_record(
                vertex=vertex, graph=graph, valid=False, data_dict={"error": str(e)}
            )

            raise

        return state

    # Set function name for debugging
    node_function.__name__ = f"node_{vertex.id}"
    return node_function


def _emit_end_vertex_event(
    *,
    vertex: LangGraphVertex,
    graph: Any,
    event_manager: Any,
    elapsed_time: float,
) -> None:
    """Emit an ``end_vertex`` event in the exact format the Playground frontend expects.

    This mirrors the event emission in ``build.py:_build_vertex`` so that the
    frontend receives identical NDJSON events whether execution goes through the
    custom path or the LangGraph compiled path.
    """
    import json

    from agentcore.api.schemas import ResultDataResponse, VertexBuildResponse
    from agentcore.api.utils import format_elapsed_time

    try:
        # Build ResultDataResponse from vertex result
        if vertex.result is not None:
            result_data_response = ResultDataResponse.model_validate(vertex.result, from_attributes=True)
        else:
            result_data_response = ResultDataResponse()

        result_data_response.message = vertex.artifacts
        result_data_response.duration = format_elapsed_time(elapsed_time)
        result_data_response.timedelta = elapsed_time

        # Compute next_vertices_ids — informational for frontend UI animations.
        # LangGraph controls actual execution order.
        next_vertices_ids = [
            sid
            for sid in graph.successor_map.get(vertex.id, [])
            if graph.get_vertex(sid) and graph.get_vertex(sid).is_active()
        ]
        inactivated_vertices = list(graph.inactivated_vertices)
        top_level_vertices = graph.get_top_level_vertices(next_vertices_ids)

        # Handle stop_vertex filtering
        if graph.stop_vertex and graph.stop_vertex in next_vertices_ids:
            next_vertices_ids = [graph.stop_vertex]

        build_response = VertexBuildResponse(
            inactivated_vertices=list(set(inactivated_vertices)),
            next_vertices_ids=list(set(next_vertices_ids)),
            top_level_vertices=list(set(top_level_vertices)),
            valid=vertex.built,
            params=str(vertex.built_object_repr()),
            id=vertex.id,
            data=result_data_response,
        )

        build_data = json.loads(build_response.model_dump_json())
        event_manager.on_end_vertex(data={"build_data": build_data})

        # Reset per-vertex tracking (same as Playground's _build_vertex)
        graph.reset_inactivated_vertices()
        graph.reset_activated_vertices()
    except Exception:
        logger.opt(exception=True).warning(f"Error emitting end_vertex event for {vertex.id}")


def _resolve_vertex_dependencies(vertex: LangGraphVertex, state: AgentCoreState) -> dict[str, Any]:
    """Resolve vertex parameter dependencies from state.

    Vertices can have parameters that reference other vertices by ID. This function
    resolves those references by looking up the results in the state.
    """
    resolved_params = {}

    for key, value in vertex.raw_params.items():
        # Case 1: Value is a vertex ID (string matching pattern)
        if isinstance(value, str) and value in state["vertices_results"]:
            resolved_params[key] = state["vertices_results"][value]

        # Case 2: Value is a list that might contain vertex IDs
        elif isinstance(value, list):
            resolved_list = []
            for item in value:
                if isinstance(item, str) and item in state["vertices_results"]:
                    resolved_list.append(state["vertices_results"][item])
                else:
                    resolved_list.append(item)
            if resolved_list != value:
                resolved_params[key] = resolved_list

        # Case 3: Value is a dict with vertex ID values
        elif isinstance(value, dict):
            resolved_dict = {}
            has_vertices = False
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str) and sub_value in state["vertices_results"]:
                    has_vertices = True
                    resolved_dict[sub_key] = state["vertices_results"][sub_value]
                else:
                    resolved_dict[sub_key] = sub_value

            if has_vertices:
                resolved_params[key] = resolved_dict

    return resolved_params
