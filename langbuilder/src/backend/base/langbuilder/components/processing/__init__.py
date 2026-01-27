"""Processing components for LangBuilder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langbuilder.components._importing import import_mod

if TYPE_CHECKING:
    from langbuilder.components.processing.batch_run import BatchRunComponent
    from langbuilder.components.processing.parser import ParserComponent
    from langbuilder.components.processing.prompt import PromptComponent
    from langbuilder.components.processing.split_text import SplitTextComponent
    from langbuilder.components.processing.structured_output import StructuredOutputComponent

_dynamic_imports = {
    "BatchRunComponent": "batch_run",
    "ParserComponent": "parser",
    "PromptComponent": "prompt",
    "SplitTextComponent": "split_text",
    "StructuredOutputComponent": "structured_output",
}

__all__ = [
    "BatchRunComponent",
    "ParserComponent",
    "PromptComponent",
    "SplitTextComponent",
    "StructuredOutputComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import processing components on attribute access."""
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
