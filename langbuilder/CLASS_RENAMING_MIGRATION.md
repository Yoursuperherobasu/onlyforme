# Class Renaming Migration Guide

## Overview

This document describes the comprehensive renaming of core component classes in the LangBuilder codebase to use more industry-standard, clearer terminology.

## Naming Changes Summary

| Old Class Name | New Class Name | File Location |
|----------------|----------------|---------------|
| `BaseComponent` | `NodeBase` | `custom/custom_component/base_component.py` |
| `CustomComponent` | `ExecutableNode` | `custom/custom_component/custom_component.py` |
| `Component` | `Node` | `custom/custom_component/component.py` |
| `ComponentWithCache` | `NodeWithCache` | `custom/custom_component/component_with_cache.py` |

## Backwards Compatibility

**Backwards compatibility aliases are maintained** in `custom/__init__.py`:

```python
from langbuilder.custom.custom_component.component import Node
from langbuilder.custom.custom_component.custom_component import ExecutableNode

# Backwards compatibility aliases
Component = Node
CustomComponent = ExecutableNode

__all__ = ["Node", "ExecutableNode", "Component", "CustomComponent"]
```

This means existing code using `Component` or `CustomComponent` will continue to work without modification.

---

## Complete Changes Summary

### 1. Core Class Definition Files (4 files)

| File | Change |
|------|--------|
| `base_component.py` | `class BaseComponent` → `class NodeBase` |
| `custom_component.py` | `class CustomComponent(NodeBase)` → `class ExecutableNode(NodeBase)` |
| `component.py` | `class Component(CustomComponent)` → `class Node(ExecutableNode)` |
| `component_with_cache.py` | `class ComponentWithCache(Component)` → `class NodeWithCache(Node)` |

### 2. Type Hints Updated

The following files had type hints updated:

| File | Changes |
|------|---------|
| `base/tools/component_tool.py` | `component: Component` → `component: Node` in 6 functions |
| `custom/utils.py` | Type hints updated for ~10 functions |
| `interface/initialize/loading.py` | `custom_component: CustomComponent` → `custom_component: ExecutableNode` |
| `services/tracing/service.py` | `component: Component` → `component: Node` |
| `api/v1/endpoints.py` | `isinstance(x, Component)` → `isinstance(x, Node)` |

### 3. isinstance() Checks Updated

| File | Old | New |
|------|-----|-----|
| `component.py` | `isinstance(x, Component)` | `isinstance(x, Node)` |
| `endpoints.py` | `isinstance(component_instance, Component)` | `isinstance(component_instance, Node)` |
| `tests/integration/utils.py` | `isinstance(value, Component)` | `isinstance(value, Node)` |

### 4. Class Recognition Updated (for backwards compatibility)

| File | Purpose | Old Values | New Values |
|------|---------|------------|------------|
| `custom_component.py` | Base class detection | `"Component", "CustomComponent"` | `"Component", "CustomComponent", "Node", "ExecutableNode"` |
| `code_parser.py` | Base class filtering | `"CustomComponent", "Component", "BaseComponent"` | Added `"ExecutableNode", "Node", "NodeBase"` |
| `utils.py` | Type name detection | `{"Component", "CustomComponent"}` | `{"Component", "CustomComponent", "Node", "ExecutableNode"}` |
| `graph/constants.py` | Vertex type mapping | `"CustomComponent", "Component"` | Added `"ExecutableNode", "Node"` |

### 5. Code Templates Updated

| File | Change |
|------|--------|
| `template/frontend_node/custom_components.py` | Default code template now uses `Node` |

### 6. Import Path Normalization (validate.py)

Old imports are automatically converted:
- `from langbuilder import CustomComponent` → `from langbuilder.custom import ExecutableNode`
- `from langbuilder import Component` → `from langbuilder.custom import Node`

---

## Detailed Changes by Category

### Python Files Updated

#### Core Custom Component Files
- `custom/custom_component/base_component.py` - Class renamed
- `custom/custom_component/custom_component.py` - Class renamed, base class detection updated  
- `custom/custom_component/component.py` - Class renamed, type hints updated
- `custom/custom_component/component_with_cache.py` - Class renamed
- `custom/__init__.py` - Exports updated with aliases

#### Base Directory
- `base/tools/component_tool.py` - Type hints updated
- `base/models/model.py` - Inherits from Node

#### Interface/Utils
- `interface/initialize/loading.py` - Type hints updated
- `custom/utils.py` - Type hints updated, type detection updated
- `custom/code_parser/code_parser.py` - Base class filtering updated
- `utils/validate.py` - Context and import handling updated

#### API/Services
- `api/v1/endpoints.py` - isinstance checks, instantiation updated
- `services/tracing/service.py` - Type hints updated

#### Graph
- `graph/graph/constants.py` - Vertex type mapping updated

#### Templates
- `template/frontend_node/custom_components.py` - Default code template updated

### Test Files Updated
- `tests/base.py` - Return type hints
- `tests/integration/utils.py` - Import, type hints, isinstance
- `tests/unit/test_custom_component.py` - Import alias for NodeBase
- `tests/unit/components/agents/test_agent_component.py` - Import, type hints
- `tests/data/component.py` - Uses ExecutableNode
- `tests/data/component_with_templatefield.py` - Uses ExecutableNode

### JSON Starter Projects (41 files)
All starter project JSON files updated:
- Import statements: `from langbuilder.custom.custom_component.component import Component` → `import Node`
- Class inheritance: `class ClassName(Component):` → `class ClassName(Node):`

