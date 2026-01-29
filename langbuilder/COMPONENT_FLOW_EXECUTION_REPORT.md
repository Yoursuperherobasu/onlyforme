# LangBuilder Component Flow Execution - Comprehensive Technical Report

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Code as String - Why and How](#code-as-string---why-and-how)
3. [Template Folder Structure](#template-folder-structure)
4. [Frontend Node Architecture](#frontend-node-architecture)
5. [Flow Execution Pipeline](#flow-execution-pipeline)
6. [LangGraph Integration](#langgraph-integration)
7. [Example 1: Simple Flow Without Tools](#example-1-simple-flow-without-tools)
8. [Example 2: Agent Flow With Calculator Tool](#example-2-agent-flow-with-calculator-tool)
9. [Complete Code Execution Flow](#complete-code-execution-flow)
10. [Diagrams](#diagrams)

---

## Executive Summary

LangBuilder is a visual flow-based system that allows users to create AI applications by connecting components in a drag-and-drop interface. Each component is defined as Python code that gets dynamically evaluated and executed. The system bridges the gap between a visual frontend and Python backend through a sophisticated template and evaluation system.

**Key Concepts:**
- **Components are stored as Python code strings** in the database
- **Templates define the UI structure** for each component
- **Frontend Nodes represent the visual appearance** in the UI
- **Graph/LangGraph orchestrates execution** of connected components
- **Dynamic evaluation** converts code strings to executable classes

---

## Code as String - Why and How

### What Code Comes as String?

Every component in LangBuilder has its Python code stored as a **string**. This is the `code` field in the component template.

**Example of code string stored in database:**

```python
# This is stored as a STRING in the component's template
code_string = """
from langbuilder.custom import Component
from langbuilder.io import MessageTextInput, Output
from langbuilder.schema.message import Message

class ChatInput(Component):
    display_name = "Chat Input"
    description = "Get chat inputs from the Playground."
    
    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Text",
            value="",
        ),
    ]
    
    outputs = [
        Output(display_name="Chat Message", name="message", method="message_response"),
    ]
    
    async def message_response(self) -> Message:
        message = await Message.create(text=self.input_value)
        return message
"""
```

### Why Code is Stored as String

1. **Dynamic Custom Components**: Users can create custom components through the UI by writing Python code directly
2. **Persistence**: Component definitions need to be stored in the database
3. **Serialization**: JSON-based flows need string representation of code
4. **Hot-Reloading**: Components can be modified without restarting the server
5. **Version Control**: Different versions of components can be stored
6. **Sandboxed Execution**: Code is evaluated in a controlled namespace

### How Code String is Evaluated

The evaluation happens in `langbuilder/custom/eval.py`:

```python
# File: langbuilder/custom/eval.py

def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code."""
    # Step 1: Extract the class name from the code string
    class_name = validate.extract_class_name(code)
    
    # Step 2: Dynamically create the class from the code
    return validate.create_class(code, class_name)
```

The detailed evaluation process in `langbuilder/utils/validate.py`:

```python
# File: langbuilder/utils/validate.py

def create_class(code, class_name):
    """Dynamically create a class from a string of code."""
    
    # Step 1: Add default imports
    code = DEFAULT_IMPORT_STRING + "\n" + code
    
    # Step 2: Parse the code into AST (Abstract Syntax Tree)
    module = ast.parse(code)
    
    # Step 3: Prepare global scope with imports
    exec_globals = prepare_global_scope(module)
    
    # Step 4: Extract just the class definition
    class_code = extract_class_code(module, class_name)
    
    # Step 5: Compile the class code
    compiled_class = compile_class_code(class_code)
    
    # Step 6: Execute and return the class constructor
    return build_class_constructor(compiled_class, exec_globals, class_name)
```

**Input Example:**
```python
code_input = """
from langbuilder.custom import Component

class MyComponent(Component):
    def build(self):
        return "Hello"
"""
```

**Output:**
```python
# Returns the actual Python class type
<class 'MyComponent'>  # This can now be instantiated
```

---

## Template Folder Structure

The `template/` folder contains the foundational structures for representing components in the system.

```
langbuilder/template/
├── __init__.py
├── utils.py
├── field/
│   ├── __init__.py
│   ├── base.py          # Input and Output field definitions
│   └── prompt.py        # Prompt-specific field types
├── frontend_node/
│   ├── __init__.py
│   ├── base.py          # FrontendNode base class
│   ├── constants.py
│   └── custom_components.py  # ComponentFrontendNode
└── template/
    ├── __init__.py
    └── base.py          # Template class definition
```

### Why Template Folder is Needed

1. **UI Representation**: Defines how components appear in the frontend
2. **Field Types**: Specifies input types (text, dropdown, file, handle connections)
3. **Validation**: Ensures components have valid inputs/outputs
4. **Serialization**: Converts component definitions to JSON for the frontend

### Key Classes

#### Input (field/base.py)
```python
class Input(BaseModel):
    field_type: str | type | None     # "str", "int", "bool", "LanguageModel", etc.
    required: bool = False             # Is this field required?
    placeholder: str = ""              # Placeholder text
    is_list: bool = False              # Can accept multiple values?
    show: bool = True                  # Show in UI?
    value: Any = None                  # Default value
    name: str | None = None            # Field name (e.g., "input_value")
    display_name: str | None = None    # Display name (e.g., "Input Text")
    advanced: bool = False             # Show in advanced section?
    input_types: list[str] | None = None  # What types can connect here?
    dynamic: bool = False              # Can change based on other fields?
```

#### Output (field/base.py)
```python
class Output(BaseModel):
    types: list[str] = []             # Output types (e.g., ["Message", "Data"])
    selected: str | None = None        # Currently selected output type
    name: str                          # Output name
    display_name: str | None = None    # Display name in UI
    method: str | None = None          # Method to call for this output
    cache: bool = True                 # Should cache results?
```

---

## Frontend Node Architecture

### What is a Frontend Node?

A **FrontendNode** is the JSON representation of a component that gets sent to the frontend UI. It contains all the information needed to render the component visually.

### FrontendNode Base Class (template/frontend_node/base.py)

```python
class FrontendNode(BaseModel):
    template: Template                    # Contains all input fields
    description: str | None = None        # Component description
    icon: str | None = None               # Icon identifier
    is_input: bool | None = None          # Is this an input component?
    is_output: bool | None = None         # Is this an output component?
    base_classes: list[str]               # Types this component outputs
    name: str = ""                        # Component name (e.g., "ChatInput")
    display_name: str | None = ""         # Display name (e.g., "Chat Input")
    outputs: list[Output] = []            # Output definitions
    outputs: list[Output] = []            # Output connection points
    field_order: list[str] = []           # Order of fields in UI
    tool_mode: bool = False               # Can be used as a tool?
```

### Why Frontend Node is Needed

1. **Visual Representation**: The frontend needs a JSON structure to render components
2. **Connection Handling**: Defines input/output types for drag-and-drop connections
3. **Validation**: Frontend can validate connections before sending to backend
4. **Dynamic Updates**: Fields can change based on user selections

### Example Frontend Node JSON

```json
{
  "ChatInput": {
    "template": {
      "_type": "Component",
      "input_value": {
        "type": "str",
        "required": false,
        "value": "",
        "display_name": "Input Text",
        "show": true
      },
      "code": {
        "type": "code",
        "value": "class ChatInput(Component):...",
        "show": true,
        "dynamic": true
      }
    },
    "description": "Get chat inputs from the Playground.",
    "icon": "MessagesSquare",
    "display_name": "Chat Input",
    "is_input": true,
    "base_classes": ["Message"],
    "outputs": [
      {
        "name": "message",
        "display_name": "Chat Message",
        "types": ["Message"],
        "method": "message_response"
      }
    ]
  }
}
```

---

## Flow Execution Pipeline

When a user runs a flow, the following sequence of files and functions are executed:

### High-Level Flow

```
User clicks "Run" in UI
         ↓
    API Endpoint (/build/{flow_id}/flow)
         ↓
    Graph Construction (from JSON)
         ↓
    Vertex Building (for each component)
         ↓
    Component Instantiation (from code string)
         ↓
    Method Execution (outputs)
         ↓
    Results Returned to UI
```

### Detailed Execution Sequence

#### Step 1: API Request (api/v1/chat.py)

```python
# File: langbuilder/api/v1/chat.py

@router.post("/build/{flow_id}/flow")
async def build_flow(
    flow_id: uuid.UUID,
    inputs: InputValueRequest | None = None,  # User's input message
    data: FlowDataRequest | None = None,      # Flow definition (nodes/edges)
    ...
):
    # Start the build process
    job_id = await start_flow_build(
        flow_id=flow_id,
        inputs=inputs,
        data=data,
        ...
    )
    return {"job_id": job_id}
```

**Input to API:**
```json
{
  "inputs": {
    "input_value": "Hello, what is 2+2?",
    "session": "abc123"
  },
  "data": {
    "nodes": [...],  // List of component definitions
    "edges": [...]   // Connections between components
  }
}
```

#### Step 2: Flow Build Initialization (api/build.py)

```python
# File: langbuilder/api/build.py

async def start_flow_build(...) -> str:
    job_id = str(uuid.uuid4())
    
    # Create event queue for real-time updates
    _, event_manager = queue_service.create_queue(job_id)
    
    # Start the async build task
    task_coro = generate_flow_events(...)
    queue_service.start_job(job_id, task_coro)
    
    return job_id
```

#### Step 3: Graph Construction (api/build.py → graph/graph/base.py)

```python
# File: langbuilder/api/build.py

async def generate_flow_events(...):
    # Build graph from database or provided data
    async def build_graph_and_get_order():
        async with session_scope() as session:
            graph = await create_graph(session, flow_id_str, flow_name)
        
        # Sort vertices topologically
        first_layer = sort_vertices(graph)
        return first_layer, vertices_to_run, graph
```

```python
# File: langbuilder/graph/graph/base.py

class Graph:
    def __init__(self, ...):
        self.vertices: list[Vertex] = []
        self.edges: list[CycleEdge] = []
        self.vertex_map: dict[str, Vertex] = {}
        self.predecessor_map: dict[str, list[str]] = {}
        self.successor_map: dict[str, list[str]] = {}
    
    def add_nodes_and_edges(self, nodes, edges):
        # Process flow data
        self._graph_data = process_flow(self.raw_graph_data)
        
        # Create vertex objects for each node
        self.initialize()
```

#### Step 4: Vertex Building (graph/vertex/base.py)

```python
# File: langbuilder/graph/vertex/base.py

class Vertex:
    async def build(self, user_id=None, inputs=None, ...):
        # Reset state
        self._reset()
        
        # Inject inputs (like user's message)
        if self._is_chat_input() and inputs:
            self.update_raw_params({"input_value": inputs.get("input_value")})
        
        # Execute build steps
        for step in self.steps:
            await step(user_id=user_id, event_manager=event_manager)
        
        # Finalize
        self.finalize_build()
```

#### Step 5: Component Instantiation (interface/initialize/loading.py)

```python
# File: langbuilder/interface/initialize/loading.py

def instantiate_class(vertex, user_id=None, event_manager=None):
    """Instantiate class from module type and key, and params."""
    
    # Get component parameters
    custom_params = get_params(vertex.params)
    
    # Extract the code string
    code = custom_params.pop("code")
    
    # CRITICAL: Evaluate code string to get the class
    class_object = eval_custom_component_code(code)
    
    # Create instance of the component
    custom_component = class_object(
        _user_id=user_id,
        _parameters=custom_params,
        _vertex=vertex,
        _tracing_service=get_tracing_service(),
        _id=vertex.id,
    )
    
    return custom_component, custom_params
```

**Input to `instantiate_class`:**
```python
vertex.params = {
    "code": "class ChatInput(Component):...",  # THE CODE STRING
    "input_value": "Hello, what is 2+2?",
    "sender": "User",
    "session_id": "abc123"
}
```

**Output:**
```python
(
    <ChatInput instance>,  # Instantiated component
    {                      # Parameters (without code)
        "input_value": "Hello, what is 2+2?",
        "sender": "User",
        "session_id": "abc123"
    }
)
```

#### Step 6: Component Execution (interface/initialize/loading.py)

```python
# File: langbuilder/interface/initialize/loading.py

async def get_instance_results(custom_component, custom_params, vertex, ...):
    # Load secrets from database if needed
    custom_params = await update_params_with_load_from_db_fields(...)
    
    # Build the component based on type
    if base_type == "component":
        return await build_component(params=custom_params, custom_component=custom_component)

async def build_component(params, custom_component):
    # Set all parameters as attributes
    custom_component.set_attributes(params)
    
    # Execute the component's outputs
    build_results, artifacts = await custom_component.build_results()
    
    return custom_component, build_results, artifacts
```

#### Step 7: Output Method Execution (custom/custom_component/component.py)

```python
# File: langbuilder/custom/custom_component/component.py

class Component:
    async def build_results(self):
        """Execute all connected outputs."""
        results = {}
        artifacts = {}
        
        for output in self._outputs_map.values():
            # Get the method name (e.g., "message_response")
            method_name = output.method
            
            # Get the method from the component
            method = getattr(self, method_name)
            
            # Execute the method
            result = await method()
            
            # Store results
            results[output.name] = result
            output.value = result
        
        return results, artifacts
```

**For ChatInput Component:**
```python
# The method being called:
async def message_response(self) -> Message:
    message = await Message.create(
        text=self.input_value,  # "Hello, what is 2+2?"
        sender=self.sender,
        sender_name=self.sender_name,
        session_id=self.session_id,
    )
    return message
```

**Output:**
```python
Message(
    text="Hello, what is 2+2?",
    sender="User",
    sender_name="User",
    session_id="abc123"
)
```

---

## LangGraph Integration

LangBuilder uses **LangGraph** (from LangChain) for graph-based execution orchestration.

### LangGraph Adapter (graph_langgraph/adapter.py)

```python
# File: langbuilder/graph_langgraph/adapter.py

class LangGraphAdapter:
    """Adapter to convert LangBuilder Graph to LangGraph StateGraph."""
    
    def __init__(self, flow_id=None, flow_name=None, user_id=None):
        # Storage
        self.vertices: list[LangGraphVertex] = []
        self.vertex_map: dict[str, LangGraphVertex] = {}
        self.edges: list[dict] = []
        
        # LangGraph components
        self.workflow: StateGraph | None = None
        self.compiled_app = None
        
        # Adjacency maps
        self.predecessor_map: dict[str, list[str]] = {}
        self.successor_map: dict[str, list[str]] = {}
    
    def add_nodes_and_edges(self, nodes, edges):
        # Process flow data
        processed_data = process_flow(self.raw_graph_data)
        
        # Build vertices
        self._build_vertices(processed_data["nodes"])
        
        # Build edges
        self._build_edges(processed_data["edges"])
        
        # Build LangGraph workflow
        self._build_langgraph_workflow()
```

### LangGraph Executor (graph_langgraph/executor.py)

```python
# File: langbuilder/graph_langgraph/executor.py

class LangGraphExecutor:
    """Handles execution of LangGraph workflows."""
    
    async def execute(self, inputs=None, ...):
        # Update input vertices with user data
        if inputs:
            for vertex_id in self.adapter._is_input_vertices:
                vertex = self.adapter.get_vertex(vertex_id)
                vertex.update_raw_params(inputs, overwrite=True)
        
        # Create initial state
        initial_state = self._create_initial_state(...)
        
        # Execute the LangGraph workflow
        final_state = await self.compiled_app.ainvoke(initial_state)
        
        return final_state
```

### Connection Between Components and LangGraph

1. **LangBuilder Components** → Wrapped as **LangGraph Nodes**
2. **LangBuilder Edges** → Converted to **LangGraph Edges**
3. **Execution** → Uses LangGraph's `StateGraph.astream()` or `ainvoke()`

---

## Example 1: Simple Flow Without Tools

### Flow Description
A simple chat flow: `ChatInput` → `ChatOutput`

### Visual Representation
```
┌─────────────────┐         ┌─────────────────┐
│   ChatInput     │────────▶│   ChatOutput    │
│                 │ Message │                 │
│ input_value:    │         │ input_value:    │
│ "Hello World"   │         │ (from ChatInput)│
└─────────────────┘         └─────────────────┘
```

### JSON Flow Definition

```json
{
  "nodes": [
    {
      "id": "ChatInput-abc123",
      "data": {
        "node": {
          "template": {
            "_type": "Component",
            "code": {
              "type": "code",
              "value": "class ChatInput(Component):\n    ...",
              "show": true
            },
            "input_value": {
              "type": "str",
              "value": "",
              "display_name": "Input Text"
            }
          },
          "display_name": "Chat Input",
          "outputs": [
            {"name": "message", "types": ["Message"], "method": "message_response"}
          ]
        }
      }
    },
    {
      "id": "ChatOutput-def456",
      "data": {
        "node": {
          "template": {
            "_type": "Component",
            "code": {
              "type": "code",
              "value": "class ChatOutput(Component):\n    ...",
              "show": true
            },
            "input_value": {
              "type": "Message",
              "value": "",
              "display_name": "Inputs"
            }
          },
          "display_name": "Chat Output",
          "outputs": [
            {"name": "message", "types": ["Message"], "method": "message_response"}
          ]
        }
      }
    }
  ],
  "edges": [
    {
      "source": "ChatInput-abc123",
      "target": "ChatOutput-def456",
      "data": {
        "sourceHandle": {
          "name": "message",
          "output_types": ["Message"]
        },
        "targetHandle": {
          "fieldName": "input_value",
          "inputTypes": ["Message"]
        }
      }
    }
  ]
}
```

### Execution Trace

#### Step 1: API receives request
```
POST /api/v1/build/{flow_id}/flow
Body: { "inputs": { "input_value": "Hello World", "session": "sess123" } }
```

#### Step 2: Graph is constructed
```python
# Graph vertices created:
vertices = [
    Vertex(id="ChatInput-abc123", display_name="Chat Input"),
    Vertex(id="ChatOutput-def456", display_name="Chat Output")
]

# Topological sort determines order:
first_layer = ["ChatInput-abc123"]  # No predecessors
# ChatOutput-def456 depends on ChatInput-abc123
```

#### Step 3: ChatInput vertex builds
```python
# File: interface/initialize/loading.py

# 1. Extract code from params
code = """
class ChatInput(Component):
    inputs = [MessageTextInput(name="input_value", ...)]
    outputs = [Output(name="message", method="message_response")]
    
    async def message_response(self) -> Message:
        message = await Message.create(text=self.input_value)
        return message
"""

# 2. Evaluate code to get class
ChatInputClass = eval_custom_component_code(code)
# Result: <class 'ChatInput'>

# 3. Instantiate with parameters
component = ChatInputClass(
    _parameters={"input_value": "Hello World", "session_id": "sess123"},
    _vertex=vertex,
    _id="ChatInput-abc123"
)

# 4. Execute output method
result = await component.message_response()
# Result: Message(text="Hello World", sender="User")
```

#### Step 4: ChatOutput vertex builds
```python
# ChatOutput receives the Message from ChatInput
component = ChatOutputClass(
    _parameters={"input_value": Message(text="Hello World")},
    ...
)

result = await component.message_response()
# Result: Message(text="Hello World", sender="AI")
```

#### Step 5: Results returned
```json
{
  "vertices_results": {
    "ChatInput-abc123": {"message": "Message(text='Hello World')"},
    "ChatOutput-def456": {"message": "Message(text='Hello World')"}
  }
}
```

---

## Example 2: Agent Flow With Calculator Tool

### Flow Description
An AI agent that can use a calculator tool: `ChatInput` → `Calculator` → `Agent` → `ChatOutput`

### Visual Representation
```
┌─────────────────┐
│   ChatInput     │───────────────────────────────┐
│                 │                               │
│ "What is 25*4?" │                               │
└─────────────────┘                               │
                                                  │ Message
┌─────────────────┐       Tool                    ▼
│   Calculator    │─────────────────────▶┌─────────────────┐
│                 │                      │     Agent       │
│ build_tool()    │                      │                 │
└─────────────────┘                      │ LLM + Tools     │
                                         │                 │
                                         └────────┬────────┘
                                                  │ Message
                                                  ▼
                                         ┌─────────────────┐
                                         │   ChatOutput    │
                                         │                 │
                                         │ "The answer is  │
                                         │  100"           │
                                         └─────────────────┘
```

### Component Definitions

#### Calculator Tool Component
```python
# File: langbuilder/components/tools/calculator.py

class CalculatorToolComponent(LCToolComponent):
    display_name = "Calculator"
    description = "Perform basic arithmetic operations."
    
    inputs = [
        MessageTextInput(
            name="expression",
            display_name="Expression",
            info="The arithmetic expression to evaluate.",
        ),
    ]
    
    # Two outputs: Data (direct result) and Tool (for agent use)
    outputs = [
        Output(name="api_run_model", display_name="Data", method="run_model"),
        Output(name="api_build_tool", display_name="Tool", method="build_tool"),
    ]
    
    def run_model(self) -> list[Data]:
        """Direct execution - returns Data."""
        result = self._evaluate_expression(self.expression)
        return [Data(data={"result": result})]
    
    def build_tool(self) -> Tool:
        """For agent use - returns a LangChain Tool."""
        return StructuredTool.from_function(
            name="calculator",
            description="Evaluate arithmetic expressions.",
            func=self._evaluate_expression,
        )
```

#### Agent Component
```python
# File: langbuilder/components/agents/agent.py

class AgentComponent(ToolCallingAgentComponent):
    display_name = "Agent"
    description = "Define agent instructions and use tools."
    
    inputs = [
        DropdownInput(name="agent_llm", display_name="Model Provider", ...),
        HandleInput(name="tools", display_name="Tools", input_types=["Tool"], is_list=True),
        MessageInput(name="input_value", display_name="Input", ...),
        MultilineInput(name="system_prompt", display_name="Agent Instructions", ...),
    ]
    
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]
    
    async def message_response(self) -> Message:
        # Get LLM model
        llm_model, display_name = self.get_llm()
        
        # Get chat history
        self.chat_history = await self.get_memory_data()
        
        # Normalize tools to list
        if self.tools is None:
            self.tools = []
        
        # Set up agent
        self.set(
            llm=llm_model,
            tools=self.tools,
            chat_history=self.chat_history,
            input_value=self.input_value,
            system_prompt=self.system_prompt,
        )
        
        # Create and run agent
        agent = self.create_agent_runnable()
        result = await self.run_agent(agent)
        
        return result
```

### Execution Trace

#### Step 1: Build order determined
```python
# Topological sort:
# Level 0: ChatInput (no dependencies)
# Level 1: Calculator (no dependencies from flow, but agent needs its output)
# Level 2: Agent (depends on ChatInput message + Calculator tool)
# Level 3: ChatOutput (depends on Agent)

first_layer = ["ChatInput-xxx", "CalculatorTool-yyy"]
```

#### Step 2: ChatInput executes
```python
# Input: "What is 25*4?"
# Output: Message(text="What is 25*4?", sender="User")
```

#### Step 3: Calculator Tool builds
```python
# The Calculator component's build_tool() method is called
# (because the Agent is connected to its "Tool" output)

def build_tool(self) -> Tool:
    return StructuredTool.from_function(
        name="calculator",
        description="Evaluate arithmetic expressions.",
        func=self._evaluate_expression,
        args_schema=self.CalculatorToolSchema,  # Pydantic model for args
    )

# Output: StructuredTool(name="calculator", ...)
```

#### Step 4: Agent executes
```python
# Agent receives:
# - input_value: Message("What is 25*4?")
# - tools: [StructuredTool(name="calculator", ...)]

async def message_response(self):
    # 1. Get LLM (e.g., OpenAI GPT-4)
    llm_model = self._build_llm_model(...)
    
    # 2. Create tool-calling agent
    agent = create_tool_calling_agent(llm_model, self.tools, prompt)
    
    # 3. Run agent with streaming
    result = await self.run_agent(agent)
    
    # Agent internally:
    # - Sends "What is 25*4?" to LLM
    # - LLM decides to call calculator tool with "25*4"
    # - Tool returns "100"
    # - LLM formulates response: "The answer is 100"
    
    return Message(text="The answer to 25*4 is 100.", sender="AI")
```

#### Step 5: ChatOutput executes
```python
# Receives: Message(text="The answer to 25*4 is 100.", sender="AI")
# Stores to database and returns
```

### Complete Data Flow

```
User Input: "What is 25*4?"
         ↓
┌─────────────────────────────────────────────────────────────┐
│ ChatInput.message_response()                                 │
│   Input: input_value = "What is 25*4?"                       │
│   Output: Message(text="What is 25*4?", sender="User")       │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ CalculatorTool.build_tool()                                  │
│   Input: (none - tool definition)                            │
│   Output: StructuredTool(                                    │
│     name="calculator",                                       │
│     func=evaluate_expression,                                │
│     args_schema={"expression": str}                          │
│   )                                                          │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ Agent.message_response()                                     │
│   Input:                                                     │
│     - input_value = Message("What is 25*4?")                 │
│     - tools = [StructuredTool("calculator")]                 │
│     - system_prompt = "You are a helpful assistant..."       │
│                                                              │
│   Internal LLM Calls:                                        │
│     1. User: "What is 25*4?"                                 │
│     2. LLM thinks: "I should use calculator"                 │
│     3. Tool call: calculator(expression="25*4")              │
│     4. Tool result: "100"                                    │
│     5. LLM response: "The answer to 25*4 is 100."            │
│                                                              │
│   Output: Message(text="The answer is 100.", sender="AI")    │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ ChatOutput.message_response()                                │
│   Input: Message("The answer is 100.")                       │
│   Action: Store to database, emit to frontend                │
│   Output: Message(text="The answer is 100.", sender="AI")    │
└─────────────────────────────────────────────────────────────┘
```

---

## Complete Code Execution Flow

### Full Sequence Diagram

```
User (Browser)
    │
    │ POST /api/v1/build/{flow_id}/flow
    │ Body: { inputs: { input_value: "Hello" } }
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           API Layer                                     │
│  File: langbuilder/api/v1/chat.py                                       │
│                                                                         │
│  @router.post("/build/{flow_id}/flow")                                  │
│  async def build_flow(flow_id, inputs, data, ...):                      │
│      job_id = await start_flow_build(...)                               │
│      return {"job_id": job_id}                                          │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Build Orchestration                              │
│  File: langbuilder/api/build.py                                         │
│                                                                         │
│  async def start_flow_build(...):                                       │
│      job_id = str(uuid.uuid4())                                         │
│      _, event_manager = queue_service.create_queue(job_id)              │
│      task = generate_flow_events(...)                                   │
│      queue_service.start_job(job_id, task)                              │
│                                                                         │
│  async def generate_flow_events(...):                                   │
│      graph = await create_graph(session, flow_id, ...)                  │
│      first_layer = sort_vertices(graph)                                 │
│      for vertex_id in first_layer:                                      │
│          await build_vertices(vertex_id, graph, event_manager)          │
│      event_manager.on_end({})                                           │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Graph Construction                             │
│  File: langbuilder/graph/graph/base.py                                  │
│                                                                         │
│  class Graph:                                                           │
│      def add_nodes_and_edges(self, nodes, edges):                       │
│          self._graph_data = process_flow(self.raw_graph_data)           │
│          self.initialize()  # Creates Vertex objects                    │
│                                                                         │
│      def prepare(self, stop_component_id, start_component_id):          │
│          self.sort_vertices(start_component_id)                         │
│          return self                                                    │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           Vertex Building                               │
│  File: langbuilder/graph/vertex/base.py                                 │
│                                                                         │
│  class Vertex:                                                          │
│      async def build(self, user_id, inputs, ...):                       │
│          self._reset()                                                  │
│          for step in self.steps:  # [self._build]                       │
│              await step(user_id=user_id, ...)                           │
│          self.finalize_build()                                          │
│                                                                         │
│      async def _build(self, ...):                                       │
│          # Resolve dependencies (wait for predecessor vertices)         │
│          await self._resolve_parameters()                               │
│          # Get results                                                  │
│          await self._build_results(custom_component, custom_params)     │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Component Instantiation                            │
│  File: langbuilder/interface/initialize/loading.py                      │
│                                                                         │
│  def instantiate_class(vertex, user_id, event_manager):                 │
│      custom_params = get_params(vertex.params)                          │
│      code = custom_params.pop("code")  # Extract code string            │
│                                                                         │
│      # MAGIC HAPPENS HERE - Code string → Python class                  │
│      class_object = eval_custom_component_code(code)                    │
│                                                                         │
│      # Create instance                                                  │
│      custom_component = class_object(                                   │
│          _parameters=custom_params,                                     │
│          _vertex=vertex,                                                │
│          _id=vertex.id,                                                 │
│      )                                                                  │
│      return custom_component, custom_params                             │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Code Evaluation                                 │
│  File: langbuilder/custom/eval.py                                       │
│                                                                         │
│  def eval_custom_component_code(code: str) -> type:                     │
│      class_name = validate.extract_class_name(code)                     │
│      return validate.create_class(code, class_name)                     │
│                                                                         │
│  # In validate.py:                                                      │
│  def create_class(code, class_name):                                    │
│      module = ast.parse(code)           # Parse to AST                  │
│      exec_globals = prepare_global_scope(module)  # Handle imports      │
│      class_code = extract_class_code(module, class_name)                │
│      compiled = compile(ast.Module([class_code]), "<string>", "exec")   │
│      exec(compiled, exec_globals, exec_locals)                          │
│      return exec_globals[class_name]    # Return the class              │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Component Execution                              │
│  File: langbuilder/interface/initialize/loading.py                      │
│                                                                         │
│  async def build_component(params, custom_component):                   │
│      custom_component.set_attributes(params)  # Set input values        │
│      build_results, artifacts = await custom_component.build_results()  │
│      return custom_component, build_results, artifacts                  │
│                                                                         │
│  # In component.py:                                                     │
│  async def build_results(self):                                         │
│      for output in self._outputs_map.values():                          │
│          method = getattr(self, output.method)                          │
│          result = await method()  # Call the output method              │
│          output.value = result                                          │
│      return results, artifacts                                          │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Event Streaming                                 │
│  File: langbuilder/api/build.py                                         │
│                                                                         │
│  # After each vertex builds:                                            │
│  event_manager.on_end_vertex(data={"build_data": build_response})       │
│                                                                         │
│  # When all done:                                                       │
│  event_manager.on_end(data={})                                          │
│  await event_manager.queue.put((None, None, time.time()))               │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
User (Browser) receives SSE events with results
```

---

## Diagrams

### Component Class Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BaseComponent                                  │
│  File: langbuilder/custom/custom_component/base_component.py             │
│  - _id: str                                                              │
│  - _code: str                                                            │
│  - _template_config: dict                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CustomComponent                                  │
│  File: langbuilder/custom/custom_component/custom_component.py           │
│  - name, display_name, description, icon                                 │
│  - field_config, field_order                                             │
│  - build() method (abstract)                                             │
│  - get_function_entrypoint_args                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Component                                     │
│  File: langbuilder/custom/custom_component/component.py                  │
│  - inputs: list[InputTypes]                                              │
│  - outputs: list[Output]                                                 │
│  - _inputs: dict[str, InputTypes]                                        │
│  - _outputs_map: dict[str, Output]                                       │
│  - set(), run(), build_results()                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│   LCToolComponent │   │  LCAgentComponent │   │    ChatComponent  │
│   (Tool-based)    │   │   (Agent-based)   │   │   (IO-based)      │
│                   │   │                   │   │                   │
│ - run_model()     │   │ - build_agent()   │   │ - send_message()  │
│ - build_tool()    │   │ - run_agent()     │   │ - message_response│
└───────────────────┘   └───────────────────┘   └───────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│CalculatorTool     │   │ AgentComponent    │   │ ChatInput         │
│ WebSearchTool     │   │ (with providers)  │   │ ChatOutput        │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

### Flow Execution State Machine

```
                    ┌─────────────────┐
                    │     START       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Graph Created  │
                    │  (from JSON)    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Topological Sort│
                    │ (determine order)│
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     Process First Layer      │
              │ (vertices with no deps)      │
              └──────────────┬───────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Build Vertex A  │ │ Build Vertex B  │ │ Build Vertex C  │
│                 │ │                 │ │                 │
│ 1. Instantiate  │ │ 1. Instantiate  │ │ 1. Instantiate  │
│ 2. Set params   │ │ 2. Set params   │ │ 2. Set params   │
│ 3. Execute      │ │ 3. Execute      │ │ 3. Execute      │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   Get Next Runnable Vertices │
              │   (successors ready to run)  │
              └──────────────┬───────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  More vertices? │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ YES                         │ NO
              ▼                             ▼
    (loop back to Process)         ┌─────────────────┐
                                   │      END        │
                                   │ (send results)  │
                                   └─────────────────┘
```

### Data Flow in Agent with Tools

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Message                                     │
│                    "What is 25 * 4?"                                    │
└────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         ChatInput                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ async def message_response(self):                                │   │
│  │     message = Message.create(                                    │   │
│  │         text=self.input_value,  # "What is 25 * 4?"              │   │
│  │         sender="User"                                            │   │
│  │     )                                                            │   │
│  │     return message                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Output: Message(text="What is 25 * 4?")                                │
└────────────────────────────────────────────────────────────────────────┘
                                │
                                │ Message
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Calculator Tool                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ def build_tool(self) -> Tool:                                    │   │
│  │     return StructuredTool.from_function(                         │   │
│  │         name="calculator",                                       │   │
│  │         description="Evaluate arithmetic expressions",           │   │
│  │         func=self._evaluate_expression,                          │   │
│  │     )                                                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Output: StructuredTool(name="calculator")                              │
└────────────────────────────────────────────────────────────────────────┘
                                │
                                │ Tool
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           Agent                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ async def message_response(self):                                │   │
│  │     # 1. Get LLM                                                 │   │
│  │     llm = self.get_llm()  # e.g., GPT-4                          │   │
│  │                                                                  │   │
│  │     # 2. Create agent with tools                                 │   │
│  │     agent = create_tool_calling_agent(llm, self.tools, prompt)   │   │
│  │                                                                  │   │
│  │     # 3. Run agent                                               │   │
│  │     result = await self.run_agent(agent)                         │   │
│  │                                                                  │   │
│  │     return result                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Internal Agent Execution:                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. LLM receives: "What is 25 * 4?"                               │   │
│  │ 2. LLM decides to use calculator tool                           │   │
│  │ 3. Tool Call: calculator(expression="25*4")                      │   │
│  │ 4. Tool Result: "100"                                            │   │
│  │ 5. LLM generates final answer                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Output: Message(text="25 * 4 = 100", sender="AI")                      │
└────────────────────────────────────────────────────────────────────────┘
                                │
                                │ Message
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         ChatOutput                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ async def message_response(self):                                │   │
│  │     # Store message to database                                  │   │
│  │     stored = await self.send_message(self.input_value)           │   │
│  │     return stored                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Output: Message(text="25 * 4 = 100", id="msg-123")                     │
└────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Final Response to User                             │
│                      "25 * 4 = 100"                                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

### Key Files and Their Roles

| File | Purpose |
|------|---------|
| `api/v1/chat.py` | API endpoints for flow execution |
| `api/build.py` | Flow build orchestration and event streaming |
| `graph/graph/base.py` | Graph construction and vertex management |
| `graph/vertex/base.py` | Individual vertex building and execution |
| `interface/initialize/loading.py` | Component instantiation from code strings |
| `custom/eval.py` | Code string evaluation to Python classes |
| `utils/validate.py` | AST parsing and class creation |
| `custom/custom_component/component.py` | Base Component class with build_results() |
| `template/frontend_node/base.py` | FrontendNode for UI representation |
| `template/field/base.py` | Input and Output field definitions |
| `graph_langgraph/adapter.py` | LangGraph integration adapter |
| `components/tools/*.py` | Tool component implementations |
| `components/agents/agent.py` | Agent component with LLM + tools |
| `components/input_output/*.py` | Chat input/output components |

### Key Concepts Recap

1. **Code as String**: Components are Python code stored as strings, dynamically evaluated at runtime
2. **Template**: Defines the structure and UI representation of a component
3. **FrontendNode**: JSON representation sent to the UI for rendering
4. **Graph**: Manages vertices (components) and edges (connections)
5. **Vertex**: Wrapper around a component for graph execution
6. **LangGraph**: Optional orchestration layer for advanced execution patterns
7. **Output Method**: Each component defines methods that produce outputs
8. **Tool Mode**: Components can be wrapped as LangChain tools for agent use
