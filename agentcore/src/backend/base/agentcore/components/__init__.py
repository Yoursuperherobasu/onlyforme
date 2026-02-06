"""AgentCore Components module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentcore.components._importing import import_mod

if TYPE_CHECKING:
    from agentcore.components import (
        agents,
        aiml,
        amazon,
        anthropic,
        Guardrails,
        HumanInTheLoop,
        azure,
        custom_component,
        data,
        embeddings,
        google,
        groq,
        helpers,
        input_output,
        logic,
        mistral,
        models,
        processing,
        prototypes,
        tools,
        vectorstores,
    )

_dynamic_imports = {
    "agents": "agentcore.components.agents",
    "data": "agentcore.components.data",
    "processing": "agentcore.components.processing",
    "vectorstores": "agentcore.components.vectorstores",
    "tools": "agentcore.components.tools",
    "models": "agentcore.components.models",
    "embeddings": "agentcore.components.embeddings",
    "helpers": "agentcore.components.helpers",
    "input_output": "agentcore.components.input_output",
    "logic": "agentcore.components.logic",
    "custom_component": "agentcore.components.custom_component",
    "prototypes": "agentcore.components.prototypes",
    "openai": "agentcore.components.openai",
    "anthropic": "agentcore.components.anthropic",
    "google": "agentcore.components.google",
    "azure": "agentcore.components.azure",
    "huggingface": "agentcore.components.huggingface",
    "ollama": "agentcore.components.ollama",
    "groq": "agentcore.components.groq",
    "Guardrails": "agentcore.components.Guardrails",
    "HumanInTheLoop": "agentcore.components.HumanInTheLoop",
    "cohere": "agentcore.components.cohere",
    "mistral": "agentcore.components.mistral",
    "deepseek": "agentcore.components.deepseek",
    "nvidia": "agentcore.components.nvidia",
    "amazon": "agentcore.components.amazon",
    "vertexai": "agentcore.components.vertexai",
    "xai": "agentcore.components.xai",
    "perplexity": "agentcore.components.perplexity",
    "openrouter": "agentcore.components.openrouter",
    "lmstudio": "agentcore.components.lmstudio",
    "sambanova": "agentcore.components.sambanova",
    "maritalk": "agentcore.components.maritalk",
    "novita": "agentcore.components.novita",
    "olivya": "agentcore.components.olivya",
    "notdiamond": "agentcore.components.notdiamond",
    "needle": "agentcore.components.needle",
    "cloudflare": "agentcore.components.cloudflare",
    "cloudgeometry": "agentcore.components.cloudgeometry",
    "baidu": "agentcore.components.baidu",
    "aiml": "agentcore.components.aiml",
    "ibm": "agentcore.components.ibm",
    "jira": "agentcore.components.jira",
    "crewai": "agentcore.components.crewai",
    "composio": "agentcore.components.composio",
    "mem0": "agentcore.components.mem0",
    "datastax": "agentcore.components.datastax",
    "cleanlab": "agentcore.components.cleanlab",
    "langwatch": "agentcore.components.langwatch",
    "icosacomputing": "agentcore.components.icosacomputing",
    "homeassistant": "agentcore.components.homeassistant",
    "hubspot": "agentcore.components.hubspot",
    "agentql": "agentcore.components.agentql",
    "assemblyai": "agentcore.components.assemblyai",
    "twelvelabs": "agentcore.components.twelvelabs",
    "docling": "agentcore.components.docling",
    "unstructured": "agentcore.components.unstructured",
    "redis": "agentcore.components.redis",
    "zep": "agentcore.components.zep",
    "bing": "agentcore.components.bing",
    "duckduckgo": "agentcore.components.duckduckgo",
    "serpapi": "agentcore.components.serpapi",
    "searchapi": "agentcore.components.searchapi",
    "tavily": "agentcore.components.tavily",
    "exa": "agentcore.components.exa",
    "glean": "agentcore.components.glean",
    "yahoosearch": "agentcore.components.yahoosearch",
    "apollo": "agentcore.components.apollo",
    "apify": "agentcore.components.apify",
    "arxiv": "agentcore.components.arxiv",
    "confluence": "agentcore.components.confluence",
    "firecrawl": "agentcore.components.firecrawl",
    "git": "agentcore.components.git",
    "wikipedia": "agentcore.components.wikipedia",
    "youtube": "agentcore.components.youtube",
    "scrapegraph": "agentcore.components.scrapegraph",
    "Notion": "agentcore.components.Notion",
    "wolframalpha": "agentcore.components.wolframalpha",
}

__all__: list[str] = [
    "Notion",
    "agentql",
    "agents",
    "aiml",
    "amazon",
    "anthropic",
    "apollo",
    "apify",
    "arxiv",
    "assemblyai",
    "azure",
    "baidu",
    "bing",
    "cleanlab",
    "cloudflare",
    "cloudgeometry",
    "cohere",
    "composio",
    "confluence",
    "crewai",
    "custom_component",
    "data",
    "datastax",
    "deepseek",
    "docling",
    "duckduckgo",
    "embeddings",
    "exa",
    "firecrawl",
    "git",
    "glean",
    "google",
    "groq",
    "Guardrails",
    "HumanInTheLoop",
    "helpers",
    "homeassistant",
    "hubspot",
    "huggingface",
    "ibm",
    "icosacomputing",
    "input_output",
    "jira",
    "langwatch",
    "lmstudio",
    "logic",
    "maritalk",
    "mem0",
    "mistral",
    "models",
    "needle",
    "notdiamond",
    "novita",
    "nvidia",
    "olivya",
    "ollama",
    "openai",
    "openrouter",
    "perplexity",
    "processing",
    "prototypes",
    "redis",
    "sambanova",
    "scrapegraph",
    "searchapi",
    "serpapi",
    "tavily",
    "tools",
    "twelvelabs",
    "unstructured",
    "vectorstores",
    "vertexai",
    "wikipedia",
    "wolframalpha",
    "xai",
    "yahoosearch",
    "youtube",
    "zep",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import component modules on attribute access.

    Args:
        attr_name (str): The attribute/module name to import.

    Returns:
        Any: The imported module or attribute.

    Raises:
        AttributeError: If the attribute is not a known component or cannot be imported.
    """
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        # Use import_mod as in LangChain, passing the module name and package
        result = import_mod(attr_name, "__module__", __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result  # Cache for future access
    return result


def __dir__() -> list[str]:
    """Return list of available attributes for tab-completion and dir()."""
    return list(__all__)


# Optional: Consistency check (can be removed in production)
_missing = set(__all__) - set(_dynamic_imports)
if _missing:
    msg = f"Missing dynamic import mapping for: {', '.join(_missing)}"
    raise ImportError(msg)