---
- `components/inputs/`
- `components/langchain_utilities/`
- `components/logic/`
- `components/memories/`
- `components/models/`
- `components/outputs/`
- `components/processing/`
- `components/prompts/`
- `components/prototypes/`
- `components/retrievers/`
- `components/tools/`
- `components/vectorstores/`

#### Base Directory (`base/`)

- `base/agents/agent.py`
- `base/agents/crewai/crew.py`
- `base/bundles/base.py`
- `base/bundles/chat_with_tool.py`
- `base/bundles/manager.py`
- `base/data/data.py`
- `base/embeddings/model.py`
- `base/io/io.py`
- `base/io/inputs.py`
- `base/llms/model.py`
- `base/memories/base_memory.py`
- `base/models/model.py`
- `base/processing/base.py`
- `base/prompts/prompt.py`
- `base/tools/component_tool.py`
- `base/tools/run_flow.py`
- `base/vectorstores/base.py`

---

### 3. JSON Starter Project Files

**41 JSON files updated** in:
- `src/backend/base/langbuilder/initial_setup/starter_projects/`
- Additional starter project directories

**Changes made:**
1. Import statements updated from:
   ```python
   from langbuilder.custom.custom_component.component import Component
   ```
   to:
   ```python
   from langbuilder.custom.custom_component.component import Node
   ```

2. Class inheritance updated from:
   ```python
   class ClassName(Component):
   ```
   to:
   ```python
   class ClassName(Node):
   ```

**Files affected include:**
- `Basic Prompting.json`
- `Blog Writer.json`
- `Complex Agent.json`
- `Document QA.json`
- `Dynamic Agent.json`
- `Hierarchical Agent.json`
- `Image Sentiment Analysis.json`
- `Market Research.json`
- `Memory Chatbot.json`
- `Multi Agent.json`
- `Prompt Chaining.json`
- `RAG with Message History.json`
- `Research Agent.json`
- `SaaS Pricing.json`
- `Sequential Agent.json`
- `Sequential Tasks Agent.json`
- `Simple Agent.json`
- `Simple API.json`
- `Travel Planning Agents.json`
- `Vector Store RAG.json`
- `Website Traffic Analysis.json`
- And more...

---

### 4. Test Files

**Python test files updated:**
- `src/backend/tests/unit/test_custom_component.py`

**Frontend test files updated:**
- `src/frontend/tests/extended/features/flowPage.spec.ts`
- `src/frontend/tests/fixtures/codeAreaComponent.json`
- `src/frontend/tests/fixtures/defaultCodeAreaComponentCode.ts`
- `src/frontend/tests/extended/features/code-in-code.spec.ts`
- `src/frontend/tests/extended/features/globalVariables.spec.ts`
- `src/frontend/tests/extended/features/keyboardKeysHandler.spec.ts`
- `src/frontend/tests/extended/regression/generalBugs-shard-7.spec.ts`
- `src/frontend/tests/extended/regression/generalBugs-shard-10.spec.ts`
- `src/frontend/tests/extended/regression/generalBugs-shard-14.spec.ts`

---

## Migration Instructions for Developers

### If you have custom components using old names:

**Option 1: Use new names (recommended)**
```python
# Before
from langbuilder.custom.custom_component.component import Component

class MyComponent(Component):
    pass

# After
from langbuilder.custom.custom_component.component import Node

class MyComponent(Node):
    pass
```

**Option 2: Use backwards compatibility aliases (temporary)**
```python
# This still works due to backwards compatibility
from langbuilder.custom import Component

class MyComponent(Component):
    pass
```

### For custom code in flows (JSON files):

Update your flow JSON files to use new import names:

```python
# Old
from langbuilder.custom.custom_component.component import Component

class MyCustomNode(Component):
    ...

# New
from langbuilder.custom.custom_component.component import Node

class MyCustomNode(Node):
    ...
```

---

## Class Hierarchy Overview

```
NodeBase (base_component.py)
    └── ExecutableNode (custom_component.py)
            └── Node (component.py)
                    └── NodeWithCache (component_with_cache.py)
```

**Purpose of each class:**

1. **NodeBase**: Foundation class with basic input/output handling, status tracking, and metadata
2. **ExecutableNode**: Adds tracing (Langfuse), flow control, graph access, and `run()` method abstraction
3. **Node**: Main class developers extend - defines `inputs`, `outputs`, `build()` method pattern
4. **NodeWithCache**: Adds shared cache service access for stateful operations

---

## Files Changed Summary

| Category | Files Changed |
|----------|---------------|
| Core class definitions | 4 |
| Custom __init__.py | 1 |
| Components directory (Python) | ~50 |
| Base directory (Python) | ~15 |
| Starter project JSON files | 41 |
| Frontend test files | ~10 |
| Backend test files | 1 |
| **Total** | **~122 files** |

---

## Rationale for New Names

| New Name | Rationale |
|----------|-----------|
| **NodeBase** | Clearly indicates this is the base class for nodes in the execution graph |
| **ExecutableNode** | Emphasizes that this represents an executable unit in the flow |
| **Node** | Industry-standard term used in graph-based systems (LangGraph, Apache Airflow, Node-RED) |
| **NodeWithCache** | Clear extension of Node with caching capability |

---

## Date of Migration

**Migration Date**: 2025-01-27

---

## Support

If you encounter any issues with this migration, check:
1. Your imports are using the correct new class names
2. Your class inheritance is updated
3. Backwards compatibility aliases are working for gradual migration
