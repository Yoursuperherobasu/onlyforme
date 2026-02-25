# Graph LangGraph — Code Walkthrough

**Module path:** `src/backend/base/agentcore/graph_langgraph/`
**Purpose:** Converts AgentCore's visual drag-and-drop agent graphs into executable LangGraph `StateGraph` workflows.

---

## 1. High-Level Overview

AgentCore lets users build AI agents visually by connecting components (nodes) with wires (edges). This module is the **execution engine** that takes that visual graph and runs it:

1. Reads the graph JSON (nodes + edges)
2. Converts each node into an executable LangGraph node
3. Compiles the graph into a LangGraph `StateGraph`
4. Runs the compiled graph, passing a shared `AgentCoreState` through every node
5. Collects and returns results

---

## 2. File Structure

```
graph_langgraph/
├── __init__.py               ← Public API exports
├── adapter.py                ← MAIN ENGINE — LangGraphAdapter (core orchestrator)
├── vertex_wrapper.py         ← LangGraphVertex (wraps one component/node)
├── executor.py               ← LangGraphExecutor (manages workflow invocation)
├── nodes.py                  ← create_node_function (converts vertex → LangGraph node)
├── state.py                  ← AgentCoreState (shared state flowing through graph)
├── state_model.py            ← Dynamic Pydantic model creation utility
├── edge.py                   ← LangGraphEdge (represents a connection between nodes)
├── edges.py                  ← Edge utilities (add_edges_to_workflow)
├── runnable_vertices_manager.py ← Execution state tracker
├── utils.py                  ← Graph algorithms (sort, cycle detection, BFS)
├── schema.py                 ← Data models, enums, type definitions
├── logging.py                ← DB logging for vertex builds and transactions
├── streaming.py              ← Event streaming utilities
├── param_handler.py          ← Parameter processing helpers
└── constants.py              ← Finish sentinel class
```

---

## 3. Entry Point

### `__init__.py` — Public API

This file is the **entry point** for any external code that imports from this module. It re-exports all public classes and functions.

Key aliases defined here for backward compatibility:
```python
Graph  = LangGraphAdapter   # The main orchestrator
Vertex = LangGraphVertex    # A single node wrapper
Edge   = LangGraphEdge      # A connection between nodes
```

Everything external code needs comes from here.

---

## 4. File-by-File Description

---

### `adapter.py` — `LangGraphAdapter` (The Engine)

**Role:** Central orchestrator. Does everything: builds, compiles, and runs the graph.

**Size:** ~87 KB — the largest and most important file.

#### How it is created

```python
adapter = LangGraphAdapter.from_payload(
    payload={"nodes": [...], "edges": [...]},
    agent_id="abc-123",
    agent_name="My Agent"
)
```

#### Key attributes

| Attribute | Type | Purpose |
|---|---|---|
| `vertices` | `list[LangGraphVertex]` | All nodes in the graph |
| `vertex_map` | `dict[str, LangGraphVertex]` | Lookup node by its ID |
| `edges` | `list[dict]` | Raw edge data |
| `workflow` | `StateGraph` | The LangGraph state graph (before compile) |
| `compiled_app` | `CompiledGraph` | The compiled, runnable graph |
| `predecessor_map` | `dict[str, list[str]]` | Which nodes feed into each node |
| `successor_map` | `dict[str, list[str]]` | Which nodes each node feeds into |
| `cycle_vertices` | `set[str]` | Nodes that are part of a loop/cycle |
| `is_cyclic` | `bool` | Whether the graph contains loops |

#### Key methods

