"""Utility functions for LangGraph - independent of old graph folder."""

from __future__ import annotations

import copy
from collections import defaultdict, deque
from typing import Any


def process_flow(flow_object: dict[str, Any]) -> dict[str, Any]:
    """Process flow data to handle group nodes.
    
    This is a simplified version that handles nested flows.
    
    Args:
        flow_object: Flow data with nodes and edges
        
    Returns:
        Processed flow data
    """
    cloned_flow = copy.deepcopy(flow_object)
    processed_nodes = set()
    
    def process_node(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        
        if node_id in processed_nodes:
            return
        
        # Check if node contains a nested flow
        if (node.get("data") and 
            node["data"].get("node") and 
            node["data"]["node"].get("flow")):
            # Recursively process nested flow
            process_flow(node["data"]["node"]["flow"]["data"])
        
        processed_nodes.add(node_id)
    
    nodes_to_process = deque(cloned_flow.get("nodes", []))
    
    while nodes_to_process:
        node = nodes_to_process.popleft()
        process_node(node)
    
    return cloned_flow


def has_cycle(vertex_ids: list[str], edges: list[tuple[str, str]]) -> bool:
    """Check if graph contains cycles.
    
    Args:
        vertex_ids: List of vertex IDs
        edges: List of (source, target) edge tuples
        
    Returns:
        True if graph has cycles
    """
    # Build adjacency list
    graph = defaultdict(list)
    for source, target in edges:
        graph[source].append(target)
    
    # DFS to detect cycle
    def dfs(vertex: str, visited: set[str], rec_stack: set[str]) -> bool:
        visited.add(vertex)
        rec_stack.add(vertex)
        
        for neighbor in graph[vertex]:
            if neighbor not in visited:
                if dfs(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        
        rec_stack.remove(vertex)
        return False
    
    visited: set[str] = set()
    rec_stack: set[str] = set()
    
    for vertex in vertex_ids:
        if vertex not in visited:
            if dfs(vertex, visited, rec_stack):
                return True
    
    return False


def find_cycle_vertices(edges: list[tuple[str, str]]) -> list[str]:
    """Find vertices that are part of cycles.
    
    Args:
        edges: List of (source, target) edge tuples
        
    Returns:
        List of vertex IDs in cycles
    """
    # Build adjacency list
    graph = defaultdict(list)
    for source, target in edges:
        graph[source].append(target)
    
    cycle_vertices = set()
    
    def dfs(vertex: str, visited: set[str], rec_stack: set[str], path: list[str]) -> None:
        visited.add(vertex)
        rec_stack.add(vertex)
        path.append(vertex)
        
        for neighbor in graph[vertex]:
            if neighbor not in visited:
                dfs(neighbor, visited, rec_stack, path)
            elif neighbor in rec_stack:
                # Found a cycle - add all vertices in the cycle
                cycle_start_idx = path.index(neighbor)
                cycle_vertices.update(path[cycle_start_idx:])
        
        rec_stack.remove(vertex)
        path.pop()
    
    visited: set[str] = set()
    rec_stack: set[str] = set()
    
    #for vertex in graph:
    for vertex in list(graph):
        if vertex not in visited:
            dfs(vertex, visited, rec_stack, [])
    
    return sorted(cycle_vertices)


def build_adjacency_maps(
    edges_data: list[dict[str, Any]]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build predecessor and successor maps from edges.
    
    Args:
        edges_data: List of edge data dictionaries
        
    Returns:
        Tuple of (predecessor_map, successor_map)
    """
    predecessor_map: dict[str, set[str]] = defaultdict(set)
    successor_map: dict[str, set[str]] = defaultdict(set)
    
    for edge in edges_data:
        source_id = edge.get("source")
        target_id = edge.get("target")
        
        if source_id and target_id:
            predecessor_map[target_id].add(source_id)
            successor_map[source_id].add(target_id)
    
    # Convert sets to lists for consistency
    return {k: list(v) for k, v in predecessor_map.items()}, {k: list(v) for k, v in successor_map.items()}


def build_in_degree_map(
    edges_data: list[dict[str, Any]], 
    all_vertex_ids: set[str]
) -> dict[str, int]:
    """Build in-degree map for vertices.
    
    Args:
        edges_data: List of edge data
        all_vertex_ids: Set of all vertex IDs
        
    Returns:
        Dictionary mapping vertex ID to its in-degree
    """
    in_degree: dict[str, int] = {vid: 0 for vid in all_vertex_ids}
    
    for edge in edges_data:
        target_id = edge.get("target")
        if target_id and target_id in in_degree:
            in_degree[target_id] += 1
    
    return in_degree


def filter_vertices_up_to_vertex(
    vertices_ids: list[str],
    stop_vertex_id: str,
    predecessor_map: dict[str, list[str]],
) -> set[str]:
    """Filter vertices to only include those that lead up to (are predecessors of) the stop vertex.
    
    This function performs a breadth-first traversal backwards from the stop vertex,
    collecting all vertices that are predecessors (directly or indirectly) of the stop vertex.
    This is used for "Run Till Specific Component" functionality.
    
    Args:
        vertices_ids: List of all vertex IDs in the graph
        stop_vertex_id: ID of the vertex to stop at (will be included in result)
        predecessor_map: Map of vertex ID -> list of predecessor vertex IDs
        
    Returns:
        Set of vertex IDs that lead to the stop vertex (including the stop vertex itself)
        
    Example:
        Given graph: A -> B -> C -> D
        If stop_vertex_id = "C", returns {"A", "B", "C"}
        
        Given graph: 
            A -> C
            B -> C -> D
        If stop_vertex_id = "C", returns {"A", "B", "C"}
    """
    vertices_set = set(vertices_ids)
    
    # If stop vertex doesn't exist, return empty
    if stop_vertex_id not in vertices_set:
        return set()
    
    # Start with the target vertex
    filtered_vertices = {stop_vertex_id}
    queue = deque([stop_vertex_id])
    
    # Process vertices in breadth-first order going backwards
    while queue:
        current_vertex = queue.popleft()
        predecessors = predecessor_map.get(current_vertex, [])
        
        for predecessor in predecessors:
            if predecessor in vertices_set and predecessor not in filtered_vertices:
                filtered_vertices.add(predecessor)
                queue.append(predecessor)
    
    return filtered_vertices


def filter_vertices_from_vertex(
    vertices_ids: list[str],
    start_vertex_id: str,
    successor_map: dict[str, list[str]],
) -> set[str]:
    """Filter vertices to only include those reachable from the start vertex.
    
    This function performs a breadth-first traversal forward from the start vertex,
    collecting all vertices that are successors (directly or indirectly) of the start vertex.
    This is used for "Run From Specific Component" functionality.
    
    Args:
        vertices_ids: List of all vertex IDs in the graph
        start_vertex_id: ID of the vertex to start from (will be included in result)
        successor_map: Map of vertex ID -> list of successor vertex IDs
        
    Returns:
        Set of vertex IDs reachable from the start vertex (including the start vertex itself)
        
    Example:
        Given graph: A -> B -> C -> D
        If start_vertex_id = "B", returns {"B", "C", "D"}
    """
    vertices_set = set(vertices_ids)
    
    # If start vertex doesn't exist, return empty
    if start_vertex_id not in vertices_set:
        return set()
    
    # Start with the start vertex
    filtered_vertices = {start_vertex_id}
    queue = deque([start_vertex_id])
    
    # Process vertices in breadth-first order going forward
    while queue:
        current_vertex = queue.popleft()
        successors = successor_map.get(current_vertex, [])
        
        for successor in successors:
            if successor in vertices_set and successor not in filtered_vertices:
                filtered_vertices.add(successor)
                queue.append(successor)
    
    return filtered_vertices


def get_sorted_vertices_for_langgraph(
    vertices_ids: list[str],
    in_degree_map: dict[str, int],
    predecessor_map: dict[str, list[str]],
    successor_map: dict[str, list[str]],
    cycle_vertices: set[str],
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    is_cyclic: bool = False,
) -> tuple[list[str], list[str], set[str]]:
    """Get sorted vertices for LangGraph execution, handling stop/start components.
    
    This function:
    1. Filters vertices based on stop_component_id (only predecessors)
    2. Filters vertices based on start_component_id (only successors)
    3. Returns first layer (vertices with no dependencies) and all vertices to run
    
    Args:
        vertices_ids: All vertex IDs in the graph
        in_degree_map: Map of vertex ID to number of incoming edges
        predecessor_map: Map of vertex ID to list of predecessor IDs
        successor_map: Map of vertex ID to list of successor IDs
        cycle_vertices: Set of vertex IDs that are part of cycles
        stop_component_id: Optional ID of component to stop at
        start_component_id: Optional ID of component to start from
        is_cyclic: Whether the graph contains cycles
        
    Returns:
        Tuple of (first_layer_vertices, all_vertices_to_run, filtered_vertices_set)
    """
    working_vertices = set(vertices_ids)
    
    # Handle cycle case: if stop component is in a cycle, convert to start
    if stop_component_id and stop_component_id in cycle_vertices:
        start_component_id = stop_component_id
        stop_component_id = None
    
    # Filter vertices up to stop component (only predecessors)
    if stop_component_id is not None:
        filtered = filter_vertices_up_to_vertex(
            list(working_vertices),
            stop_component_id,
            predecessor_map,
        )
        working_vertices = filtered
    
    # Filter vertices from start component (only successors + their predecessors)
    if start_component_id is not None:
        # Get all vertices reachable from start
        reachable = filter_vertices_from_vertex(
            list(working_vertices),
            start_component_id,
            successor_map,
        )
        # Also include predecessors of reachable vertices
        connected_vertices = set()
        for vertex in reachable:
            predecessors_of_vertex = filter_vertices_up_to_vertex(
                list(working_vertices),
                vertex,
                predecessor_map,
            )
            connected_vertices.update(predecessors_of_vertex)
        working_vertices = connected_vertices
    
    # Build filtered in_degree_map for the working vertices
    filtered_in_degree = {}
    for vid in working_vertices:
        # Count only predecessors that are in working_vertices
        preds = predecessor_map.get(vid, [])
        filtered_preds = [p for p in preds if p in working_vertices]
        filtered_in_degree[vid] = len(filtered_preds)
    
    # First layer: vertices with no dependencies (in_degree == 0) within filtered set
    first_layer = [vid for vid, degree in filtered_in_degree.items() if degree == 0]
    
    # All vertices to run
    vertices_to_run = list(working_vertices)
    
    return first_layer, vertices_to_run, working_vertices
