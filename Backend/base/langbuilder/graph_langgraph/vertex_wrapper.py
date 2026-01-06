"""Lightweight vertex wrapper for LangGraph - no dependencies on old graph folder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langbuilder.events.event_manager import EventManager


class LangGraphVertex:
    """Lightweight vertex wrapper for LangGraph execution.
    
    This replaces the heavy Vertex class from graph/vertex/base.py with
    a minimal implementation that only contains what LangGraph needs.
    """
    
    def __init__(self, node_data: dict[str, Any], graph_adapter: Any) -> None:
        """Initialize vertex from node data.
        
        Args:
            node_data: Raw node data from JSON
            graph_adapter: Reference to parent adapter
        """
        # Core identity
        self.id: str = node_data["id"]
        self.base_name: str = self.id.split("-")[0]
        self.data = node_data.get("data", {})
        self.full_data = node_data.copy()
        self.graph = graph_adapter
        
        # Extract node metadata
        node_info = self.data.get("node", {})
        self.display_name = node_info.get("display_name", self.base_name)
        self.description = node_info.get("description", "")
        self.template = node_info.get("template", {})
        self.outputs = node_info.get("outputs", [])
        self.base_classes = node_info.get("base_classes", [])
        self.output_names: list[str] = [
            output["name"] for output in self.outputs if isinstance(output, dict) and "name" in output
        ]
        
        # Type information
        self.vertex_type = self.data.get("type", "")
        self.base_type = self._determine_base_type()
        
        # Parent information
        self.parent_node_id: str | None = node_data.get("parent_node_id")
        self.parent_is_top_level = False  # Will be set during graph processing
        self.layer: int | None = None
        
        # Vertex state (ACTIVE/INACTIVE) for conditional routing
        from langbuilder.graph.vertex.base import VertexStates
        self.state = VertexStates.ACTIVE
        
        # State and flags
        self.is_input = node_info.get("is_input", False) or "input" in self.id.lower()
        self.is_output = node_info.get("is_output", False) or "output" in self.id.lower()
        self.is_state = False
        self.has_session_id = False  # Will be updated when session_id parameter is added
        self.frozen = node_info.get("frozen", False)
        self.will_stream = False  # Whether this vertex will stream results
        self.updated_raw_params = False
        self.has_external_input = False
        self.has_external_output = False
        self.has_cycle_edges = False
        self.use_result = False
        self.is_task = False
        self._is_loop: bool | None = None
        
        # Component state
        try:
            from langbuilder.graph_langgraph.schema import InterfaceComponentTypes
            self.is_interface_component = self.vertex_type in InterfaceComponentTypes
        except (ValueError, ImportError):
            self.is_interface_component = False
        
        # Parameters (will be populated from edges)
        self.params: dict[str, Any] = {}
        self.raw_params: dict[str, Any] = {}
        self.load_from_db_fields: list[str] = []  # Fields that should load from database
        
        # Build state
        self.built = False
        self.built_object: Any = None
        self.built_result: Any = None
        self.result: Any = None
        self.results: dict[str, Any] = {}
        self.artifacts: dict[str, Any] = {}
        self.artifacts_raw: dict[str, Any] | None = {}
        self.artifacts_type: dict[str, str] = {}
        self.outputs_logs: dict[str, Any] = {}
        self.logs: dict[str, list] = {}
        self.build_times: list[float] = []  # Track build times for performance metrics
        
        # Execution tracking
        self.steps: list = []
        self.steps_ran: list = []
        self.task_id: str | None = None
        
        # Edges (for compatibility)
        self._incoming_edges: list | None = None
        self._outgoing_edges: list | None = None
        self._successors_ids: list[str] | None = None
        
        # Component instance (loaded lazily)
        self.custom_component: Any = None
    
    def _determine_base_type(self) -> str:
        """Determine base type from vertex type."""
        # This logic extracted from lazy_load_dict
        type_mapping = {
            "Custom": "custom_components",
            "Component": "component",
        }
        
        template_type = self.template.get("_type", "")
        return type_mapping.get(template_type, "component")
    
    def build_params_from_template(self) -> None:
        """Build parameters from template (before edges are resolved)."""
        import os
        from langbuilder.services.deps import get_storage_service
        from langbuilder.logging import logger
        
        storage_service = get_storage_service()
        
        for key, value_dict in self.template.items():
            if not isinstance(value_dict, dict):
                continue
            
            # Process file type fields (like the old ParameterHandler does)
            if value_dict.get("type") == "file":
                file_path = value_dict.get("file_path")
                logger.debug(f"Processing file field '{key}': file_path={file_path}")
                
                if file_path:
                    try:
                        full_path: str | list[str] = ""
                        if value_dict.get("list"):
                            full_path = []
                            if isinstance(file_path, str):
                                file_path = [file_path]
                            for p in file_path:
                                flow_id, file_name = os.path.split(p)
                                path = storage_service.build_full_path(flow_id, file_name)
                                full_path.append(path)
                        else:
                            flow_id, file_name = os.path.split(file_path)
                            full_path = storage_service.build_full_path(flow_id, file_name)
                        
                        logger.debug(f"Resolved file field '{key}' to: {full_path}")
                        self.raw_params[key] = full_path
                    except ValueError as e:
                        if "too many values to unpack" in str(e):
                            self.raw_params[key] = file_path
                        else:
                            raise
                elif value_dict.get("list"):
                    self.raw_params[key] = []
                else:
                    self.raw_params[key] = None
            elif "value" in value_dict:
                self.raw_params[key] = value_dict["value"]
            
            # Check if this is a session_id parameter
            if key == "session_id":
                self.has_session_id = True
        
        self.params = self.raw_params.copy()
    
    def set_state(self, state: str) -> None:
        """Set the vertex state (ACTIVE or INACTIVE).
        
        Used by conditional routers to deactivate branches.
        
        Args:
            state: "ACTIVE" or "INACTIVE"
        """
        from langbuilder.graph.vertex.base import VertexStates
        self.state = VertexStates[state]
        
        # Track inactivated vertices in the graph
        if self.state == VertexStates.INACTIVE:
            if hasattr(self, 'graph') and self.graph is not None:
                self.graph.inactivated_vertices.add(self.id)
        elif self.state == VertexStates.ACTIVE:
            if hasattr(self, 'graph') and self.graph is not None:
                self.graph.inactivated_vertices.discard(self.id)
    
    def is_active(self) -> bool:
        """Check if vertex is active.
        
        Returns:
            True if vertex is in ACTIVE state
        """
        from langbuilder.graph.vertex.base import VertexStates
        return self.state == VertexStates.ACTIVE
    
    def update_param(self, param_name: str, value: Any) -> None:
        """Update a parameter value.
        
        Args:
            param_name: Name of the parameter
            value: New value
        """
        self.params[param_name] = value
        self.raw_params[param_name] = value
        
        # Update has_session_id flag if session_id parameter is set
        if param_name == "session_id":
            self.has_session_id = True
    
    def update_raw_params(self, params: dict[str, Any], overwrite: bool = False) -> None:
        """Update raw parameters with new values.
        
        Args:
            params: Dictionary of parameters to update
            overwrite: If True, replace existing values. If False, only update if not set.
        """
        for param_name, value in params.items():
            if overwrite or param_name not in self.raw_params:
                self.raw_params[param_name] = value
                self.params[param_name] = value
                
                # Update has_session_id flag if session_id parameter is set
                if param_name == "session_id":
                    self.has_session_id = True
        
        self.updated_raw_params = True
    
    async def build(
        self,
        user_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        files: list[str] | None = None,
        event_manager: EventManager | None = None,
        fallback_to_env_vars: bool = False,
    ) -> None:
        """Build this vertex (execute the component).
        
        Args:
            user_id: User ID
            inputs: Input data
            files: File paths
            event_manager: Event manager
            fallback_to_env_vars: Whether to fallback to env vars
        """
        from langbuilder.interface.initialize import loading
        
        # Resolve parameters that reference other vertices
        await self._resolve_params()
        
        # Instantiate component if not already done
        if not self.custom_component:
            self.custom_component, custom_params = loading.instantiate_class(
                vertex=self,
                user_id=user_id,
                event_manager=event_manager,
            )
        else:
            custom_params = loading.get_params(self.params)
        
        # Build the component
        result = await loading.get_instance_results(
            custom_component=self.custom_component,
            custom_params=custom_params,
            vertex=self,
            fallback_to_env_vars=fallback_to_env_vars,
            base_type=self.base_type,
        )
        
        # Process result
        if isinstance(result, tuple):
            if len(result) == 3:
                self.custom_component, self.built_object, self.artifacts = result
            elif len(result) == 2:
                self.built_object, self.artifacts = result
        else:
            self.built_object = result
        
        self.built_result = self.built_object
        self.built = True
        
        # Create result data
        self.result = {
            "results": self.built_result if isinstance(self.built_result, dict) else {"result": self.built_result},
            "artifacts": self.artifacts,
            "outputs": self.outputs_logs,
        }
    
    def finalize_build(self) -> None:
        """Finalize the build process (compatibility method for frozen vertices).
        
        This is called when restoring a vertex from cache. It ensures the result
        data structure is properly set up.
        """
        from langbuilder.schema import ResultData
        
        result_dict = self.get_built_result() if hasattr(self, 'get_built_result') else self.built_result
        artifacts = getattr(self, 'artifacts_raw', self.artifacts)
        
        # Extract messages from artifacts if it's a dict
        messages = []
        if isinstance(artifacts, dict):
            # Try to extract messages (simplified version)
            if 'messages' in artifacts:
                messages = artifacts['messages']
        
        result_data = ResultData(
            results=result_dict if isinstance(result_dict, dict) else {"result": result_dict},
            artifacts=artifacts,
            outputs=self.outputs_logs,
            logs=getattr(self, 'logs', {}),
            messages=messages,
            component_display_name=self.display_name,
            component_id=self.id,
        )
        self.set_result(result_data)
    
    async def _resolve_params(self) -> None:
        """Resolve parameters that are vertex IDs to actual built results."""
        if not hasattr(self, 'graph') or not self.graph:
            return
        
        # Create a copy of params to modify
        resolved_params = self.params.copy()
        
        # Iterate through parameters
        for param_name, param_value in self.params.items():
            # Check if this parameter value is a vertex ID
            if isinstance(param_value, str) and hasattr(self.graph, 'get_vertex'):
                source_vertex = self.graph.get_vertex(param_value)
                
                # If it's a valid vertex ID and that vertex is built
                if source_vertex and source_vertex.built:
                    # Find the edge to determine which output to use
                    source_output = None
                    for edge_data in self.graph.edges:
                        if edge_data.get('source') == param_value and edge_data.get('target') == self.id:
                            # Get the source handle to determine output name
                            source_handle = edge_data.get('data', {}).get('sourceHandle', {})
                            if isinstance(source_handle, dict):
                                source_output = source_handle.get('name')
                            break
                    
                    # Resolve to the built result
                    result_value = None
                    if source_vertex.built_object is not None:
                        # If built_object is a dict and we know the output name, extract it
                        if isinstance(source_vertex.built_object, dict) and source_output:
                            result_value = source_vertex.built_object.get(source_output, source_vertex.built_object)
                        # If dict with single key, extract the value
                        elif isinstance(source_vertex.built_object, dict) and len(source_vertex.built_object) == 1:
                            result_value = list(source_vertex.built_object.values())[0]
                        else:
                            result_value = source_vertex.built_object
                    elif source_vertex.built_result is not None:
                        result_value = source_vertex.built_result
                    
                    if result_value is not None:
                        resolved_params[param_name] = result_value
        
        # Update params with resolved values
        self.params = resolved_params
    
    def built_object_repr(self) -> str:
        """Get string representation of build status."""
        return "Built successfully ✨" if self.built_object is not None else "Failed to build 😵‍💫"
    
    def add_build_time(self, time: float) -> None:
        """Add a build time to the tracking list.
        
        Args:
            time: Build time in seconds
        """
        self.build_times.append(time)
    
    def avg_build_time(self) -> float:
        """Calculate average build time.
        
        Returns:
            Average build time in seconds, or 0 if no builds
        """
        return sum(self.build_times) / len(self.build_times) if self.build_times else 0
    
    @property
    def is_loop(self) -> bool:
        """Check if any output allows looping."""
        if self._is_loop is None:
            self._is_loop = any(output.get("allows_loop", False) for output in self.outputs)
        return self._is_loop
    
    def to_data(self) -> dict[str, Any]:
        """Return the full node data."""
        return self.full_data
    
    def add_result(self, name: str, result: Any) -> None:
        """Add a named result."""
        self.results[name] = result
    
    def set_result(self, result: Any) -> None:
        """Set the vertex result."""
        self.result = result
    
    @property
    def edges(self) -> list:
        """Get all edges connected to this vertex."""
        if hasattr(self.graph, 'edges'):
            return self.graph.edges
        return []
    
    @property
    def outgoing_edges(self) -> list:
        """Get outgoing edges from this vertex."""
        if self._outgoing_edges is None:
            from langbuilder.graph_langgraph.edge import LangGraphEdge
            # Get edges from graph adapter
            if hasattr(self.graph, 'edges'):
                edge_dicts = [edge for edge in self.graph.edges if edge.get('source') == self.id]
                self._outgoing_edges = []
                for edge_dict in edge_dicts:
                    target_id = edge_dict.get('target')
                    if target_id and hasattr(self.graph, 'get_vertex'):
                        target_vertex = self.graph.get_vertex(target_id)
                        if target_vertex:
                            edge_obj = LangGraphEdge(source=self, target=target_vertex, edge_data=edge_dict)
                            self._outgoing_edges.append(edge_obj)
            else:
                self._outgoing_edges = []
        return self._outgoing_edges
    
    @property
    def incoming_edges(self) -> list:
        """Get incoming edges to this vertex."""
        if self._incoming_edges is None:
            from langbuilder.graph_langgraph.edge import LangGraphEdge
            # Get edges from graph adapter
            if hasattr(self.graph, 'edges'):
                edge_dicts = [edge for edge in self.graph.edges if edge.get('target') == self.id]
                self._incoming_edges = []
                for edge_dict in edge_dicts:
                    source_id = edge_dict.get('source')
                    if source_id and hasattr(self.graph, 'get_vertex'):
                        source_vertex = self.graph.get_vertex(source_id)
                        if source_vertex:
                            edge_obj = LangGraphEdge(source=source_vertex, target=self, edge_data=edge_dict)
                            self._incoming_edges.append(edge_obj)
            else:
                self._incoming_edges = []
        return self._incoming_edges
    
    @property
    def edges_source_names(self) -> set[str | None]:
        """Get set of source handle names from outgoing edges."""
        from loguru import logger
        names = set()
        # Check outgoing edges from graph (edges where this vertex is the source)
        if hasattr(self.graph, 'edges'):
            for edge in self.graph.edges:
                if edge.get('source') == self.id:
                    source_handle = edge.get('data', {}).get('sourceHandle', {})
                    logger.info(f"🔍 EDGES_SOURCE_NAMES: vertex={self.id}, edge_target={edge.get('target')}, source_handle={source_handle}")
                    if isinstance(source_handle, dict):
                        names.add(source_handle.get('name'))
                    else:
                        names.add(None)
        logger.info(f"🔍 EDGES_SOURCE_NAMES RESULT: vertex={self.id}, names={names}")
        return names
    
    @property
    def predecessors(self) -> list:
        """Get predecessor vertices."""
        if hasattr(self.graph, 'get_predecessors'):
            return self.graph.get_predecessors(self)
        # Fallback: get vertices from predecessor_map
        if hasattr(self.graph, 'predecessor_map'):
            pred_ids = self.graph.predecessor_map.get(self.id, [])
            return [self.graph.get_vertex(vid) for vid in pred_ids if self.graph.get_vertex(vid)]
        return []
    
    @property
    def successors(self) -> list:
        """Get successor vertices."""
        if hasattr(self.graph, 'get_successors'):
            return self.graph.get_successors(self)
        # Fallback: get vertices from successor_map
        if hasattr(self.graph, 'successor_map'):
            succ_ids = self.graph.successor_map.get(self.id, [])
            return [self.graph.get_vertex(vid) for vid in succ_ids if self.graph.get_vertex(vid)]
        return []
    
    @property
    def successors_ids(self) -> list[str]:
        """Get IDs of successor vertices."""
        if hasattr(self.graph, 'successor_map'):
            return self.graph.successor_map.get(self.id, [])
        return []
    
    def get_incoming_edge_by_target_param(self, target_param: str) -> str | None:
        """Get source vertex ID by target parameter name."""
        for edge in self.incoming_edges:
            if isinstance(edge, dict):
                target_handle = edge.get('data', {}).get('targetHandle', {})
                if isinstance(target_handle, dict):
                    if target_handle.get('fieldName') == target_param:
                        return edge.get('source')
        return None