| Method | Purpose |
|---|---|
| `from_payload()` | Class method — parse JSON payload and create adapter instance |
| `add_nodes_and_edges()` | Parse nodes/edges, create vertex objects, detect cycles, build adjacency maps |
| `_build_vertices()` | Create `LangGraphVertex` objects from raw node data |
| `_build_edges()` | Process edge data, resolve connections between vertices |
| `_build_langgraph_workflow()` | Create `StateGraph`, add all nodes and edges, compile to `CompiledGraph` |
| `arun()` | **Main execution method** — async, runs the whole graph end-to-end |
| `build_vertex()` | Build (execute) a single vertex |
| `sort_vertices()` | Calculate execution order using topological sort |
| `initialize_run()` | Reset all state before a new execution run |
| `get_next_runnable_vertices()` | After a vertex completes, discover which vertices can now run |
| `end_all_traces_in_context()` | Finalize observability traces after run completes |

#### Logging contexts supported

The adapter supports logging to multiple transaction tables based on deployment context:

| Flag/Field | Table logged to |
|---|---|
| `skip_dev_logging=False` | `transaction` (dev) |
| `orch_session_id` set | `orch_transaction` |
| `prod_deployment_id` set | `transaction_prod` |
| `uat_deployment_id` set | `transaction_uat` |

---

### `state.py` — `AgentCoreState` (Shared State)

**Role:** Defines the single state object that is passed between every node during graph execution.

This is a Python `TypedDict` — a typed dictionary that LangGraph carries through the execution pipeline.

#### Key fields

| Field | Type | Purpose |
|---|---|---|
| `vertices_results` | `dict[str, Any]` | Stores each vertex's output, keyed by vertex ID |
| `artifacts` | `dict[str, Any]` | Stores generated artifacts (files, images, etc.) per vertex |
| `completed_vertices` | `list[str]` | Accumulating list of finished vertex IDs |
| `events` | `list[dict]` | Accumulating stream of execution events for real-time updates |
| `current_vertex` | `str` | ID of the vertex currently executing |
| `agent_id`, `agent_name`, `session_id`, `user_id` | `str` | Agent/session metadata |
| `event_manager` | `Any` | Optional event manager for real-time streaming |
| `input_data` | `dict` | The user's input (e.g. chat message) |
| `predecessor_map`, `successor_map`, `in_degree_map` | `dict` | Graph structure maps for traversal logic |
| `cycle_vertices` | `set[str]` | Nodes in loops |
| `vertices_layers` | `list[list[str]]` | Execution layers (each layer can run in parallel) |
| `stop_component_id` | `str \| None` | Run only up to this node (partial execution) |
| `start_component_id` | `str \| None` | Start execution from this node (partial execution) |

> **Why one shared state?** This pattern (called a "state machine") means every node reads what previous nodes produced and adds its own output. No node needs to know the full graph — it just reads what it needs from state and writes its result back.

---

### `vertex_wrapper.py` — `LangGraphVertex` (Node Wrapper)

**Role:** Wraps a single component/node from the visual graph. Responsible for executing one component.

#### Key attributes

| Attribute | Purpose |
|---|---|
| `id` | Unique vertex identifier |
| `display_name` | Human-readable component name |
| `template` | Component configuration (parameters from UI) |
| `raw_params` | Resolved parameter values |
| `built_result` | The output produced after execution |
| `artifacts` | Generated files or binary data |
| `outputs_logs` | Structured output metadata |
| `is_input` / `is_output` | Whether this is an input/output interface component |

#### Key methods

| Method | Purpose |
|---|---|
| `build_params_from_template()` | Extract initial parameter values from the UI template config |
| `update_raw_params()` | Update parameter values (e.g. inject user input) |
| `build()` | **Execute the component** — resolves params, instantiates the component class, runs it, stores result |
| `_resolve_params()` | Look at incoming edges to pull output values from predecessor vertices |
| `set_state()` | Mark vertex as `ACTIVE` or `INACTIVE` (used by conditional routers) |
| `is_active()` | Check whether this vertex should run (for conditional branching) |
| `finalize_build()` | Post-process after restoring from cache |

#### What happens inside `build()`

