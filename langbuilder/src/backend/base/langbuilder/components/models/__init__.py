from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langbuilder.components._importing import import_mod

if TYPE_CHECKING:
    from .amazon_bedrock_embedding import AmazonBedrockEmbeddingsComponent
    from .amazon_bedrock_model import AmazonBedrockComponent
    from .openai import OpenAIEmbeddingsComponent
    from .openai_chat_model import OpenAIModelComponent
    from .anthropic import AnthropicModelComponent
    from .azure_openai import AzureChatOpenAIComponent
    from .azure_openai_embeddings import AzureOpenAIEmbeddingsComponent
    from .google_generative_ai import GoogleGenerativeAIComponent
    from .google_generative_ai_embeddings import GoogleGenerativeAIEmbeddingsComponent


_dynamic_imports = {
    "OpenAIEmbeddingsComponent": "openai",
    "OpenAIModelComponent": "openai_chat_model",
    "GroqModel": "groq",
    "AzureChatOpenAIComponent": "azure_openai",
    "AzureOpenAIEmbeddingsComponent": "azure_openai_embeddings",
    "AnthropicModelComponent": "anthropic",
    "AmazonBedrockEmbeddingsComponent": "amazon_bedrock_embedding",
    "AmazonBedrockComponent": "amazon_bedrock_model",
    "GoogleGenerativeAIComponent":"google_chat",
    "GoogleGenerativeAIEmbeddingsComponent":"google_embedding",
}

__all__ = [
    "OpenAIEmbeddingsComponent",
    "OpenAIModelComponent",
    "GroqModel",
    "AzureChatOpenAIComponent",
    "AzureOpenAIEmbeddingsComponent",
    "AnthropicModelComponent",
    "AmazonBedrockComponent",
    "AmazonBedrockEmbeddingsComponent",
    "GoogleGenerativeAIComponent",
    "GoogleGenerativeAIEmbeddingsComponent",
    
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import OpenAI components on attribute access."""
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
