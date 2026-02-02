from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langbuilder.components._importing import import_mod

if TYPE_CHECKING:
    from langbuilder.components.amazon.amazon_bedrock_embedding import AmazonBedrockEmbeddingsNode
    from langbuilder.components.amazon.amazon_bedrock_model import AmazonBedrockNode

_dynamic_imports = {
    "AmazonBedrockEmbeddingsNode": "amazon_bedrock_embedding",
    "AmazonBedrockNode": "amazon_bedrock_model",
}

__all__ = [
    "AmazonBedrockNode",
    "AmazonBedrockEmbeddingsNode",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import amazon components on attribute access."""
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