1. Resolve parameters — look at edges to find what predecessor nodes produced
2. Instantiate the component class (e.g. `ChatOpenAI`, `VectorStore`, etc.)
3. Execute the component's method
4. Store `built_result`, `artifacts`, and `outputs_logs`
5. Return structured result data

---

### `nodes.py` — `create_node_function`

**Role:** Converts a `LangGraphVertex` into a LangGraph-compatible async node function.

#### `create_node_function(vertex)` → `async node_function(state)`

This is the bridge between AgentCore's vertex system and LangGraph's node system.

For each vertex, it creates an async function that:

1. **Resolves dependencies** — calls `_resolve_vertex_dependencies()` to look up predecessor outputs from state
2. **Updates params** — injects resolved values into the vertex
3. **Builds the vertex** — calls `vertex.build(...)` to actually execute the component
4. **Updates state** — writes results, artifacts, events into the shared state
5. **Logs to DB** — calls `log_vertex_build()` to record the execution in the database
6. **Handles errors** — catches exceptions, writes error events, re-raises

#### `_resolve_vertex_dependencies(vertex, state)`

Inspects the vertex's raw params and replaces any values that are vertex IDs with the actual result from that vertex. Handles strings, lists, and dicts.

---

### `executor.py` — `LangGraphExecutor`

**Role:** Manages the actual invocation of the compiled LangGraph workflow.

Wraps `adapter.compiled_app` and provides a clean interface for running it.

#### Key methods

| Method | Purpose |
|---|---|
| `execute()` | Run the workflow once and return final state |
| `stream_execute()` | Run the workflow and yield state updates as they happen (async generator) |
| `_create_initial_state()` | Build the starting `AgentCoreState` from adapter metadata and user inputs |
| `get_results()` | Extract output vertex results from the final state |

#### `execute()` internal flow

1. Update input vertices with user-provided data (e.g. the chat message)
2. Call `_create_initial_state()` to build starting state
3. Call `compiled_app.ainvoke(initial_state)` — LangGraph runs the full graph
4. Return final state

---

### `runnable_vertices_manager.py` — `RunnableVerticesManager`

**Role:** Tracks which vertices are ready to run, currently running, and completed, during adaptive graph traversal.

This is used by the adapter's `arun()` loop to decide what to execute next.

#### Key attributes

| Attribute | Purpose |
|---|---|
| `run_map` | Maps each vertex to its successors (reverse of predecessor_map) |
| `run_predecessors` | Pending predecessors for each vertex (when empty → vertex can run) |
| `vertices_to_run` | Set of vertices that are eligible to run |
| `vertices_being_run` | Set of vertices currently executing |
| `cycle_vertices` | Vertices in loops/cycles |
| `ran_at_least_once` | Cycle vertices that have already executed once |

#### Key methods

| Method | Purpose |
|---|---|
| `is_vertex_runnable()` | Check if a vertex can start: is active, not already running, all predecessors done |
| `are_all_predecessors_fulfilled()` | For cycle vertices: complex logic for first-run vs re-run; for regular vertices: simple predecessor check |
| `remove_from_predecessors()` | After a vertex completes, remove it from pending predecessor lists |
| `build_run_map()` | Build the reverse map from predecessor_map |
| `update_vertex_run_state()` | Mark a vertex as runnable or done |

> **Cycle handling logic:** On the first execution of a cycle vertex, it only waits for non-cycle predecessors. On subsequent executions, it waits for ALL predecessors to be done. This prevents infinite loops while supporting iterative workflows.

---

### `utils.py` — Graph Algorithms

**Role:** Graph algorithms used during graph construction and execution ordering.

#### Key functions

