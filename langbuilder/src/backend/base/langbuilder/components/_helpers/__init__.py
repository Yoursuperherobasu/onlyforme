from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langbuilder.components._importing import import_mod

if TYPE_CHECKING:
    from langbuilder.components._helpers.calculator_core import CalculatorNode
    from langbuilder.components._helpers.create_list import CreateListNode
    from langbuilder.components._helpers.current_date import CurrentDateNode
    from langbuilder.components._helpers.id_generator import IDGeneratorNode
    from langbuilder.components._helpers.memory import MemoryNode
    from langbuilder.components._helpers.output_parser import OutputParserNode
    from langbuilder.components._helpers.store_message import MessageStoreNode

_dynamic_imports = {
    "CalculatorNode": "calculator_core",
    "CreateListNode": "create_list",
    "CurrentDateNode": "current_date",
    "IDGeneratorNode": "id_generator",
    "MemoryNode": "memory",
    "OutputParserNode": "output_parser",
    "MessageStoreNode": "store_message",
}

__all__ = [
    "CalculatorNode",
    "CreateListNode",
    "CurrentDateNode",
    "IDGeneratorNode",
    "MemoryNode",
    "MessageStoreNode",
    "OutputParserNode",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import helper components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
