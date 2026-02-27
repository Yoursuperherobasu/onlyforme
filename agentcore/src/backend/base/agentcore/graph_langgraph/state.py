
from __future__ import annotations

from operator import add
from typing import TYPE_CHECKING, Annotated, Any, TypedDict


def _merge_dicts(left: dict, right: dict) -> dict:
    """Reducer that merges two dicts.

    Used for state channels that can be written by parallel nodes
    (e.g. ``vertices_results``, ``artifacts``, ``outputs_logs``).
    Without this, LangGraph raises ``InvalidUpdateError`` when two
    nodes in the same superstep both return state updates for the
    same dict key.
    """
    merged = left.copy()
    merged.update(right)
    return merged


def _last_value(left: str, right: str) -> str:
    """Reducer that simply takes the latest value (last writer wins)."""
    return right


# EventManager is optional and only used at runtime, use string annotation
class AgentCoreState(TypedDict):
    """State that agents through the LangGraph execution.

    This state is passed between nodes and maintains the execution context,
    results, and events for the entire agent.
    """

    # Core execution results — use _merge_dicts reducer so parallel nodes
    # can each contribute their vertex's results without conflicting.
    vertices_results: Annotated[dict[str, Any], _merge_dicts]
    artifacts: Annotated[dict[str, Any], _merge_dicts]
    outputs_logs: Annotated[dict[str, Any], _merge_dicts]

    # Current execution context — last writer wins for parallel nodes
    current_vertex: Annotated[str, _last_value]
    completed_vertices: Annotated[list[str], add]  # List of completed vertex IDs
    
    # Event streaming (accumulate events as list)
    events: Annotated[list[dict[str, Any]], add]
    
    # Agent metadata
    agent_id: str
    agent_name: str | None
    session_id: str
    user_id: str | None
    
    # Execution context (use Any to avoid import issues)
    event_manager: Any  # EventManager | None - using Any to avoid circular imports
    input_data: dict[str, Any]
    files: list[str] | None
    
    # Configuration
    fallback_to_env_vars: bool
    stop_component_id: str | None
    start_component_id: str | None
    
    # Vertex maps for traversal
    vertex_objects: dict[str, Any]  # Store actual vertex objects
    predecessor_map: dict[str, list[str]]
    successor_map: dict[str, list[str]]
    in_degree_map: dict[str, int]
    
    # Cycle handling
    cycle_vertices: set[str]
    is_cyclic: bool
    
    # Layer execution tracking
    current_layer: int
    vertices_layers: list[list[str]]

    # Input vertex tracking (for parameter filtering in node_function)
    input_vertex_ids: list[str]
