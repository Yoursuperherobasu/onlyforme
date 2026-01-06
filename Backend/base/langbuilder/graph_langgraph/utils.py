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
    
    for vertex in graph:
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