| Function | Purpose |
|---|---|
| `process_agent()` | Handle nested agents (group nodes that contain sub-graphs) |
| `has_cycle()` | DFS-based cycle detection — returns `True` if graph has any cycle |
| `find_cycle_vertices()` | DFS to find all vertex IDs that are part of cycles |
| `build_adjacency_maps()` | Build `predecessor_map` and `successor_map` from edge list |
| `build_in_degree_map()` | Calculate how many inputs each vertex has |
| `layered_topological_sort()` | **Core sort** — returns layers of vertices where each layer can run in parallel |
| `filter_vertices_up_to_vertex()` | BFS backward from a node — used for "stop at component" feature |
| `filter_vertices_from_vertex()` | BFS forward from a node — used for "start from component" feature |
| `get_sorted_vertices_for_langgraph()` | Main sorting entry point — applies stop/start filters, then topological sort |
| `find_start_component_id()` | Auto-detect which input vertex to start from (priority: Webhook > ChatInput) |
| `has_chat_output()` | Check if graph has a ChatOutput component |
| `has_output_vertex()` | Check if graph has any output component |

#### `layered_topological_sort()` — How it works

Modified Kahn's algorithm:
1. Start with all vertices that have `in_degree = 0` (no predecessors)
2. Process them as "layer 0"
3. Reduce `in_degree` of their successors
4. Any successors that now have `in_degree = 0` form the next layer
5. Repeat until all vertices are sorted
6. For cycle vertices: allow up to `MAX_CYCLE_APPEARANCES = 2` re-appearances

This produces execution layers — vertices in the same layer can run in parallel.

---

### `schema.py` — Data Models and Types

**Role:** All data structures and type definitions used across the module.

#### Key types

| Type | Purpose |
|---|---|
| `NodeTypeEnum` | `noteNode` or `genericNode` |
| `VertexStates` | `ACTIVE`, `INACTIVE`, `ERROR` — used for conditional routing |
| `InterfaceComponentTypes` | Enum of all interface node types: `ChatInput`, `ChatOutput`, `TextInput`, etc. |
| `ResultData` | Output of a single vertex execution |
| `RunOutputs` | Final result returned from `adapter.arun()` — contains inputs + list of `ResultData` |
| `VertexBuildResult` | Named tuple: `(vertex, build_result)` |
| `EdgeData` | Full edge definition with source/target/handle info |
| `GraphDump` | Complete graph export format |
| `SourceHandle` / `TargetHandle` | Pydantic models for edge connection points |
| `ResultPair` | `(result, extra_data)` pair |

#### Component groupings

```python
INPUT_COMPONENTS   = {ChatInput, Webhook, TextInput}
OUTPUT_COMPONENTS  = {ChatOutput, DataOutput, TextOutput}
CHAT_COMPONENTS    = {ChatInput, ChatOutput}
RECORDS_COMPONENTS = {DataOutput}
```

---

### `logging.py` — Database Logging

**Role:** Logs vertex executions and transactions to the database.

#### Key functions

| Function | Purpose |
|---|---|
| `log_vertex_build()` | Record a vertex execution (vertex_id, valid/failed, params, result, artifacts) to `vertex_build` table |
| `log_transaction()` | Record a full transaction (inputs, outputs, status, error) to transaction tables |
| `_vertex_to_primitive_dict()` | Strip non-primitive types from params before logging |

Both functions respect feature flags (`transactions_storage_enabled`, `vertex_builds_storage_enabled`) and apply length/item limits before writing.

---

### `streaming.py` — Event Streaming

**Role:** Converts internal execution events into streamable NDJSON format for real-time client updates.

#### Key functions

| Function | Purpose |
|---|---|
| `stream_langgraph_events()` | Async generator — yields events from state as execution progresses |
| `_convert_to_agentcore_event()` | Convert a LangGraph event dict to AgentCore's event schema |
| `_emit_event()` | Emit event via the `event_manager` (if available) |
| `format_event_as_ndjson()` | Format an event as newline-delimited JSON for HTTP streaming |

---

### `param_handler.py` — Parameter Processing

**Role:** Handles extraction, validation, and processing of component parameters from the node template.

Used internally by `LangGraphVertex` when resolving what values to pass to a component.

---

### `state_model.py` — Dynamic State Model

