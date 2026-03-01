"""Unified Embeddings component that reads models from the model_registry table (model_type='embedding')."""

from __future__ import annotations

import asyncio
import os
import threading

from loguru import logger

from agentcore.base.embeddings.model import LCEmbeddingsModel
from agentcore.field_typing import Embeddings
from agentcore.io import DropdownInput, IntInput

# Display label → DB key mapping (same as LLM registry)
PROVIDER_LABEL_TO_KEY = {
    "OpenAI": "openai",
    "Azure": "azure",
    "Google": "google",
    "Custom Model": "openai_compatible",
}
PROVIDER_KEY_TO_LABEL = {v: k for k, v in PROVIDER_LABEL_TO_KEY.items()}
PROVIDER_OPTIONS = list(PROVIDER_LABEL_TO_KEY.keys())

_sync_engine = None
_sync_engine_lock = threading.Lock()


def _get_sync_engine():
    """Return a dedicated synchronous SQLAlchemy engine (created once)."""
    global _sync_engine
    if _sync_engine is not None:
        return _sync_engine

    with _sync_engine_lock:
        if _sync_engine is not None:
            return _sync_engine

        from sqlalchemy import create_engine

        from agentcore.services.deps import get_db_service

        db_service = get_db_service()
        db_url = db_service.database_url
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "")

        _sync_engine = create_engine(db_url, pool_pre_ping=True, pool_size=3)
        logger.info(f"Created dedicated sync engine for embedding registry component: {db_url.split('@')[-1]}")
        return _sync_engine


def _run_async(coro):
    """Run an async coroutine from a synchronous context."""
    import concurrent.futures as _cf

    try:
        asyncio.get_running_loop()
        with _cf.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(coro)


