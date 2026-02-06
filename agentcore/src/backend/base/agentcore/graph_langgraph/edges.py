"""Edge handling for LangGraph implementation - fully independent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from langgraph.graph import StateGraph
    
    from agentcore.graph_langgraph.vertex_wrapper import LangGraphVertex


def add_edges_to_workflow(
    workflow: StateGraph,
    edges_data: list[dict[str, Any]],
    vertices_map: dict[str, LangGraphVertex],
) -> None:
    """Add edges from AgentCore to LangGraph workflow.
    
    Args:
        workflow: The LangGraph StateGraph to add edges to
        edges_data: List of edge data from AgentCore
        vertices_map: Map of vertex IDs to Vertex objects
    """
    
    for edge_data in edges_data:
        source_id = edge_data["source"]
        target_id = edge_data["target"]
        
        # Validate that both vertices exist
        if source_id not in vertices_map:
            logger.warning(f"Source vertex {source_id} not found, skipping edge")
            continue
        
        if target_id not in vertices_map:
            logger.warning(f"Target vertex {target_id} not found, skipping edge")
            continue
        
        # Add simple edge (LangGraph will handle ordering via state)
        try:
            workflow.add_edge(source_id, target_id)
            logger.debug(f"Added edge: {source_id} -> {target_id}")
        except Exception as e:
            logger.error(f"Failed to add edge {source_id} -> {target_id}: {e}")


def build_adjacency_maps(edges_data: list[dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build predecessor and successor maps from edges.
    
    This maintains compatibility with the original Graph implementation.
    
    Args:
        edges_data: List of edge data
        
    Returns:
        Tuple of (predecessor_map, successor_map)
    """
    from collections import defaultdict
    
    predecessor_map: dict[str, list[str]] = defaultdict(list)
    successor_map: dict[str, list[str]] = defaultdict(list)
    
    for edge in edges_data:
        source_id = edge["source"]
        target_id = edge["target"]
        
        predecessor_map[target_id].append(source_id)
        successor_map[source_id].append(target_id)
    
    return predecessor_map, successor_map


def build_in_degree_map(edges_data: list[dict[str, Any]], all_vertex_ids: set[str]) -> dict[str, int]:
    """Build in-degree map for vertices.
    
    Args:
        edges_data: List of edge data
        all_vertex_ids: Set of all vertex IDs
        
    Returns:
        Dictionary mapping vertex ID to its in-degree
    """
    in_degree: dict[str, int] = {vid: 0 for vid in all_vertex_ids}
    
    for edge in edges_data:
        target_id = edge["target"]
        if target_id in in_degree:
            in_degree[target_id] += 1
    
    return in_degree
