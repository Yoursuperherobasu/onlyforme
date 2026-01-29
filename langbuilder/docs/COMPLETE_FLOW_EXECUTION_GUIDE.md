# 🎓 Complete Flow Execution Guide: From Code to Runtime

## A Comprehensive Deep Dive into Langbuilder's Component System

---

## 📚 Table of Contents

1. [Why Code Needs to Be in String Format](#why-code-needs-to-be-in-string-format)
2. [Template Folder Deep Dive](#template-folder-deep-dive)
3. [What is FrontendNode](#what-is-frontendnode)
4. [Complete Flow Execution: Step by Step](#complete-flow-execution-step-by-step)
5. [LangGraph Integration](#langgraph-integration)
6. [Example 1: Simple Chat Flow (Without Tool)](#example-1-simple-chat-flow-without-tool)
7. [Example 2: Calculator Tool Flow](#example-2-calculator-tool-flow)
8. [Complete Code Execution Trace](#complete-code-execution-trace)
9. [When is Each Folder Used? (UI vs Runtime)](#when-is-each-folder-used)
10. [Detailed Examples: UI Loading vs Runtime Execution](#detailed-examples-ui-vs-runtime)
11. [Tracing with Langfuse: Complete Integration](#tracing-with-langfuse)

---

## 1. Why Code Needs to Be in String Format {#why-code-needs-to-be-in-string-format}

### The Core Problem

When you create a flow in Langbuilder's visual UI, the system needs to:
1. **Store** the component's Python code in a database (JSON format)
2. **Send** it to the frontend as part of the flow definition
3. **Reconstruct** it at runtime on potentially different servers

**Python classes CANNOT be directly stored in JSON or sent over HTTP.**

### The Solution: Code as String

```
┌─────────────────────────────────────────────────────────────────────┐
│                    YOUR COMPONENT FILE                               │
│  ──────────────────────────────────                                  │
│  calculator.py (on disk)                                             │
│                                                                      │
│  class CalculatorToolComponent(LCToolComponent):                     │
│      display_name = "Calculator [DEPRECATED]"                        │
│      icon = "calculator"                                             │
│      ...                                                             │
└────────────────────────────────────────────────────────────────────┘
                               │
                               ▼ READ AS STRING
┌─────────────────────────────────────────────────────────────────────┐
│                    CODE STRING                                       │
│  ──────────────────────────                                          │
│  code_string = '''                                                   │
│  class CalculatorToolComponent(LCToolComponent):                     │
│      display_name = "Calculator [DEPRECATED]"                        │
│      icon = "calculator"                                             │
│      ...                                                             │
│  '''                                                                 │
└────────────────────────────────────────────────────────────────────┘
                               │
                               ▼ STORED IN DATABASE
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE (JSON)                                   │
│  ──────────────────────────────                                      │
│  {                                                                   │
│    "nodes": [{                                                       │
│      "id": "Calculator-xyz123",                                      │
│      "data": {                                                       │
│        "node": {                                                     │
│          "template": {                                               │
│            "code": "class CalculatorToolComponent..."                │
│          }                                                           │
│        }                                                             │
│      }                                                               │
│    }]                                                                │
│  }                                                                   │
└────────────────────────────────────────────────────────────────────┘
                               │
                               ▼ AT RUNTIME
┌─────────────────────────────────────────────────────────────────────┐
│                    RUNTIME EXECUTION                                 │
│  ────────────────────────────                                        │
│                                                                      │
│  # eval_custom_component_code() is called:                          │
│  class_object = eval_custom_component_code(code_string)              │
│                                                                      │
│  # Now we have an actual Python class!                              │
│  instance = class_object()                                           │
│  instance.run_model()  # Executes!                                  │
└────────────────────────────────────────────────────────────────────┘
```

### Key Code Location: `eval.py`

```python
# File: langbuilder/custom/eval.py

def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code string and return the class."""
    # Extract class name from the code string
    class_name = validate.extract_class_name(code)  # "CalculatorToolComponent"
    
    # Create and return the actual Python class from string
    return validate.create_class(code, class_name)
    # Returns: <class 'CalculatorToolComponent'>
```

### Why This Architecture?

| Requirement | Why String Works |
|-------------|------------------|
| **Database Storage** | JSON can store strings, not Python objects |
| **Network Transfer** | HTTP APIs transmit text, not binary classes |
| **Version Control** | Flows can be exported/imported as JSON files |
| **User Custom Code** | Users can edit component code directly in the UI |
| **Hot Reloading** | Changes to code don't require server restart |

---

## 2. Template Folder Deep Dive {#template-folder-deep-dive}

### Folder Structure

```
template/
├── __init__.py
├── utils.py                    # Utility functions
├── field/                      # INPUT/OUTPUT DEFINITIONS
│   ├── __init__.py
│   ├── base.py                 # Input and Output classes
│   └── prompt.py
├── frontend_node/              # UI NODE REPRESENTATION
│   ├── __init__.py
│   ├── base.py                 # FrontendNode base class
│   ├── constants.py
│   └── custom_components.py    # Component-specific nodes
└── template/                   # TEMPLATE CONFIGURATION
    └── base.py                 # Template class
```

### File: `template/field/base.py` - Input/Output Definitions

This file defines HOW inputs and outputs are structured:

```python
class Input(BaseModel):
    """Defines an input field for a component."""
    
    field_type: str | type | None    # "str", "int", "file", etc.
    required: bool = False            # Is this input mandatory?
    placeholder: str = ""             # Placeholder text
    is_list: bool = False             # Can accept multiple values?
    show: bool = True                 # Visible in UI?
    multiline: bool = False           # Text editor for long text?
    value: Any = None                 # Default value
    file_types: list[str] = []        # Allowed file extensions
    password: bool = False            # Hide input (for API keys)?
    options: list[str] = None         # Dropdown options
    name: str = None                  # Internal name
    display_name: str = None          # UI label
    advanced: bool = False            # Hide in advanced section?
    input_types: list[str] = None     # Accepted connection types
    dynamic: bool = False             # Can change at runtime?
    info: str = ""                    # Tooltip text


class Output(BaseModel):
    """Defines an output field for a component."""
    
    types: list[str] = []            # Output data types
    selected: str = None              # Currently selected type
    name: str                         # Internal name
    hidden: bool = None               # Hidden from UI?
    display_name: str = None          # UI label
    method: str = None                # Method to call for output
    value: Any = UNDEFINED            # Output value
```

### File: `template/template/base.py` - Template Configuration

```python
class Template(BaseModel):
    """Container for all input fields of a component."""
    
    type_name: str                   # Component type name
    fields: list[InputTypes]         # List of all inputs
    
    def add_field(self, field: Input) -> None:
        """Add a new input field."""
        self.fields.append(field)
    
    def get_field(self, field_name: str) -> Input:
        """Get field by name."""
        return next(f for f in self.fields if f.name == field_name)
```

### Visual Example: How Template Maps to UI

```
Template Definition (Python)              UI Rendering (Frontend)
─────────────────────────────────────────────────────────────────────
Template(                                 ┌────────────────────────┐
  type_name="Calculator",                 │ 🔢 Calculator          │
  fields=[                                ├────────────────────────┤
    Input(                        ───►    │ Expression:            │
      name="expression",                  │ [4*4*(33/22)+12-20  ]  │
      display_name="Expression",          │                        │
      field_type="str",                   │ ℹ️ The arithmetic...   │
      info="The arithmetic..."            │                        │
    )                                     │ [▶ Run]                │
  ]                                       └────────────────────────┘
)
```

---

## 3. What is FrontendNode {#what-is-frontendnode}

### Definition

`FrontendNode` is the **complete JSON representation** of a component that gets sent to the frontend UI. It contains:
- All metadata (name, icon, description)
- All input fields (with their types, defaults, options)
- All output definitions
- Validation rules
- UI configuration

### File: `template/frontend_node/base.py`

```python
class FrontendNode(BaseModel):
    """Complete representation of a component for the frontend."""
    
    # METADATA
    name: str = ""                    # Internal name
    display_name: str = ""            # UI title
    description: str = None           # Component description
    icon: str = None                  # Icon name/emoji
    documentation: str = ""           # Link to docs
    
    # CATEGORIZATION
    base_classes: list[str]           # What types it can output
    output_types: list[str] = []      # Available output types
    
    # UI STATE
    minimized: bool = False           # Collapsed by default?
    pinned: bool = False              # Pinned to top?
    frozen: bool = False              # Prevent editing?
    beta: bool = False                # Show beta badge?
    legacy: bool = False              # Show deprecated badge?
    
    # FIELDS
    template: Template                # All input fields
    outputs: list[Output] = []        # All output fields
    
    # VALIDATION
    conditional_paths: list[str] = [] # For routers
    custom_fields: dict = {}          # Extra configuration
```

### How FrontendNode is Created

```
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: Component Code (Python file)                                │
│  ─────────────────────────────────────                               │
│                                                                      │
│  class ChatInput(ChatComponent):                                     │
│      display_name = "Chat Input"                                     │
│      description = "Get chat inputs..."                              │
│      icon = "MessagesSquare"                                         │
│      inputs = [                                                      │
│          MultilineInput(name="input_value", display_name="Input"),   │
│          BoolInput(name="should_store_message", value=True),         │
│      ]                                                               │
│      outputs = [                                                     │
│          Output(name="message", method="message_response"),          │
│      ]                                                               │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ CodeParser extracts metadata
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: Build Template                                              │
│  ──────────────────────                                              │
│                                                                      │
│  Template(                                                           │
│      type_name="ChatInput",                                          │
│      fields=[                                                        │
│          MultilineInput(name="input_value", ...),                    │
│          BoolInput(name="should_store_message", ...),                │
│      ]                                                               │
│  )                                                                   │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Wrap in FrontendNode
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3: FrontendNode (JSON sent to frontend)                        │
│  ────────────────────────────────────────────                        │
│                                                                      │
│  {                                                                   │
│    "ChatInput": {                                                    │
│      "display_name": "Chat Input",                                   │
│      "description": "Get chat inputs...",                            │
│      "icon": "MessagesSquare",                                       │
│      "template": {                                                   │
│        "_type": "ChatInput",                                         │
│        "input_value": {                                              │
│          "type": "str",                                              │
│          "display_name": "Input",                                    │
│          "multiline": true                                           │
│        },                                                            │
│        "should_store_message": {                                     │
│          "type": "bool",                                             │
│          "value": true                                               │
│        }                                                             │
│      },                                                              │
│      "outputs": [                                                    │
│        {"name": "message", "method": "message_response"}             │
│      ]                                                               │
│    }                                                                 │
│  }                                                                   │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Rendered in UI
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 4: Visual UI Component                                         │
│  ───────────────────────────                                         │
│                                                                      │
│  ┌────────────────────────────────────────┐                          │
│  │ 💬 Chat Input                          │                          │
│  │ ─────────────────────────────────────  │                          │
│  │ Get chat inputs from the Playground.   │                          │
│  │                                        │                          │
│  │ Input: [________________________]      │  ◄── input_value         │
│  │        [________________________]      │                          │
│  │                                        │                          │
│  │ ☑ Store Messages                       │  ◄── should_store_message│
│  │                                        │                          │
│  │                    ○ message ──────►   │  ◄── output handle       │
│  └────────────────────────────────────────┘                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Complete Flow Execution: Step by Step {#complete-flow-execution-step-by-step}

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE EXECUTION FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

     USER CLICKS "RUN" IN PLAYGROUND
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. FRONTEND                                                                 │
│     ─────────                                                                │
│     • Collects input values from UI                                          │
│     • Serializes flow graph to JSON                                          │
│     • POST /api/v1/build/{flow_id}/flow                                      │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼ HTTP Request with JSON payload
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. API ENDPOINT: chat.py                                                    │
│     ─────────────────────────                                                │
│     File: langbuilder/api/v1/chat.py                                        │
│     Function: build_flow()                                                   │
│                                                                              │
│     • Validates user authentication                                          │
│     • Creates job queue for async execution                                  │
│     • Calls start_flow_build()                                              │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. BUILD ORCHESTRATION: build.py                                            │
│     ──────────────────────────────                                           │
│     File: langbuilder/api/build.py                                          │
│     Function: start_flow_build() → generate_flow_events()                   │
│                                                                              │
│     • Creates EventManager for real-time updates                             │
│     • Calls create_graph() to build the execution graph                     │
│     • Determines vertex execution order                                      │
│     • Iterates through vertices, building each one                          │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. GRAPH CREATION: LangGraphAdapter                                         │
│     ────────────────────────────────                                         │
│     File: langbuilder/graph_langgraph/adapter.py                            │
│     Class: LangGraphAdapter                                                  │
│                                                                              │
│     • Parses JSON payload into vertex objects                                │
│     • Builds adjacency maps (predecessor/successor)                          │
│     • Detects cycles in the graph                                            │
│     • Creates LangGraph StateGraph workflow                                  │
│     • Compiles the workflow for execution                                    │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. VERTEX BUILDING (For each component)                                     │
│     ────────────────────────────────────                                     │
│     File: langbuilder/graph_langgraph/vertex_wrapper.py                     │
│     Class: LangGraphVertex                                                   │
│                                                                              │
│     a) Build parameters from edges and template                             │
│     b) Call instantiate_class() to create component instance                │
│     c) Execute the component's build method                                 │
│     d) Collect outputs and artifacts                                        │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. COMPONENT INSTANTIATION                                                  │
│     ──────────────────────────                                               │
│     File: langbuilder/interface/initialize/loading.py                       │
│     Function: instantiate_class()                                           │
│                                                                              │
│     • Gets code string from vertex params                                    │
│     • Calls eval_custom_component_code(code)                                │
│     • Creates component instance with parameters                             │
│     • Sets event manager, tracing service                                   │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. CODE EVALUATION                                                          │
│     ────────────────                                                         │
│     File: langbuilder/custom/eval.py                                        │
│     Function: eval_custom_component_code()                                  │
│                                                                              │
│     code_string = "class ChatInput(ChatComponent):..."                      │
│     class_name = "ChatInput"                                                 │
│     class_object = create_class(code_string, class_name)                    │
│     # Returns: <class 'ChatInput'>                                          │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  8. COMPONENT EXECUTION                                                      │
│     ────────────────────                                                     │
│     File: langbuilder/custom/custom_component/component.py                  │
│     Class: Component                                                         │
│                                                                              │
│     • Component.__init__() sets up inputs, outputs, parameters              │
│     • build_results() is called                                             │
│     • For each output, the corresponding method is invoked                  │
│       - e.g., ChatInput.message_response() returns Message                  │
│     • Results are collected and stored                                      │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  9. RESULT PROPAGATION                                                       │
│     ────────────────────                                                     │
│                                                                              │
│     • Output value is stored in vertex.built_result                         │
│     • Next vertices get this value as input parameter                       │
│     • Process repeats for all vertices in order                             │
│     • Events are sent to frontend in real-time                              │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  10. COMPLETION                                                              │
│      ──────────                                                              │
│                                                                              │
│     • All vertices built successfully                                        │
│     • Final output is collected                                              │
│     • Response sent back to frontend                                         │
│     • UI displays the result                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. LangGraph Integration {#langgraph-integration}

### What is LangGraph?

LangGraph is a library from LangChain for building stateful, multi-actor applications with LLMs. Langbuilder uses it as the execution engine.

### Folder Structure

```
graph_langgraph/
├── __init__.py
├── adapter.py           # Main adapter - converts Langbuilder graph to LangGraph
├── executor.py          # Executes the compiled workflow
├── nodes.py             # Node function creators
├── edges.py             # Edge function creators
├── state.py             # State definition (LangBuilderState)
├── vertex_wrapper.py    # Wraps Langbuilder vertices for LangGraph
├── runnable_vertices_manager.py
├── schema.py
├── streaming.py
└── utils.py
```

### How LangGraph Connects to Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH INTEGRATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  YOUR FLOW (Visual Graph)                                                    │
│  ────────────────────────                                                    │
│                                                                              │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐                        │
│  │ ChatInput │─────►│   LLM     │─────►│ChatOutput │                        │
│  └───────────┘      └───────────┘      └───────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼ LangGraphAdapter.from_payload()
┌─────────────────────────────────────────────────────────────────────────────┐
│  LANGGRAPH ADAPTER                                                           │
│  ─────────────────                                                           │
│  File: graph_langgraph/adapter.py                                           │
│                                                                              │
│  1. Parse JSON payload                                                       │
│  2. Create LangGraphVertex for each node                                    │
│  3. Build adjacency maps                                                    │
│  4. Detect cycles                                                           │
│  5. Create StateGraph workflow                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼ _build_langgraph_workflow()
┌─────────────────────────────────────────────────────────────────────────────┐
│  LANGGRAPH WORKFLOW (StateGraph)                                             │
│  ───────────────────────────────                                             │
│                                                                              │
│  from langgraph.graph import StateGraph                                     │
│                                                                              │
│  workflow = StateGraph(LangBuilderState)                                    │
│                                                                              │
│  # Add nodes (each wraps a Langbuilder component)                           │
│  workflow.add_node("ChatInput-abc", node_function_for_chatinput)            │
│  workflow.add_node("LLM-def", node_function_for_llm)                        │
│  workflow.add_node("ChatOutput-ghi", node_function_for_chatoutput)          │
│                                                                              │
│  # Add edges (connections between components)                               │
│  workflow.add_edge("ChatInput-abc", "LLM-def")                              │
│  workflow.add_edge("LLM-def", "ChatOutput-ghi")                             │
│                                                                              │
│  # Set entry point                                                          │
│  workflow.set_entry_point("ChatInput-abc")                                  │
│                                                                              │
│  # Compile                                                                  │
│  compiled_app = workflow.compile()                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼ Execute
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXECUTION                                                                   │
│  ─────────                                                                   │
│  File: graph_langgraph/executor.py                                          │
│                                                                              │
│  executor = LangGraphExecutor(adapter)                                      │
│  final_state = await executor.execute(inputs={"input_value": "Hello"})      │
│                                                                              │
│  # The workflow automatically:                                               │
│  # 1. Runs ChatInput with "Hello"                                           │
│  # 2. Passes Message to LLM                                                 │
│  # 3. Passes LLM response to ChatOutput                                     │
│  # 4. Returns final state with all results                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key File: `graph_langgraph/state.py`

```python
class LangBuilderState(TypedDict):
    """State that flows through the LangGraph workflow."""
    
    # Results storage
    vertices_results: dict[str, Any]      # Results from each vertex
    artifacts: dict[str, Any]              # Artifacts (files, etc.)
    outputs_logs: dict[str, Any]           # Output logs
    
    # Execution tracking
    current_vertex: str                    # Currently executing vertex
    completed_vertices: list[str]          # Completed vertex IDs
    events: list[dict]                     # Events for streaming
    
    # Flow metadata
    flow_id: str
    flow_name: str | None
    session_id: str
    user_id: str | None
```

---

## 6. Example 1: Simple Chat Flow (Without Tool) {#example-1-simple-chat-flow-without-tool}

### The Flow

```
┌───────────────┐       ┌───────────────────┐       ┌────────────────┐
│  Chat Input   │──────►│  Language Model   │──────►│  Chat Output   │
│               │       │    (OpenAI)       │       │                │
│ "Hello AI!"   │       │                   │       │ Display result │
└───────────────┘       └───────────────────┘       └────────────────┘
```

### Step-by-Step Execution

#### STEP 1: User clicks "Run" with input "Hello AI!"

```
Frontend sends POST /api/v1/build/{flow_id}/flow

Request Body:
{
  "inputs": {
    "input_value": "Hello AI!",
    "session": "session-123"
  },
  "data": {
    "nodes": [
      {
        "id": "ChatInput-abc123",
        "data": {
          "type": "ChatInput",
          "node": {
            "template": {
              "code": "class ChatInput(ChatComponent):\n    ...",
              "input_value": {"value": ""},
              "should_store_message": {"value": true}
            }
          }
        }
      },
      {
        "id": "LanguageModel-def456",
        "data": {
          "type": "LanguageModelComponent",
          "node": {
            "template": {
              "code": "class LanguageModelComponent(LCModelComponent):\n    ...",
              "provider": {"value": "OpenAI"},
              "model_name": {"value": "gpt-4o-mini"},
              "api_key": {"value": "sk-..."}
            }
          }
        }
      },
      {
        "id": "ChatOutput-ghi789",
        "data": {
          "type": "ChatOutput",
          "node": {
            "template": {
              "code": "class ChatOutput(ChatComponent):\n    ..."
            }
          }
        }
      }
    ],
    "edges": [
      {"source": "ChatInput-abc123", "target": "LanguageModel-def456", ...},
      {"source": "LanguageModel-def456", "target": "ChatOutput-ghi789", ...}
    ]
  }
}
```

#### STEP 2: API receives request

```python
# File: langbuilder/api/v1/chat.py

@router.post("/build/{flow_id}/flow")
async def build_flow(
    flow_id: uuid.UUID,
    inputs: InputValueRequest,
    data: FlowDataRequest,
    ...
):
    # Start the build process
    job_id = await start_flow_build(
        flow_id=flow_id,
        inputs=inputs,           # {"input_value": "Hello AI!"}
        data=data,               # The full flow graph
        ...
    )
    return {"job_id": job_id}
```

#### STEP 3: Graph is created from payload

```python
# File: langbuilder/api/build.py

async def create_graph(session, flow_id_str, flow_name):
    # Build graph using LangGraph adapter
    return await build_graph_from_data(
        flow_id=flow_id_str,
        payload=data.model_dump(),
        user_id=str(current_user.id),
        use_langgraph=True,  # Use LangGraph!
    )
```

```python
# File: langbuilder/graph_langgraph/adapter.py

@classmethod
def from_payload(cls, payload: dict, flow_id: str, ...):
    adapter = cls(flow_id=flow_id, ...)
    
    # Parse nodes and edges from JSON
    adapter.add_nodes_and_edges(
        nodes=payload["nodes"],      # [ChatInput, LLM, ChatOutput]
        edges=payload["edges"]       # Connections between them
    )
    
    return adapter
```

#### STEP 4: Vertices are sorted by execution order

```python
# The adapter determines: ChatInput → LLM → ChatOutput

in_degree_map = {
    "ChatInput-abc123": 0,      # No inputs, runs first
    "LanguageModel-def456": 1,  # Waits for ChatInput
    "ChatOutput-ghi789": 1      # Waits for LLM
}

first_layer = ["ChatInput-abc123"]  # Start here
```

#### STEP 5: Build ChatInput vertex

```python
# File: langbuilder/api/build.py

async def _build_vertex(vertex_id: str, graph: Graph, ...):
    vertex = graph.get_vertex(vertex_id)  # "ChatInput-abc123"
    
    vertex_build_result = await graph.build_vertex(
        vertex_id=vertex_id,
        user_id=user_id,
        inputs_dict={"input_value": "Hello AI!"},  # From request
        ...
    )
```

```python
# File: langbuilder/graph_langgraph/vertex_wrapper.py

async def _build(self, ...):
    # Get the code string from template
    code = self.params["code"]
    # "class ChatInput(ChatComponent):\n    display_name = 'Chat Input'..."
    
    # Create the actual Python class
    from langbuilder.interface.initialize import loading
    custom_component, custom_params = loading.instantiate_class(
        vertex=self,
        user_id=user_id,
    )
    # custom_component is now a ChatInput instance!
```

```python
# File: langbuilder/interface/initialize/loading.py

def instantiate_class(vertex, user_id=None, ...):
    # Get code string
    custom_params = get_params(vertex.params)
    code = custom_params.pop("code")
    
    # MAGIC: Convert string to class!
    class_object = eval_custom_component_code(code)
    # class_object = <class 'ChatInput'>
    
    # Create instance
    custom_component = class_object(
        _user_id=user_id,
        _parameters=custom_params,  # {"input_value": "Hello AI!"}
        _vertex=vertex,
        ...
    )
    
    return custom_component, custom_params
```

#### STEP 6: ChatInput.message_response() executes

```python
# File: langbuilder/components/input_output/chat.py

class ChatInput(ChatComponent):
    async def message_response(self) -> Message:
        # self.input_value = "Hello AI!" (from _parameters)
        
        message = await Message.create(
            text=self.input_value,        # "Hello AI!"
            sender=self.sender,            # "User"
            sender_name=self.sender_name,  # "User"
            session_id=self.session_id,
        )
        
        self.status = message
        return message

# OUTPUT: Message(text="Hello AI!", sender="User", ...)
```

#### STEP 7: Build LanguageModel vertex

```python
# The LLM vertex receives ChatInput's output as input

vertex_build_result = await graph.build_vertex(
    vertex_id="LanguageModel-def456",
    inputs_dict={
        "input_value": Message(text="Hello AI!", ...)  # From ChatInput!
    },
    ...
)
```

```python
# File: langbuilder/components/models/language_model.py

class LanguageModelComponent(LCModelComponent):
    def build_model(self) -> LanguageModel:
        # Create OpenAI model
        return ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.1,
            openai_api_key=self.api_key,
        )
    
    async def text_response(self) -> Message:
        model = self.build_model()
        
        # Call the LLM!
        result = await self.get_chat_result(
            runnable=model,
            stream=self.stream,
            input_value=self.input_value,  # Message from ChatInput
            system_message=self.system_message,
        )
        
        return result

# OUTPUT: Message(text="Hello! How can I help you today?", sender="AI", ...)
```

#### STEP 8: Build ChatOutput vertex

```python
# ChatOutput receives LLM's response

class ChatOutput(ChatComponent):
    async def message_response(self) -> Message:
        # self.input_value = Message from LLM
        
        text = self.convert_to_string()  # "Hello! How can I help you today?"
        
        message = await Message.create(
            text=text,
            sender="AI",
            sender_name="AI",
            ...
        )
        
        # Store in chat history
        stored_message = await self.send_message(message)
        
        return stored_message

# OUTPUT: Message displayed in UI!
```

#### STEP 9: Events sent to frontend

```python
# Events are streamed back to the frontend

# Event 1: ChatInput completed
{"event": "vertex_build_result", "data": {"id": "ChatInput-abc123", ...}}

# Event 2: LLM completed  
{"event": "vertex_build_result", "data": {"id": "LanguageModel-def456", ...}}

# Event 3: ChatOutput completed
{"event": "vertex_build_result", "data": {"id": "ChatOutput-ghi789", ...}}

# Event 4: Flow completed
{"event": "end", "data": {"final_output": "Hello! How can I help you today?"}}
```

---

## 7. Example 2: Calculator Tool Flow {#example-2-calculator-tool-flow}

### The Flow

```
┌───────────────┐       ┌───────────────────┐       ┌────────────────┐
│  Chat Input   │──────►│    Calculator     │──────►│  Chat Output   │
│               │       │                   │       │                │
│ "4*4+10-2"    │       │ Evaluates math    │       │ Display "24"   │
└───────────────┘       └───────────────────┘       └────────────────┘
```

### Calculator Component Code

```python
# File: langbuilder/components/tools/calculator.py

class CalculatorToolComponent(LCToolComponent):
    display_name = "Calculator [DEPRECATED]"
    description = "Perform basic arithmetic operations"
    icon = "calculator"
    name = "CalculatorTool"
    legacy = True

    inputs = [
        MessageTextInput(
            name="expression",
            display_name="Expression",
            info="The arithmetic expression to evaluate",
        ),
    ]

    def run_model(self) -> list[Data]:
        return self._evaluate_expression(self.expression)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="calculator",
            description="Evaluate basic arithmetic expressions",
            func=self._eval_expr_with_error,
            args_schema=self.CalculatorToolSchema,
        )

    def _evaluate_expression(self, expression: str) -> list[Data]:
        # Parse expression using AST (safe evaluation)
        tree = ast.parse(expression, mode="eval")
        result = self._eval_expr(tree.body)
        
        # Format result
        formatted_result = f"{result:.6f}".rstrip("0").rstrip(".")
        
        self.status = formatted_result
        return [Data(data={"result": formatted_result})]
```

### Step-by-Step Execution

#### STEP 1: Request with math expression

```
POST /api/v1/build/{flow_id}/flow

{
  "inputs": {
    "input_value": "4*4+10-2"
  },
  "data": {
    "nodes": [
      {"id": "ChatInput-abc", "data": {"type": "ChatInput", ...}},
      {"id": "Calculator-def", "data": {"type": "CalculatorToolComponent", ...}},
      {"id": "ChatOutput-ghi", "data": {"type": "ChatOutput", ...}}
    ],
    "edges": [
      {"source": "ChatInput-abc", "target": "Calculator-def", ...},
      {"source": "Calculator-def", "target": "ChatOutput-ghi", ...}
    ]
  }
}
```

#### STEP 2: ChatInput processes input

```python
# ChatInput receives "4*4+10-2"

async def message_response(self) -> Message:
    message = await Message.create(
        text="4*4+10-2",
        sender="User",
        ...
    )
    return message

# OUTPUT: Message(text="4*4+10-2", ...)
```

#### STEP 3: Calculator receives the expression

```python
# The Calculator vertex receives the expression

async def _build(self, ...):
    # Instantiate Calculator component
    code = self.params["code"]
    # "class CalculatorToolComponent(LCToolComponent):..."
    
    class_object = eval_custom_component_code(code)
    
    custom_component = class_object(
        _parameters={
            "expression": "4*4+10-2"  # From ChatInput's output!
        },
        ...
    )
```

#### STEP 4: Calculator evaluates expression

```python
# File: langbuilder/components/tools/calculator.py

def run_model(self) -> list[Data]:
    expression = self.expression  # "4*4+10-2"
    
    return self._evaluate_expression(expression)

def _evaluate_expression(self, expression: str) -> list[Data]:
    # Parse using Python's AST (Abstract Syntax Tree)
    tree = ast.parse(expression, mode="eval")
    
    # tree looks like:
    # Expression(
    #   body=BinOp(
    #     left=BinOp(
    #       left=BinOp(left=4, op=Mult, right=4),  # 4*4 = 16
    #       op=Add,
    #       right=10                                 # 16+10 = 26
    #     ),
    #     op=Sub,
    #     right=2                                    # 26-2 = 24
    #   )
    # )
    
    result = self._eval_expr(tree.body)  # 24.0
    
    formatted_result = "24"
    
    self.status = formatted_result
    return [Data(data={"result": "24"})]
```

#### STEP 5: AST Evaluation Detail

```python
def _eval_expr(self, node):
    # Operators mapping
    self.operators = {
        ast.Add: operator.add,      # +
        ast.Sub: operator.sub,      # -
        ast.Mult: operator.mul,     # *
        ast.Div: operator.truediv,  # /
        ast.Pow: operator.pow,      # **
    }
    
    if isinstance(node, ast.Num):
        # Base case: just a number
        return node.n
    
    if isinstance(node, ast.BinOp):
        # Recursive case: evaluate left and right
        left_val = self._eval_expr(node.left)    # e.g., 16
        right_val = self._eval_expr(node.right)  # e.g., 10
        
        # Apply operator
        op_func = self.operators[type(node.op)]  # operator.add
        return op_func(left_val, right_val)      # 16 + 10 = 26
```

```
EXPRESSION: "4*4+10-2"

AST TREE:                    EVALUATION:
─────────                    ──────────
    Sub(26, 2)               = 24
    ├── Add(16, 10)          = 26
    │   ├── Mult(4, 4)       = 16
    │   │   ├── 4
    │   │   └── 4
    │   └── 10
    └── 2

RESULT: 24
```

#### STEP 6: ChatOutput displays result

```python
# ChatOutput receives Data({"result": "24"})

async def message_response(self) -> Message:
    text = self.convert_to_string()  # "24"
    
    message = await Message.create(
        text=text,
        sender="AI",
        ...
    )
    
    return message

# FINAL OUTPUT: "24" displayed in the chat!
```

---

## 8. Complete Code Execution Trace {#complete-code-execution-trace}

### Sequence Diagram: Full Flow Execution

```
┌────────┐   ┌──────────┐   ┌──────────┐   ┌───────────────┐   ┌──────────┐   ┌───────────┐
│Frontend│   │ chat.py  │   │ build.py │   │LangGraphAdaptr│   │ Vertex   │   │ Component │
└───┬────┘   └────┬─────┘   └────┬─────┘   └──────┬────────┘   └────┬─────┘   └─────┬─────┘
    │             │              │                │                 │               │
    │ POST /build │              │                │                 │               │
    │────────────►│              │                │                 │               │
    │             │              │                │                 │               │
    │             │ start_flow   │                │                 │               │
    │             │─────────────►│                │                 │               │
    │             │              │                │                 │               │
    │             │              │ from_payload   │                 │               │
    │             │              │───────────────►│                 │               │
    │             │              │                │                 │               │
    │             │              │                │ add_nodes_edges │               │
    │             │              │                │────────────────►│               │
    │             │              │                │                 │               │
    │             │              │ sort_vertices  │                 │               │
    │             │              │───────────────►│                 │               │
    │             │              │                │                 │               │
    │             │              │                │◄────────────────│               │
    │             │              │                │ first_layer     │               │
    │             │              │                │                 │               │
    │             │              │ FOR EACH VERTEX IN ORDER:        │               │
    │             │              │ ─────────────────────────        │               │
    │             │              │                │                 │               │
    │             │              │ build_vertex   │                 │               │
    │             │              │───────────────►│                 │               │
    │             │              │                │                 │               │
    │             │              │                │ _build          │               │
    │             │              │                │────────────────►│               │
    │             │              │                │                 │               │
    │             │              │                │                 │instantiate    │
    │             │              │                │                 │──────────────►│
    │             │              │                │                 │               │
    │             │              │                │                 │  eval_code    │
    │             │              │                │                 │◄──────────────│
    │             │              │                │                 │               │
    │             │              │                │                 │ build_results │
    │             │              │                │                 │──────────────►│
    │             │              │                │                 │               │
    │             │              │                │                 │ method()      │
    │             │              │                │                 │◄──────────────│
    │             │              │                │                 │               │
    │             │              │                │◄────────────────│               │
    │             │              │                │ result          │               │
    │             │              │                │                 │               │
    │             │              │◄───────────────│                 │               │
    │             │              │ vertex_result  │                 │               │
    │             │              │                │                 │               │
    │ SSE event   │              │                │                 │               │
    │◄────────────│◄─────────────│                │                 │               │
    │             │              │                │                 │               │
    │             │              │ (repeat for    │                 │               │
    │             │              │  each vertex)  │                 │               │
    │             │              │                │                 │               │
    │ final result│              │                │                 │               │
    │◄────────────│◄─────────────│                │                 │               │
    │             │              │                │                 │               │
```

### File-by-File Execution Order

| Order | File | Function/Class | Input | Output |
|-------|------|----------------|-------|--------|
| 1 | `api/v1/chat.py` | `build_flow()` | HTTP Request, flow_id, inputs | job_id |
| 2 | `api/build.py` | `start_flow_build()` | job_id, inputs, data | Event Queue |
| 3 | `api/build.py` | `generate_flow_events()` | Event Manager | Events stream |
| 4 | `api/build.py` | `create_graph()` | session, flow_id | Graph/Adapter |
| 5 | `graph_langgraph/adapter.py` | `from_payload()` | JSON payload | LangGraphAdapter |
| 6 | `graph_langgraph/adapter.py` | `add_nodes_and_edges()` | nodes[], edges[] | Vertices built |
| 7 | `graph_langgraph/adapter.py` | `sort_vertices()` | - | first_layer[] |
| 8 | `api/build.py` | `_build_vertex()` | vertex_id | VertexBuildResponse |
| 9 | `graph_langgraph/vertex_wrapper.py` | `_build()` | params | built_result |
| 10 | `interface/initialize/loading.py` | `instantiate_class()` | vertex | Component instance |
| 11 | `custom/eval.py` | `eval_custom_component_code()` | code string | Class object |
| 12 | `custom/custom_component/component.py` | `Component.__init__()` | params | Instance |
| 13 | Component file (e.g., `chat.py`) | `message_response()` | self.input_value | Message |
| 14 | `graph_langgraph/vertex_wrapper.py` | `finalize_build()` | - | ResultData |
| 15 | `api/build.py` | Event emission | result | SSE to frontend |

---

## Summary: Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           LANGBUILDER ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐               │
│  │   COMPONENTS    │     │     CUSTOM      │     │    TEMPLATE     │               │
│  │    (Python)     │◄───►│   (Parsing)     │◄───►│   (UI Config)   │               │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘               │
│           │                       │                       │                         │
│           │    Code String        │    Metadata           │    FrontendNode        │
│           │    ────────────       │    ────────           │    ────────────        │
│           ▼                       ▼                       ▼                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                              DATABASE                                         │   │
│  │                           (Flow JSON)                                         │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                              │
│                                      ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           API LAYER                                           │   │
│  │                    (chat.py, build.py)                                        │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                              │
│                                      ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         GRAPH LAYER                                           │   │
│  │              (LangGraphAdapter, Vertex, Edge)                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                              │
│                                      ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      EXECUTION LAYER                                          │   │
│  │           (eval.py, loading.py, Component.build_results())                    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                              │
│                                      ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         LANGGRAPH                                             │   │
│  │              (StateGraph, Nodes, Edges, State)                                │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. When is Each Folder Used? (UI vs Runtime) {#when-is-each-folder-used}

### ⚠️ IMPORTANT CLARIFICATION

The `custom/` folder is used for **BOTH** UI display **AND** runtime execution - NOT just for UI!

### Complete Usage Table

| Folder/File | Used for UI? | Used at Runtime? | Purpose |
|-------------|--------------|------------------|---------|
| **custom/code_parser/** | ✅ YES | ❌ NO | Parse code to extract metadata for UI |
| **custom/directory_reader/** | ✅ YES | ❌ NO | Discover component files for menu |
| **custom/attributes.py** | ✅ YES | ❌ NO | Validate icons, names for UI |
| **custom/eval.py** | ❌ NO | ✅ YES | Convert code string → Python class |
| **custom/custom_component/component.py** | ❌ NO | ✅ YES | Base class - ALL components inherit this |
| **custom/custom_component/custom_component.py** | ❌ NO | ✅ YES | Flow control, tracing, storage |
| **custom/custom_component/base_component.py** | ✅ YES | ✅ YES | Code tree parsing + base functionality |
| **custom/utils.py** | ✅ YES | ✅ YES | Build templates + runtime utilities |
| **template/** | ✅ YES | ❌ NO | Define UI field structure |
| **template/frontend_node/** | ✅ YES | ❌ NO | JSON for frontend rendering |

### Visual Timeline: When Each Part is Used

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        TIMELINE: CUSTOM FOLDER USAGE                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════
                              APPLICATION STARTUP (UI PREPARATION)
═══════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Component Discovery (For UI Menu)                                          │
│  ──────────────────────────────────────────                                          │
│                                                                                      │
│  Files Used:                                                                         │
│  • custom/directory_reader/  → Scans folders, finds .py files                       │
│  • custom/code_parser/       → Parses code, extracts class info                     │
│  • custom/attributes.py      → Validates icons, display names                       │
│  • custom/utils.py           → Builds component templates                           │
│  • template/                 → Creates FrontendNode JSON                            │
│                                                                                      │
│  Output: Component menu in UI sidebar                                               │
│  ┌──────────────────┐                                                               │
│  │ 📦 Components    │                                                               │
│  │ ├─ 💬 Chat Input │                                                               │
│  │ ├─ 🧠 LLM        │                                                               │
│  │ ├─ 🔢 Calculator │                                                               │
│  │ └─ 💬 Chat Output│                                                               │
│  └──────────────────┘                                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════
                              USER DRAGS COMPONENT TO CANVAS
═══════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: Component Node Creation (UI Only)                                          │
│  ──────────────────────────────────────────                                          │
│                                                                                      │
│  Files Used:                                                                         │
│  • template/frontend_node/   → FrontendNode defines what UI shows                   │
│  • template/field/           → Input/Output definitions                             │
│                                                                                      │
│  Output: Visual component on canvas                                                 │
│  ┌────────────────────────────┐                                                     │
│  │ 🔢 Calculator              │                                                     │
│  │ ──────────────────────     │                                                     │
│  │ Expression: [__________]   │  ← From template/field/base.py Input               │
│  │         ○ result ─────────►│  ← From template/field/base.py Output              │
│  └────────────────────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════
                              USER CLICKS "RUN" (RUNTIME EXECUTION)
═══════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: Flow Execution (Runtime - custom/ IS NEEDED!)                              │
│  ──────────────────────────────────────────────────────                              │
│                                                                                      │
│  Files Used:                                                                         │
│  • custom/eval.py                        → Converts code string to Python class     │
│  • custom/custom_component/component.py  → Base class for ALL components            │
│  • custom/custom_component/custom_component.py → Tracing, flow control             │
│  • custom/custom_component/base_component.py   → Code parsing at runtime           │
│                                                                                      │
│  What Happens:                                                                       │
│                                                                                      │
│  1. API receives flow JSON (with code as STRING)                                    │
│     {                                                                               │
│       "template": {                                                                 │
│         "code": "class CalculatorToolComponent(LCToolComponent):..."               │
│       }                                                                             │
│     }                                                                               │
│                                                                                      │
│  2. eval.py converts string → class                                                 │
│     class_object = eval_custom_component_code(code_string)                          │
│     # Returns: <class 'CalculatorToolComponent'>                                    │
│                                                                                      │
│  3. Component instance is created (inherits from custom/custom_component/component.py)
│     instance = class_object(_parameters={"expression": "4+5"})                      │
│                                                                                      │
│  4. Component method executes                                                       │
│     result = instance.run_model()  # Returns Data({"result": "9"})                 │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Why Component.py is CRITICAL at Runtime

Every component you create inherits from `Component`:

```python
# Your Calculator component
class CalculatorToolComponent(LCToolComponent):  # LCToolComponent extends Component!
    ...

# Inheritance chain at RUNTIME:
CalculatorToolComponent
    └── LCToolComponent
        └── Component              # ← FROM custom/custom_component/component.py
            └── CustomComponent    # ← FROM custom/custom_component/custom_component.py
                └── BaseComponent  # ← FROM custom/custom_component/base_component.py
```

**At runtime, your component USES these base class features:**

| Base Class Feature | What It Does at Runtime |
|-------------------|------------------------|
| `Component._parameters` | Stores input values (e.g., `{"expression": "4+5"}`) |
| `Component.set_attributes()` | Makes `self.expression` work |
| `Component._outputs_map` | Manages output values |
| `Component.build_results()` | Orchestrates method calls |
| `CustomComponent.status` | Sets status shown in UI |
| `CustomComponent._tracing_service` | Logs execution for debugging |
| `CustomComponent.graph` | Access to flow graph |
| `BaseComponent.cache` | Caches expensive operations |

### Summary: custom/ Folder is Used TWICE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   STARTUP/UI TIME                         RUNTIME/EXECUTION TIME             │
│   ────────────────                        ──────────────────────             │
│                                                                              │
│   ┌──────────────────┐                    ┌──────────────────┐              │
│   │  code_parser/    │                    │     eval.py      │              │
│   │  directory_reader│                    │                  │              │
│   │  attributes.py   │                    │  Converts code   │              │
│   │                  │                    │  string → class  │              │
│   │  Extracts info   │                    └────────┬─────────┘              │
│   │  for UI display  │                             │                        │
│   └────────┬─────────┘                             ▼                        │
│            │                              ┌──────────────────┐              │
│            ▼                              │   component.py   │              │
│   ┌──────────────────┐                    │ custom_component │              │
│   │ template/        │                    │ base_component   │              │
│   │ frontend_node/   │                    │                  │              │
│   │                  │                    │  BASE CLASSES    │              │
│   │ Creates JSON for │                    │  for execution   │              │
│   │ frontend UI      │                    └────────┬─────────┘              │
│   └────────┬─────────┘                             │                        │
│            │                                       ▼                        │
│            ▼                              ┌──────────────────┐              │
│   ┌──────────────────┐                    │  Your Component  │              │
│   │  UI Component    │                    │  Actually Runs!  │              │
│   │  ┌────────────┐  │                    │                  │              │
│   │  │ 🔢 Calc    │  │                    │  result = calc.  │              │
│   │  │ [4+5___]   │  │                    │    run_model()   │              │
│   │  └────────────┘  │                    │  # Returns "9"   │              │
│   └──────────────────┘                    └──────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Detailed Examples: UI Loading vs Runtime Execution {#detailed-examples-ui-vs-runtime}

### Example A: Calculator Component - Complete Lifecycle

Let's trace a Calculator component from the moment the app starts to when it executes.

#### PHASE 1: Application Startup (UI Loading)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    STARTUP: Building Component Menu for UI                           │
└─────────────────────────────────────────────────────────────────────────────────────┘

STEP 1: DirectoryReader scans component folders
════════════════════════════════════════════════

File: custom/directory_reader/directory_reader.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ DirectoryReader.get_all_components()                                                  │
│                                                                                       │
│ • Scans: langbuilder/components/tools/                                               │
│ • Finds: calculator.py                                                               │
│ • Returns: {"path": "langbuilder/components/tools/calculator.py", "code": "..."}    │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 2: CodeParser extracts metadata from the Python file
════════════════════════════════════════════════════════

File: custom/code_parser/code_parser.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ CodeParser.parse_code(calculator_code_string)                                         │
│                                                                                       │
│ Input Code:                                                                           │
│ ┌──────────────────────────────────────────────────────────────────────────────────┐ │
│ │ class CalculatorToolComponent(LCToolComponent):                                   │ │
│ │     display_name = "Calculator [DEPRECATED]"                                      │ │
│ │     description = "Perform basic arithmetic operations"                           │ │
│ │     icon = "calculator"                                                           │ │
│ │     name = "CalculatorTool"                                                       │ │
│ │     legacy = True                                                                 │ │
│ │                                                                                   │ │
│ │     inputs = [                                                                    │ │
│ │         MessageTextInput(                                                         │ │
│ │             name="expression",                                                    │ │
│ │             display_name="Expression",                                            │ │
│ │             info="The arithmetic expression to evaluate",                         │ │
│ │         ),                                                                        │ │
│ │     ]                                                                             │ │
│ └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                       │
│ Uses AST to extract:                                                                  │
│ • Class Name: "CalculatorToolComponent"                                              │
│ • Base Classes: ["LCToolComponent"]                                                  │
│ • display_name: "Calculator [DEPRECATED]"                                            │
│ • icon: "calculator"                                                                 │
│ • inputs: [{name: "expression", display_name: "Expression", ...}]                   │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 3: attributes.py validates component attributes
═══════════════════════════════════════════════════

File: custom/attributes.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ validate_icon("calculator")         → ✅ Valid icon name                             │
│ validate_display_name("Calculator") → ✅ Valid display name                          │
│ validate_component_type()           → "tools" (folder-based category)               │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 4: utils.py builds the component template
═════════════════════════════════════════════

File: custom/utils.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ build_component_template(metadata)                                                    │
│                                                                                       │
│ Creates Template object:                                                              │
│ Template(                                                                             │
│     type_name="CalculatorToolComponent",                                             │
│     fields=[                                                                          │
│         Input(name="expression", display_name="Expression", type="str", ...),        │
│         Input(name="code", type="code", value="class CalculatorToolComponent..."),   │
│     ]                                                                                 │
│ )                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 5: FrontendNode is created for UI
═════════════════════════════════════

File: template/frontend_node/base.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ FrontendNode (JSON sent to React frontend)                                            │
│                                                                                       │
│ {                                                                                     │
│   "CalculatorToolComponent": {                                                        │
│     "display_name": "Calculator [DEPRECATED]",                                        │
│     "description": "Perform basic arithmetic operations",                             │
│     "icon": "calculator",                                                             │
│     "legacy": true,                                                                   │
│     "base_classes": ["Tool", "Data"],                                                │
│     "template": {                                                                     │
│       "_type": "CalculatorToolComponent",                                            │
│       "expression": {                                                                 │
│         "type": "str",                                                                │
│         "display_name": "Expression",                                                 │
│         "info": "The arithmetic expression to evaluate"                              │
│       },                                                                              │
│       "code": {                                                                       │
│         "type": "code",                                                               │
│         "value": "class CalculatorToolComponent(LCToolComponent):..."                │
│       }                                                                               │
│     }                                                                                 │
│   }                                                                                   │
│ }                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

RESULT: UI displays calculator in sidebar menu
═════════════════════════════════════════════

┌────────────────────┐
│ 📦 Components      │
│ ├─ 💬 Inputs       │
│ ├─ 🧠 Models       │
│ ├─ 🔧 Tools        │
│ │   ├─ 🔢 Calculator [DEPRECATED] ◄── THIS IS SHOWN!
│ │   ├─ 🔍 Search   │
│ │   └─ 📁 File     │
│ └─ 💬 Outputs      │
└────────────────────┘
```

#### PHASE 2: User Drags Calculator to Canvas (Still UI)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    USER DRAGS CALCULATOR TO CANVAS                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘

Frontend receives FrontendNode JSON and renders:

┌────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  ┌─────────────────────────────────────────────────────┐                           │
│  │ 🔢 Calculator [DEPRECATED]                          │                           │
│  │ ─────────────────────────────────────────────────── │                           │
│  │ ⚠️ This component is deprecated                      │                           │
│  │                                                      │                           │
│  │ Expression:                                          │                           │
│  │ ┌──────────────────────────────────────────────────┐│                           │
│  │ │ 4*4*(33/22)+12-20                                ││ ◄─ User types expression │
│  │ └──────────────────────────────────────────────────┘│                           │
│  │ ℹ️ The arithmetic expression to evaluate            │                           │
│  │                                                      │                           │
│  │                              ○ Tool Output ─────────►│ ◄─ Output handle         │
│  │                              ○ Data Output ─────────►│                           │
│  └─────────────────────────────────────────────────────┘                           │
│                                                                                     │
└────────────────────────────────────────────────────────────────────────────────────┘

FILES USED (UI Only):
• template/frontend_node/base.py → Defines component structure
• template/field/base.py         → Defines Input/Output fields
• template/template/base.py      → Container for all fields

FILES NOT USED YET:
• custom/eval.py                        → Will be used at runtime
• custom/custom_component/component.py  → Will be used at runtime
```

#### PHASE 3: User Clicks "Run" (Runtime Execution)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    USER CLICKS "RUN" - RUNTIME BEGINS                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

STEP 1: API receives request with code as STRING
════════════════════════════════════════════════

POST /api/v1/build/{flow_id}/flow
{
  "inputs": {"expression": "4*4*(33/22)+12-20"},
  "data": {
    "nodes": [{
      "id": "Calculator-xyz123",
      "data": {
        "type": "CalculatorToolComponent",
        "node": {
          "template": {
            "code": "class CalculatorToolComponent(LCToolComponent):\n    display_name = ...",
            "expression": {"value": "4*4*(33/22)+12-20"}
          }
        }
      }
    }]
  }
}

STEP 2: eval.py converts code string to Python class
═══════════════════════════════════════════════════

File: custom/eval.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ eval_custom_component_code(code_string)                                               │
│                                                                                       │
│ Input: "class CalculatorToolComponent(LCToolComponent):\n    display_name = ..."     │
│                                                                                       │
│ Process:                                                                              │
│ 1. Extract class name: "CalculatorToolComponent"                                     │
│ 2. Create Python module namespace                                                     │
│ 3. Execute code string in namespace                                                   │
│ 4. Return class object                                                                │
│                                                                                       │
│ Output: <class 'CalculatorToolComponent'>  (actual Python class!)                    │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 3: loading.py instantiates the component
════════════════════════════════════════════

File: interface/initialize/loading.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ instantiate_class(vertex, user_id, event_manager)                                     │
│                                                                                       │
│ # Get code string and convert to class                                               │
│ code = custom_params.pop("code")                                                      │
│ class_object = eval_custom_component_code(code)                                       │
│                                                                                       │
│ # Create instance (THIS IS WHERE custom_component/ IS USED!)                         │
│ custom_component = class_object(                                                      │
│     _user_id=user_id,                                                                 │
│     _parameters={"expression": "4*4*(33/22)+12-20"},                                 │
│     _vertex=vertex,                                                                   │
│     _tracing_service=get_tracing_service(),  ◄── TRACING INJECTED HERE              │
│     _id=vertex.id,                                                                    │
│ )                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 4: Component inherits from custom/custom_component/component.py
═══════════════════════════════════════════════════════════════════

File: custom/custom_component/component.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ INHERITANCE CHAIN (ALL FROM custom/ FOLDER!)                                          │
│                                                                                       │
│ CalculatorToolComponent                                                               │
│     │                                                                                 │
│     └── LCToolComponent                                                               │
│             │                                                                         │
│             └── Component  ◄── custom/custom_component/component.py                  │
│                     │                                                                 │
│                     └── CustomComponent  ◄── custom/custom_component/custom_component.py
│                             │                                                         │
│                             └── BaseComponent  ◄── custom/custom_component/base_component.py
│                                                                                       │
│ Component.__init__() does:                                                            │
│ • self._parameters = {"expression": "4*4*(33/22)+12-20"}                             │
│ • self.set_attributes(self._parameters)  # Makes self.expression work               │
│ • self._tracing_service = tracing_service  # For logging                            │
│ • self._outputs_map = {}  # For results                                             │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 5: Component.build_results() executes with tracing
═══════════════════════════════════════════════════════

File: custom/custom_component/component.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ async def build_results(self):                                                        │
│     if self._tracing_service:                                                         │
│         return await self._build_with_tracing()                                       │
│     return await self._build_without_tracing()                                        │
│                                                                                       │
│ async def _build_with_tracing(self):                                                  │
│     inputs = self.get_trace_as_inputs()  # {"expression": "4*4*(33/22)+12-20"}       │
│     metadata = self.get_trace_as_metadata()                                           │
│                                                                                       │
│     # START TRACE (sent to Langfuse!)                                                 │
│     async with self._tracing_service.trace_component(self, self.trace_name, inputs): │
│         # EXECUTE COMPONENT                                                           │
│         results, artifacts = await self._build_results()                             │
│         # LOG OUTPUTS (sent to Langfuse!)                                             │
│         self._tracing_service.set_outputs(self.trace_name, results)                  │
│                                                                                       │
│     return results, artifacts                                                         │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 6: Calculator._evaluate_expression() runs
═════════════════════════════════════════════

File: components/tools/calculator.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ def run_model(self) -> list[Data]:                                                    │
│     return self._evaluate_expression(self.expression)  # "4*4*(33/22)+12-20"         │
│                                                                                       │
│ def _evaluate_expression(self, expression: str):                                      │
│     tree = ast.parse(expression, mode="eval")  # Parse to AST                        │
│     result = self._eval_expr(tree.body)         # Evaluate: 16*1.5+12-20 = 16       │
│                                                                                       │
│     formatted_result = "16"                                                           │
│     self.status = formatted_result              # Sets UI status                     │
│     return [Data(data={"result": "16"})]        # Returns result                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

RESULT: "16" flows to next component and displays in UI
```

### Example B: ChatInput → LLM → ChatOutput - Full Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│              EXAMPLE B: COMPLETE CHAT FLOW LIFECYCLE                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════
                              UI LOADING TIME
═══════════════════════════════════════════════════════════════════════════════════════

FILES USED:                           PURPOSE:
─────────────────────────────────────────────────────────────────────────────────────
custom/directory_reader/              Finds chat.py in components/input_output/
custom/code_parser/                   Extracts: ChatInput, ChatOutput classes
custom/attributes.py                  Validates icons, display names
custom/utils.py                       Builds templates for each component
template/field/base.py                Defines MultilineInput, BoolInput, etc.
template/frontend_node/base.py        Creates FrontendNode JSON
template/template/base.py             Wraps all inputs in Template

RESULT:
┌────────────────────┐
│ 📦 Components      │
│ ├─ 💬 Inputs       │
│ │   └─ 💬 Chat Input ◄── Shown in menu
│ ├─ 🧠 Models       │
│ │   └─ 🤖 Language Model ◄── Shown in menu
│ └─ 💬 Outputs      │
│     └─ 💬 Chat Output ◄── Shown in menu
└────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════
                              RUNTIME EXECUTION
═══════════════════════════════════════════════════════════════════════════════════════

FILES USED:                           PURPOSE:
─────────────────────────────────────────────────────────────────────────────────────
custom/eval.py                        Converts code strings → Python classes
custom/custom_component/component.py   Provides Component base class
custom/custom_component/custom_component.py  Provides tracing, flow control
custom/custom_component/base_component.py    Provides cache, code parsing
interface/initialize/loading.py       Instantiates components with parameters
services/tracing/service.py           TracingService for Langfuse
services/tracing/langfuse.py          LangFuseTracer implementation

EXECUTION TRACE:
─────────────────

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ChatInput     │────►│  LanguageModel  │────►│   ChatOutput    │
│   "Hello!"      │     │   OpenAI GPT    │     │   Display       │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    eval.py converts        eval.py converts        eval.py converts
    code → class            code → class            code → class
         │                       │                       │
         ▼                       ▼                       ▼
    Component.__init__      Component.__init__      Component.__init__
    inherits from           inherits from           inherits from
    custom_component/       custom_component/       custom_component/
         │                       │                       │
         ▼                       ▼                       ▼
    build_results()         build_results()         build_results()
    with tracing            with tracing            with tracing
         │                       │                       │
         ▼                       ▼                       ▼
    message_response()      text_response()         message_response()
    returns Message         calls OpenAI API        stores & displays
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                                 ▼
                    All traced to Langfuse!
```

---

## 11. Tracing with Langfuse: Complete Integration {#tracing-with-langfuse}

### What is Langfuse?

Langfuse is an open-source LLM engineering platform for:
- **Tracing**: See every step of your LLM application
- **Debugging**: Find where errors occur
- **Analytics**: Track latency, cost, and quality
- **Evaluation**: Score your LLM outputs

### How Langbuilder Integrates with Langfuse

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    LANGFUSE INTEGRATION ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘

                    LANGBUILDER                              LANGFUSE
                    ───────────                              ────────

┌──────────────────────────────────┐       ┌──────────────────────────────────┐
│    services/tracing/service.py   │       │                                   │
│    ─────────────────────────────  │       │         LANGFUSE SERVER          │
│                                   │       │                                   │
│    TracingService                 │       │    ┌────────────────────────┐    │
│    ├── start_tracers()           │◄──────┼────│   Trace: Flow-ABC123   │    │
│    ├── trace_component()         │       │    │   ├── Span: ChatInput  │    │
│    ├── set_outputs()             │       │    │   │   └── inputs/outputs│    │
│    └── end_tracers()             │       │    │   ├── Span: LLM        │    │
│         │                        │       │    │   │   └── inputs/outputs│    │
│         ▼                        │       │    │   └── Span: ChatOutput │    │
│    services/tracing/langfuse.py  │       │    │       └── inputs/outputs│    │
│    ─────────────────────────────  │       │    └────────────────────────┘    │
│                                   │       │                                   │
│    LangFuseTracer                │───────┼───►  API Calls:                   │
│    ├── setup_langfuse()          │       │       • trace.span()              │
│    ├── add_trace()               │       │       • span.update()             │
│    ├── end_trace()               │       │       • trace.update()            │
│    └── get_langchain_callback()  │       │                                   │
│                                   │       │    Dashboard:                     │
└──────────────────────────────────┘       │    • View traces                  │
                                           │    • Analyze costs                │
                                           │    • Debug errors                 │
                                           └──────────────────────────────────┘
```

### Key Files for Tracing

| File | Purpose |
|------|---------|
| `services/tracing/service.py` | Main TracingService - orchestrates all tracers |
| `services/tracing/langfuse.py` | LangFuseTracer - Langfuse-specific implementation |
| `services/tracing/base.py` | BaseTracer - Abstract interface for all tracers |
| `services/tracing/factory.py` | Creates TracingService instances |
| `services/deps.py` | Dependency injection for TracingService |

### How custom/ Folder Enables Tracing

The `custom/custom_component/` folder is **CRITICAL** for tracing because:

```python
# File: custom/custom_component/custom_component.py

class CustomComponent(BaseComponent):
    def __init__(self, ...):
        # TRACING SERVICE IS STORED HERE!
        self._tracing_service: TracingService | None = None
    
    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        """Get callbacks to pass to LangChain for automatic tracing."""
        if self._tracing_service:
            return self._tracing_service.get_langchain_callbacks()
        return []

# File: custom/custom_component/component.py

class Component(CustomComponent):
    async def build_results(self):
        """Build results WITH tracing if available."""
        if self._tracing_service:
            return await self._build_with_tracing()  # ◄── TRACES EVERYTHING!
        return await self._build_without_tracing()

    async def _build_with_tracing(self):
        inputs = self.get_trace_as_inputs()
        metadata = self.get_trace_as_metadata()
        
        # THIS IS WHERE TRACING HAPPENS!
        async with self._tracing_service.trace_component(self, self.trace_name, inputs, metadata):
            results, artifacts = await self._build_results()
            self._tracing_service.set_outputs(self.trace_name, results)
        
        return results, artifacts
```

### Complete Tracing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    TRACING FLOW: USER RUNS A CHAT                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘

STEP 1: Flow execution starts
═════════════════════════════

File: api/build.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ async def start_flow_build(...):                                                      │
│     tracing_service = get_tracing_service()                                           │
│                                                                                       │
│     # START MAIN TRACE (Flow-level)                                                   │
│     await tracing_service.start_tracers(                                              │
│         run_id=flow_id,                                                               │
│         run_name=f"Flow - {flow_id}",                                                │
│         user_id=user_id,                                                              │
│         session_id=session_id,                                                        │
│     )                                                                                 │
│     # This creates a trace in Langfuse!                                               │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Langfuse receives:
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Langfuse Trace Created:                                                               │
│ {                                                                                     │
│   "id": "flow-abc123",                                                                │
│   "name": "Flow - abc123",                                                            │
│   "user_id": "user-456",                                                              │
│   "session_id": "session-789"                                                         │
│ }                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 2: Each component is traced
════════════════════════════════

File: interface/initialize/loading.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ def instantiate_class(vertex, ...):                                                   │
│     custom_component = class_object(                                                  │
│         ...                                                                           │
│         _tracing_service=get_tracing_service(),  ◄── TRACING INJECTED!              │
│     )                                                                                 │
└──────────────────────────────────────────────────────────────────────────────────────┘

File: custom/custom_component/component.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ async def _build_with_tracing(self):                                                  │
│     inputs = {"input_value": "Hello!"}                                                │
│                                                                                       │
│     async with self._tracing_service.trace_component(                                │
│         self,                                                                         │
│         self.trace_name,  # "ChatInput (ChatInput-abc123)"                           │
│         inputs,                                                                       │
│         metadata                                                                      │
│     ):                                                                                │
│         # SPAN START ─────────────────────────────────────────────────────────►      │
│                                                                                       │
│         results, artifacts = await self._build_results()                             │
│         # Component executes here...                                                 │
│                                                                                       │
│         self._tracing_service.set_outputs(self.trace_name, results)                  │
│         # SPAN END ───────────────────────────────────────────────────────────►      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Langfuse receives:
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Langfuse Span Created:                                                                │
│ {                                                                                     │
│   "name": "ChatInput",                                                                │
│   "input": {"input_value": "Hello!"},                                                │
│   "output": {"message": {"text": "Hello!", "sender": "User"}},                       │
│   "start_time": "2024-01-15T10:00:00Z",                                              │
│   "end_time": "2024-01-15T10:00:00.050Z",                                            │
│   "metadata": {"component_id": "ChatInput-abc123", "trace_type": "chat"}             │
│ }                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 3: LLM calls are automatically traced
═════════════════════════════════════════

File: components/models/language_model.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ async def text_response(self) -> Message:                                             │
│     model = self.build_model()  # Creates ChatOpenAI                                  │
│                                                                                       │
│     # GET LANGCHAIN CALLBACKS FOR AUTOMATIC LLM TRACING!                             │
│     callbacks = self.get_langchain_callbacks()                                        │
│     # callbacks = [LangfuseCallbackWrapper(...)]                                     │
│                                                                                       │
│     result = await self.get_chat_result(                                             │
│         runnable=model,                                                               │
│         callbacks=callbacks,  ◄── PASSES LANGFUSE CALLBACK TO LANGCHAIN             │
│         ...                                                                           │
│     )                                                                                 │
│                                                                                       │
│     # LangChain automatically traces:                                                 │
│     # - LLM call (prompt, model, tokens)                                             │
│     # - Response (completion, latency)                                               │
│     # - Cost (token count × price)                                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Langfuse receives:
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Langfuse LLM Span (automatic via LangChain callback):                                 │
│ {                                                                                     │
│   "name": "ChatOpenAI",                                                               │
│   "input": {                                                                          │
│     "messages": [{"role": "user", "content": "Hello!"}]                              │
│   },                                                                                  │
│   "output": {                                                                         │
│     "content": "Hello! How can I help you today?"                                    │
│   },                                                                                  │
│   "model": "gpt-4o-mini",                                                            │
│   "usage": {                                                                          │
│     "prompt_tokens": 10,                                                              │
│     "completion_tokens": 8,                                                           │
│     "total_tokens": 18                                                                │
│   },                                                                                  │
│   "latency_ms": 450                                                                   │
│ }                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

STEP 4: Flow ends, trace is finalized
═════════════════════════════════════

File: api/build.py

┌──────────────────────────────────────────────────────────────────────────────────────┐
│ async def end_flow_build(...):                                                        │
│     await tracing_service.end_tracers(                                                │
│         outputs=final_outputs,                                                        │
│         error=error_if_any                                                            │
│     )                                                                                 │
│     # Finalizes trace in Langfuse                                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### What You See in Langfuse Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         LANGFUSE DASHBOARD                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  Trace: Flow - abc123                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  User: user-456 | Session: session-789 | Duration: 1.2s | Total Cost: $0.003        │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │ ▼ ChatInput (50ms)                                                              │ │
│  │   ├─ Input: {"input_value": "Hello!"}                                          │ │
│  │   └─ Output: {"message": {"text": "Hello!", "sender": "User"}}                 │ │
│  │                                                                                 │ │
│  │ ▼ LanguageModel (450ms) 💰 $0.003                                               │ │
│  │   ├─ Input: {"messages": [{"role": "user", "content": "Hello!"}]}              │ │
│  │   ├─ ▼ ChatOpenAI                                                              │ │
│  │   │   ├─ Model: gpt-4o-mini                                                    │ │
│  │   │   ├─ Tokens: 10 prompt + 8 completion = 18 total                           │ │
│  │   │   └─ Response: "Hello! How can I help you today?"                          │ │
│  │   └─ Output: {"message": {"text": "Hello! How can..."}}                        │ │
│  │                                                                                 │ │
│  │ ▼ ChatOutput (30ms)                                                             │ │
│  │   ├─ Input: {"input_value": Message(...)}                                      │ │
│  │   └─ Output: {"message": {"text": "Hello! How can...", "stored": true}}        │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Langfuse Configuration

To enable Langfuse tracing, set these environment variables:

```bash
# Required for Langfuse
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com  # or your self-hosted URL

# Optional: Disable tracing
DEACTIVATE_TRACING=false  # Set to true to disable all tracing
```

### Summary: How custom/ Folder Enables Tracing

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│              CUSTOM FOLDER'S ROLE IN TRACING                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘

custom/
├── custom_component/
│   ├── base_component.py      ─── Provides base caching functionality
│   │
│   ├── custom_component.py    ─── TRACING STORAGE
│   │   │                          • self._tracing_service: TracingService
│   │   │                          • get_langchain_callbacks() → Returns Langfuse callbacks
│   │   │
│   │   └── Component inherits from here!
│   │
│   └── component.py           ─── TRACING EXECUTION
│       │                          • build_results() → Decides trace vs no-trace
│       │                          • _build_with_tracing() → Wraps execution in trace
│       │                          • get_trace_as_inputs() → Extracts traceable inputs
│       │                          • get_trace_as_metadata() → Extracts metadata
│       │
│       └── YOUR COMPONENT inherits from Component!
│
└── eval.py                    ─── Creates component instance that has tracing!


WITHOUT custom/ folder:
  ❌ No _tracing_service attribute
  ❌ No build_results() tracing wrapper
  ❌ No get_langchain_callbacks()
  ❌ No tracing to Langfuse!

WITH custom/ folder:
  ✅ TracingService injected at instantiation
  ✅ Every component execution is traced
  ✅ LLM calls automatically traced via callbacks
  ✅ Full visibility in Langfuse dashboard!
```

---

## Key Takeaways

1. **Code as String**: Components are stored as code strings because Python classes can't be directly serialized to JSON or transmitted over HTTP.

2. **Template Folder**: Defines the structure of inputs/outputs and how they appear in the UI (FrontendNode). **Used only for UI**.

3. **FrontendNode**: The complete JSON representation of a component sent to the frontend, containing all metadata, inputs, outputs, and UI configuration.

4. **Custom Folder - DUAL PURPOSE**:
   - **UI Time**: `code_parser/`, `directory_reader/`, `attributes.py` parse code for menu display
   - **Runtime**: `eval.py` converts code string → class, `component.py` provides base class functionality AND tracing!

5. **Tracing with Langfuse**:
   - TracingService is injected into every component via `loading.py`
   - `custom_component.py` stores `_tracing_service` and provides `get_langchain_callbacks()`
   - `component.py` wraps execution in `trace_component()` context manager
   - LangChain callbacks automatically trace LLM calls

6. **LangGraph Integration**: Langbuilder uses LangGraph (from LangChain) as its execution engine, converting the visual flow into a StateGraph workflow.

7. **Execution Flow**: 
   - API receives request → Graph is created → Vertices are sorted → Each vertex is built → **`eval.py` converts code string to class** → **Component instance created (inherits from `component.py` with tracing!)** → Component method is called → Results flow to next vertex → **All traced to Langfuse!**

8. **Two Detailed Examples**:
   - **Calculator**: Shows UI loading (code_parser, attributes) vs Runtime (eval, component)
   - **Chat Flow**: Shows complete lifecycle with tracing at every step