**Role:** Creates dynamic Pydantic models at runtime from arbitrary field definitions.

#### `create_state_model(model_name, validate, **kwargs)`

- Accepts field definitions as `(type, default)` tuples, `FieldInfo`, or callables
- Converts callable fields into Pydantic properties
- Returns a fully functional Pydantic model class

Used when components need dynamic structured output types.

---

### `edge.py` — `LangGraphEdge`

**Role:** Lightweight wrapper representing a directed connection between two vertices.

#### Key attributes

| Attribute | Purpose |
|---|---|
| `source_id` / `target_id` | IDs of the connected vertices |
| `source` / `target` | References to the actual vertex objects |
| `target_param` | The parameter name on the target vertex that this edge feeds |
| `source_handle` / `target_handle` | Handle metadata (field names, types) |
| `is_cycle` | Whether this edge closes a loop |
| `valid_handles` | Whether both handles are properly defined |

---

### `edges.py` — Edge Utilities

**Role:** Utility functions for adding edges to the LangGraph `StateGraph`.

#### `add_edges_to_workflow(workflow, edges, vertex_map)`

Iterates the edge list and calls `workflow.add_edge(source_id, target_id)` for each valid connection. Validates that both source and target exist in the graph.

---

### `constants.py` — `Finish` Sentinel

**Role:** A sentinel class used to signal that graph execution is complete.

```python
class Finish:
    def __bool__(self): return True
    def __eq__(self, other): return isinstance(other, Finish)
```

Used in execution control flow to detect when the graph has finished.

---

## 5. Code Flow — End to End

```
┌──────────────────────────────────────────────────────────────┐
│  STEP 1 — Parse Input                                        │
│  JSON payload { "nodes": [...], "edges": [...] }             │
│  → LangGraphAdapter.from_payload()                           │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 2 — Build Graph Structure                              │
│  → add_nodes_and_edges()                                     │
│     - Create LangGraphVertex objects for each node           │
│     - Parse edge connections                                 │
│     - Detect cycles (has_cycle / find_cycle_vertices)        │
│     - Build predecessor_map, successor_map, in_degree_map    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 3 — Compile LangGraph Workflow                         │
│  → _build_langgraph_workflow()                               │
│     - Create StateGraph(AgentCoreState)                      │
│     - For each vertex: create_node_function(vertex)          │
│       and add to workflow                                    │
│     - Add edges between nodes                                │
│     - Compile → CompiledGraph (compiled_app)                 │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 4 — Initialize Run                                     │
│  → adapter.arun(inputs, session_id)                          │
│     - initialize_run(): reset states, generate run_id        │
│     - sort_vertices(): compute execution layer order         │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 5 — Execute (per vertex, in order)                     │
│  → For each vertex layer:                                    │
│     - node_function(state) called by LangGraph               │
│     - _resolve_vertex_dependencies() → pull predecessor data │
│     - vertex.build() → instantiate + run component           │
│     - Write results to state["vertices_results"][vertex_id]  │
│     - Emit event to state["events"]                          │
│     - log_vertex_build() → write to DB                       │
│     - Discover next runnable vertices                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 6 — Return Results                                     │
│  → Collect output vertex results from final state            │
│  → Return RunOutputs(inputs=..., outputs=[ResultData, ...])  │
│  → end_all_traces_in_context() → finalize observability      │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Important Design Patterns

### Single Shared State
All nodes read from and write to one `AgentCoreState` object. Each node writes its output to `state["vertices_results"][my_id]`, and downstream nodes read from `state["vertices_results"][predecessor_id]`.

### Adaptive Execution
After each vertex completes, the system dynamically discovers which vertices are now runnable (all predecessors done). This allows parallel execution of independent vertices.

### Conditional Routing (ACTIVE / INACTIVE)
Any component can call `set_state(VertexStates.INACTIVE)` on downstream vertices to deactivate branches. The execution engine respects this, skipping INACTIVE vertices automatically.

### Cycle / Loop Support
Graphs with loops are supported. Cycle vertices are allowed to run a limited number of times (`MAX_CYCLE_APPEARANCES = 2`) with different readiness rules on first vs. subsequent executions.

### Partial Execution
`stop_component_id` — run only the predecessors of a given node (backward BFS).
`start_component_id` — run only from a given node forward (forward BFS + their predecessors).

### Redis Serialization
Both `LangGraphAdapter` and `LangGraphVertex` implement `__getstate__` / `__setstate__` for Redis serialization. Non-serializable objects (like instantiated component classes) are excluded and re-created on restore.

---

## 7. Class Relationships

```
LangGraphAdapter  (orchestrator)
├── has many  → LangGraphVertex   (one per visual node)
├── has many  → LangGraphEdge     (one per visual wire)
├── uses      → RunnableVerticesManager  (tracks what can run)
├── compiles  → StateGraph (LangGraph)  → CompiledGraph
└── delegates to → LangGraphExecutor (for direct invocation)

