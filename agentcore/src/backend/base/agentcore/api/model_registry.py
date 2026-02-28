"""REST endpoints for the model registry."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.model_registry.model import (
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)
from agentcore.services import model_registry_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models/registry", tags=["Model Registry"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ModelRegistryRead])
async def list_registry_models(
    session: DbSession,
    current_user: CurrentActiveUser,
    provider: str | None = None,
    environment: str | None = None,
    model_type: str | None = None,
    active_only: bool = True,
):
    """List all registered models, optionally filtered by provider, environment, and/or model type."""
    return await model_registry_service.get_models(
        session, provider=provider, environment=environment, model_type=model_type, active_only=active_only
    )


@router.post("/", response_model=ModelRegistryRead, status_code=201)
async def create_registry_model(
    body: ModelRegistryCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Register a new model."""
    # Tag who created it
    if not body.created_by and current_user:
        body.created_by = current_user.username
    return await model_registry_service.create_model(session, body)


@router.get("/{model_id}", response_model=ModelRegistryRead)
async def get_registry_model(
    model_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get a single registered model by ID."""
    model = await model_registry_service.get_model(session, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/{model_id}", response_model=ModelRegistryRead)
async def update_registry_model(
    model_id: UUID,
    body: ModelRegistryUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Update an existing registered model."""
    model = await model_registry_service.update_model(session, model_id, body)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_registry_model(
    model_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a registered model."""
    deleted = await model_registry_service.delete_model(session, model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_model_connection(
    body: TestConnectionRequest,
    current_user: CurrentActiveUser,
):
    """Build the provider, send a simple message, and report success/failure + latency."""
    try:
        provider_name = body.provider.lower()
        provider_config: dict = body.provider_config or {}
        api_key = body.api_key or ""
        base_url = body.base_url or ""

        # Build a minimal LangChain model for the given provider and invoke it
        model = _build_test_model(
            provider_name=provider_name,
            model_name=body.model_name,
            api_key=api_key,
            base_url=base_url,
            provider_config=provider_config,
        )

        from langchain_core.messages import HumanMessage

        start = time.perf_counter()
        ai_message = await model.ainvoke([HumanMessage(content="Hello")])
        latency_ms = (time.perf_counter() - start) * 1000

        content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        return TestConnectionResponse(
            success=True,
            message=f"Model responded: {content[:100]}",
            latency_ms=round(latency_ms, 1),
        )
    except Exception as e:
        logger.warning("Test connection failed for %s/%s: %s", body.provider, body.model_name, e)
        return TestConnectionResponse(success=False, message=str(e))


def _build_test_model(
    *,
    provider_name: str,
    model_name: str,
    api_key: str,
    base_url: str,
    provider_config: dict,
):
    """Construct a LangChain chat model for test-connection purposes."""
    if provider_name == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {"model": model_name, "api_key": api_key, "max_tokens": 50, "streaming": False}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    if provider_name == "azure":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=provider_config.get("azure_deployment", model_name),
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=provider_config.get("api_version", "2024-02-15-preview"),
            max_tokens=50,
            streaming=False,
        )

    if provider_name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            max_tokens=50,
            streaming=False,
        )

    if provider_name == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            max_output_tokens=50,
        )

    if provider_name == "groq":
        from langchain_groq import ChatGroq

        kwargs = {"model": model_name, "api_key": api_key, "max_tokens": 50, "streaming": False}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatGroq(**kwargs)

    if provider_name == "openai_compatible":
        from langchain_openai import ChatOpenAI

        custom_headers = provider_config.get("custom_headers", {})
        kwargs = {
            "model": model_name,
            "api_key": api_key or "not-needed",
            "base_url": base_url,
            "max_tokens": 50,
            "streaming": False,
        }
        if custom_headers:
            kwargs["default_headers"] = custom_headers
        return ChatOpenAI(**kwargs)

    msg = f"Unsupported provider for test connection: {provider_name}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Test embedding connection
# ---------------------------------------------------------------------------


@router.post("/test-embedding-connection", response_model=TestConnectionResponse)
async def test_embedding_connection(
    body: TestConnectionRequest,
    current_user: CurrentActiveUser,
):
    """Build an embedding provider, embed a test string, and report success/failure + latency."""
    try:
        provider_name = body.provider.lower()
        provider_config: dict = body.provider_config or {}
        api_key = body.api_key or ""
        base_url = body.base_url or ""

        embeddings = _build_test_embeddings(
            provider_name=provider_name,
            model_name=body.model_name,
            api_key=api_key,
            base_url=base_url,
            provider_config=provider_config,
        )

        start = time.perf_counter()
        result = await embeddings.aembed_query("Hello")
        latency_ms = (time.perf_counter() - start) * 1000

        dim = len(result) if result else 0
        return TestConnectionResponse(
            success=True,
            message=f"Embedding generated: {dim} dimensions",
            latency_ms=round(latency_ms, 1),
        )
    except Exception as e:
        logger.warning("Test embedding connection failed for %s/%s: %s", body.provider, body.model_name, e)
        return TestConnectionResponse(success=False, message=str(e))


def _build_test_embeddings(
    *,
    provider_name: str,
    model_name: str,
    api_key: str,
    base_url: str,
    provider_config: dict,
):
    """Construct a LangChain embeddings model for test-connection purposes."""
    if provider_name == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs: dict = {"model": model_name, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)

    if provider_name == "azure":
        from langchain_openai import AzureOpenAIEmbeddings

        return AzureOpenAIEmbeddings(
            model=model_name,
            azure_endpoint=base_url or provider_config.get("azure_endpoint", ""),
            azure_deployment=provider_config.get("azure_deployment", model_name),
            api_version=provider_config.get("api_version", "2025-10-01-preview"),
            api_key=api_key,
        )

    if provider_name == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=api_key,
        )

    if provider_name in ("openai_compatible", "groq", "anthropic"):
        from langchain_openai import OpenAIEmbeddings

        kwargs = {
            "model": model_name,
            "api_key": api_key or "not-needed",
        }
        if base_url:
            kwargs["base_url"] = base_url
        custom_headers = provider_config.get("custom_headers", {})
        if custom_headers:
            kwargs["default_headers"] = custom_headers
        return OpenAIEmbeddings(**kwargs)

    msg = f"Unsupported provider for embedding test connection: {provider_name}"
    raise ValueError(msg)