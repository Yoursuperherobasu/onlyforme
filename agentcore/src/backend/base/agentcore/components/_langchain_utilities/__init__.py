from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentcore.components._importing import import_mod

if TYPE_CHECKING:
    from .character import CharacterTextSplitterNode
    from .conversation import ConversationChainNode
    from .csv_agent import CSVAgentNode
    from .fake_embeddings import FakeEmbeddingsComponent
    from .html_link_extractor import HtmlLinkExtractorNode
    from .json_agent import JsonAgentNode
    from .langchain_hub import LangChainHubPromptNode
    from .language_recursive import LanguageRecursiveTextSplitterNode
    from .language_semantic import SemanticTextSplitterNode
    from .llm_checker import LLMCheckerChainNode
    from .llm_math import LLMMathChainNode
    from .natural_language import NaturalLanguageTextSplitterNode
    from .openai_tools import OpenAIToolsAgentNode
    from .openapi import OpenAPIAgentNode
    from .recursive_character import RecursiveCharacterTextSplitterNode
    from .retrieval_qa import RetrievalQANode
    from .runnable_executor import RunnableExecComponent
    from .self_query import SelfQueryRetrieverNode
    from .spider import SpiderTool
    from .sql import SQLAgentNode
    from .sql_database import SQLDatabaseNode
    from .sql_generator import SQLGeneratorNode
    from .tool_calling import ToolCallingAgentNode
    from .vector_store_info import VectorStoreInfoNode
    from .vector_store_router import VectorStoreRouterAgentNode
    from .xml_agent import XMLAgentNode

_dynamic_imports = {
    "CharacterTextSplitterNode": "character",
    "ConversationChainNode": "conversation",
    "CSVAgentNode": "csv_agent",
    "FakeEmbeddingsComponent": "fake_embeddings",
    "HtmlLinkExtractorNode": "html_link_extractor",
    "JsonAgentNode": "json_agent",
    "LangChainHubPromptNode": "langchain_hub",
    "LanguageRecursiveTextSplitterNode": "language_recursive",
    "LLMCheckerChainNode": "llm_checker",
    "LLMMathChainNode": "llm_math",
    "NaturalLanguageTextSplitterNode": "natural_language",
    "OpenAIToolsAgentNode": "openai_tools",
    "OpenAPIAgentNode": "openapi",
    "RecursiveCharacterTextSplitterNode": "recursive_character",
    "RetrievalQANode": "retrieval_qa",
    "RunnableExecComponent": "runnable_executor",
    "SelfQueryRetrieverNode": "self_query",
    "SemanticTextSplitterNode": "language_semantic",
    "SpiderTool": "spider",
    "SQLAgentNode": "sql",
    "SQLDatabaseNode": "sql_database",
    "SQLGeneratorNode": "sql_generator",
    "ToolCallingAgentNode": "tool_calling",
    "VectorStoreInfoNode": "vector_store_info",
    "VectorStoreRouterAgentNode": "vector_store_router",
    "XMLAgentNode": "xml_agent",
}

__all__ = [
    "CSVAgentNode",
    "CharacterTextSplitterNode",
    "ConversationChainNode",
    "FakeEmbeddingsComponent",
    "HtmlLinkExtractorNode",
    "JsonAgentNode",
    "LLMCheckerChainNode",
    "LLMMathChainNode",
    "LangChainHubPromptNode",
    "LanguageRecursiveTextSplitterNode",
    "NaturalLanguageTextSplitterNode",
    "OpenAIToolsAgentNode",
    "OpenAPIAgentNode",
    "RecursiveCharacterTextSplitterNode",
    "RetrievalQANode",
    "RunnableExecComponent",
    "SQLAgentNode",
    "SQLDatabaseNode",
    "SQLGeneratorNode",
    "SelfQueryRetrieverNode",
    "SemanticTextSplitterNode",
    "SpiderTool",
    "ToolCallingAgentNode",
    "VectorStoreInfoNode",
    "VectorStoreRouterAgentNode",
    "XMLAgentNode",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import langchain utility components on attribute access."""
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