LangGraphVertex  (one component/node)
├── has many  → LangGraphEdge  (incoming_edges, outgoing_edges)
├── knows its → predecessors, successors
└── produces  → built_result, artifacts, outputs_logs

LangGraphEdge  (one connection)
├── source    → LangGraphVertex
├── target    → LangGraphVertex
└── carries   → target_param (which field the output feeds into)

AgentCoreState  (flows through execution)
├── accumulates → vertices_results
├── accumulates → events
└── carries     → agent metadata, graph maps, cycle info
```

---

## 8. Key Method Reference

| Method | File | Description |
|---|---|---|
| `LangGraphAdapter.from_payload()` | adapter.py | Parse JSON and create adapter |
| `LangGraphAdapter.add_nodes_and_edges()` | adapter.py | Build graph structure from raw data |
| `LangGraphAdapter._build_langgraph_workflow()` | adapter.py | Compile to LangGraph StateGraph |
| `LangGraphAdapter.arun()` | adapter.py | Main execution entry point (async) |
| `LangGraphAdapter.initialize_run()` | adapter.py | Reset state before each run |
| `LangGraphAdapter.sort_vertices()` | adapter.py | Get ordered execution plan |
| `LangGraphAdapter.get_next_runnable_vertices()` | adapter.py | Adaptive discovery after each vertex |
| `LangGraphVertex.build()` | vertex_wrapper.py | Execute a single component |
| `LangGraphVertex._resolve_params()` | vertex_wrapper.py | Pull values from predecessor vertices |
| `LangGraphVertex.set_state()` | vertex_wrapper.py | ACTIVE/INACTIVE for conditional routing |
| `create_node_function()` | nodes.py | Convert vertex to LangGraph node function |
| `_resolve_vertex_dependencies()` | nodes.py | Resolve vertex ID references in params |
| `LangGraphExecutor.execute()` | executor.py | Invoke compiled graph and return result |
| `LangGraphExecutor.stream_execute()` | executor.py | Invoke graph with streaming |
| `RunnableVerticesManager.is_vertex_runnable()` | runnable_vertices_manager.py | Check if vertex can start now |
| `RunnableVerticesManager.are_all_predecessors_fulfilled()` | runnable_vertices_manager.py | Check predecessor completion (cycle-aware) |
| `layered_topological_sort()` | utils.py | Compute parallel execution layers |
| `has_cycle()` / `find_cycle_vertices()` | utils.py | Cycle detection algorithms |
| `build_adjacency_maps()` | utils.py | Build predecessor/successor maps |
| `filter_vertices_up_to_vertex()` | utils.py | BFS backward for stop-at-component |
| `filter_vertices_from_vertex()` | utils.py | BFS forward for start-from-component |
| `log_vertex_build()` | logging.py | Write vertex execution record to DB |
| `log_transaction()` | logging.py | Write transaction record to DB |

---

*Document generated: February 2026*