def _fetch_embedding_models_for_provider(provider: str) -> list[str]:
    """Fetch active embedding models from the registry filtered by provider.

    Returns a list of strings formatted as 'display_name | model_name | uuid'.
    """
    if not provider:
        return []
    try:
        from agentcore.services.deps import get_db_service

        db_service = get_db_service()

        async def _query():
            from sqlalchemy import select

            from agentcore.services.database.models.model_registry.model import ModelRegistry

            async with db_service.with_session() as session:
                stmt = (
                    select(ModelRegistry)
                    .where(ModelRegistry.is_active.is_(True))
                    .where(ModelRegistry.provider == provider)
                    .where(ModelRegistry.model_type == "embedding")
                    .order_by(ModelRegistry.display_name)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [f"{r.display_name} | {r.model_name} | {r.id}" for r in rows]

        return _run_async(_query())
    except Exception as e:
        logger.warning(f"Could not fetch registry embeddings for provider {provider}: {e}")
        return []


def _get_registry_config(model_id: str) -> dict | None:
    """Fetch embedding model config using a dedicated sync engine."""
    from uuid import UUID

    from sqlalchemy.orm import Session

    from agentcore.services.database.models.model_registry.model import ModelRegistry
    from agentcore.utils.crypto import decrypt_api_key

    try:
        engine = _get_sync_engine()
        with Session(engine) as session:
            row = session.get(ModelRegistry, UUID(model_id))
            if row is None:
                logger.warning(f"Embedding model {model_id} not found in DB via sync engine")
                return None

            enc_key = os.getenv("MODEL_REGISTRY_ENCRYPTION_KEY", "")
            if not enc_key:
                import base64
                import hashlib

                raw = os.getenv("WEBUI_SECRET_KEY", "default-agentcore-registry-key")
                derived = hashlib.sha256(raw.encode()).digest()
                enc_key = base64.urlsafe_b64encode(derived).decode()

            config: dict = {
                "provider": row.provider,
                "model_name": row.model_name,
                "base_url": row.base_url,
                "environment": row.environment,
                "provider_config": row.provider_config or {},
                "default_params": row.default_params or {},
            }

            if row.api_key_encrypted and enc_key:
                config["api_key"] = decrypt_api_key(row.api_key_encrypted, enc_key)
            else:
                config["api_key"] = ""

            return config
    except Exception as e:
        logger.error(f"Failed to fetch registry config for embedding model {model_id}: {e}", exc_info=True)
        raise ValueError(f"Failed to load embedding model {model_id} from registry: {e}") from e


class RegistryEmbeddingsComponent(LCEmbeddingsModel):
    """A unified Embeddings component that dynamically loads models from the Model Registry.

    Users onboard embedding models via the Model Registry page. This component
    lets them pick a provider, then select a registered embedding model.
    """

    display_name: str = "Embeddings Model"
    description: str = "Select a provider and embedding model from the Model Registry."
    icon = "Binary"
    name = "RegistryEmbeddingsComponent"
    priority = 0

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Provider",
            info="Select the AI provider. Embedding models onboarded for this provider will appear below.",
            options=PROVIDER_OPTIONS,
            value="",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="registry_model",
            display_name="Registry Model",
            info="Select an embedding model from the Model Registry.",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="Override output embedding dimensions. Leave empty for model default.",
            advanced=True,
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Refresh dropdowns when provider changes or registry_model refresh is clicked."""
        if field_name == "provider":
            provider_key = PROVIDER_LABEL_TO_KEY.get(field_value, field_value)
            try:
                options = _fetch_embedding_models_for_provider(provider_key)
                build_config["registry_model"]["options"] = options if options else []
                build_config["registry_model"]["value"] = options[0] if options else ""
            except Exception as e:
                logger.warning(f"Error fetching embeddings for provider {provider_key}: {e}")
                build_config["registry_model"]["options"] = []
                build_config["registry_model"]["value"] = ""

        elif field_name == "registry_model":
            provider_label = build_config.get("provider", {}).get("value", "")
            provider_key = PROVIDER_LABEL_TO_KEY.get(provider_label, provider_label)
            if provider_key:
                try:
                    options = _fetch_embedding_models_for_provider(provider_key)
                    build_config["registry_model"]["options"] = options if options else []
                    if options and not build_config["registry_model"].get("value"):
                        build_config["registry_model"]["value"] = options[0]
                except Exception as e:
                    logger.warning(f"Error refreshing registry embeddings: {e}")
                    build_config["registry_model"]["options"] = []

        return build_config

    def build_embeddings(self) -> Embeddings:
        """Build a LangChain embeddings model from the selected registry entry."""
        selected = self.registry_model
        if not selected:
            msg = "No model selected. Please select a model from the Registry Model dropdown."
            raise ValueError(msg)

        parts = [p.strip() for p in selected.split("|")]
        if len(parts) < 3:
            msg = f"Invalid registry model format: {selected}. Please refresh the dropdown."
            raise ValueError(msg)

        model_id = parts[2]

        config = _get_registry_config(model_id)
        if config is None:
            msg = f"Embedding model {model_id} not found in registry or has been deleted."
            raise ValueError(msg)

        provider = config["provider"].lower()
        model_name = config["model_name"]
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "")
        provider_config = config.get("provider_config", {})
        default_params = config.get("default_params", {})

        dimensions = self.dimensions or default_params.get("dimensions") or None

        return self._build_provider_embeddings(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            provider_config=provider_config,
            dimensions=dimensions,
        )

    @staticmethod
    def _build_provider_embeddings(
        *,
        provider: str,
        model_name: str,
        api_key: str,
        base_url: str,
        provider_config: dict,
        dimensions: int | None,
    ) -> Embeddings:
        """Construct the appropriate LangChain embeddings model based on the provider."""
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            kwargs: dict = {"model": model_name, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            if dimensions:
                kwargs["dimensions"] = dimensions
            return OpenAIEmbeddings(**kwargs)

        if provider == "azure":
            from langchain_openai import AzureOpenAIEmbeddings

            kwargs = {
                "model": model_name,
                "azure_endpoint": base_url or provider_config.get("azure_endpoint", ""),
                "azure_deployment": provider_config.get("azure_deployment", model_name),
                "api_version": provider_config.get("api_version", "2025-10-01-preview"),
                "api_key": api_key,
            }
            if dimensions:
                kwargs["dimensions"] = dimensions
            return AzureOpenAIEmbeddings(**kwargs)

        if provider == "google":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            kwargs = {
                "model": model_name,
                "google_api_key": api_key,
            }
            if dimensions:
                kwargs["output_dimensionality"] = dimensions
            return GoogleGenerativeAIEmbeddings(**kwargs)

        if provider in ("openai_compatible", "groq", "anthropic"):
            from langchain_openai import OpenAIEmbeddings

            kwargs = {
                "model": model_name,
                "api_key": api_key or "not-needed",
            }
            if base_url:
                kwargs["base_url"] = base_url
            if dimensions:
                kwargs["dimensions"] = dimensions
            custom_headers = provider_config.get("custom_headers", {})
            if custom_headers:
                kwargs["default_headers"] = custom_headers
            return OpenAIEmbeddings(**kwargs)

        msg = f"Unsupported embedding provider: {provider}. Supported: openai, azure, google, openai_compatible"
        raise ValueError(msg)
