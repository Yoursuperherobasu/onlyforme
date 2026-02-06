from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentcore.components._importing import import_mod

if TYPE_CHECKING:
    from .azure_openai import AzureChatOpenAIComponent
    from .azure_openai_embeddings import AzureOpenAIEmbeddingsComponent
    from .google_generative_ai import GoogleGenerativeAIComponent
    from .google_generative_ai_embeddings import GoogleGenerativeAIEmbeddingsComponent
    from .groq import GroqModel
    from .mistral_embeddings import MistralAIEmbeddingsComponent


_dynamic_imports = {
    "GroqModel": "groq",
    "AzureChatOpenAIComponent": "azure_openai",
    "AzureOpenAIEmbeddingsComponent": "azure_openai_embeddings",
    "GoogleGenerativeAIComponent":"google_chat",
    "GoogleGenerativeAIEmbeddingsComponent":"google_embedding",
     "MistralAIEmbeddingsComponent": "mistral_embeddings",
}

__all__ = [
    "GroqModel",
    "AzureChatOpenAIComponent",
    "AzureOpenAIEmbeddingsComponent",
    "GoogleGenerativeAIComponent",
    "GoogleGenerativeAIEmbeddingsComponent",
    "HuggingFaceInferenceAPIEmbeddingsComponent",
    "MistralAIModelComponent",
]


def __getattr__(attr_name: str) -> Any:
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
