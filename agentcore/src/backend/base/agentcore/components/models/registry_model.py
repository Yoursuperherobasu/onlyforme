"""Unified Language Model component that reads models from the model_registry table."""

from __future__ import annotations

import asyncio
import concurrent.futures

import os
import threading

from loguru import logger
from pydantic.v1 import SecretStr

from agentcore.base.models.model import LCModelNode
from agentcore.field_typing import LanguageModel
from agentcore.field_typing.range_spec import RangeSpec
from agentcore.io import DropdownInput, IntInput, SliderInput

# Display label → DB key mapping
PROVIDER_LABEL_TO_KEY = {
    "OpenAI": "openai",
    "Azure OpenAI": "azure",
    "Anthropic": "anthropic",
    "Google": "google",
    "Groq": "groq",
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
        # Convert async URL (postgresql+psycopg) to sync-compatible URL
        db_url = db_service.database_url
        # psycopg (v3) supports both sync and async, so the same URL works
        # But if it uses an explicitly async driver, fall back to psycopg2
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "")

        _sync_engine = create_engine(db_url, pool_pre_ping=True, pool_size=3)
        logger.info(f"Created dedicated sync engine for registry component: {db_url.split('@')[-1]}")
        return _sync_engine


# ---------------------------------------------------------------------------
# Async helper for update_build_config (runs in HTTP request context)
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from a synchronous context, handling existing event loops.

    NOTE: import locally — components are loaded via exec() from string,
    so module-level imports may not be in scope.
    """
    import concurrent.futures as _cf

    try:
        asyncio.get_running_loop()
        with _cf.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(coro)


def _fetch_models_for_provider(provider: str) -> list[str]:
    """Fetch active models from the registry filtered by provider.

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
                    .order_by(ModelRegistry.display_name)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [f"{r.display_name} | {r.model_name} | {r.id}" for r in rows]

        return _run_async(_query())
    except Exception as e:
        logger.warning(f"Could not fetch registry models for provider {provider}: {e}")
        return []

# ---------------------------------------------------------------------------
# Synchronous config fetch for build_model() — uses dedicated sync engine
# ---------------------------------------------------------------------------
def _get_registry_config(model_id: str) -> dict | None:
    """Fetch model config using a dedicated sync engine (no async involvement)."""
    from uuid import UUID

    from sqlalchemy.orm import Session

    from agentcore.services.database.models.model_registry.model import ModelRegistry
    from agentcore.utils.crypto import decrypt_api_key

    try:
        engine = _get_sync_engine()
        with Session(engine) as session:
            row = session.get(ModelRegistry, UUID(model_id))
            if row is None:
                logger.warning(f"Model {model_id} not found in DB via sync engine")
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
                "capabilities": row.capabilities or {},
                "default_params": row.default_params or {},
            }

            if row.api_key_encrypted and enc_key:
                config["api_key"] = decrypt_api_key(row.api_key_encrypted, enc_key)
            else:
                config["api_key"] = ""

            return config
    except Exception as e:
        logger.error(f"Failed to fetch registry config for model {model_id}: {e}", exc_info=True)
        raise ValueError(f"Failed to load model {model_id} from registry: {e}") from e

class RegistryModelComponent(LCModelNode):
    """A unified Language Model component that dynamically loads models from the Model Registry.

    Users onboard models via the Model Registry page. This component
    lets them pick a provider, then select a registered model for that
    provider in the agent builder.
    """

    display_name: str = "Large Language Model"
    description: str = "Select a provider and model from the Model Registry to power your agent."
    icon = "BrainCircuit"
    name = "RegistryModelComponent"
    priority = 0

    inputs = [
        *LCModelNode._base_inputs,
        DropdownInput(
            name="provider",
            display_name="Provider",
            info="Select the AI provider. Models onboarded for this provider will appear below.",
            options=PROVIDER_OPTIONS,
            value="",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="registry_model",
            display_name="Registry Model",
            info="Select a model from the Model Registry.",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Controls randomness. Lower = more deterministic, higher = more creative.",
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Output Tokens",
            info="Maximum number of tokens to generate. Leave empty for model default.",
            advanced=True,
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Refresh dropdowns when provider changes or registry_model refresh is clicked."""
        if field_name == "provider":
            # Provider changed — translate label to DB key and fetch models
            provider_key = PROVIDER_LABEL_TO_KEY.get(field_value, field_value)
            try:
                options = _fetch_models_for_provider(provider_key)
                build_config["registry_model"]["options"] = options if options else []
                build_config["registry_model"]["value"] = options[0] if options else ""
            except Exception as e:
                logger.warning(f"Error fetching models for provider {provider_key}: {e}")
                build_config["registry_model"]["options"] = []
                build_config["registry_model"]["value"] = ""

        elif field_name == "registry_model":
            # Refresh button clicked — re-fetch models for the current provider
            provider_label = build_config.get("provider", {}).get("value", "")
            provider_key = PROVIDER_LABEL_TO_KEY.get(provider_label, provider_label)
            if provider_key:
                try:
                    options = _fetch_models_for_provider(provider_key)
                    build_config["registry_model"]["options"] = options if options else []
                    if options and not build_config["registry_model"].get("value"):
                        build_config["registry_model"]["value"] = options[0]
                except Exception as e:
                    logger.warning(f"Error refreshing registry models: {e}")
                    build_config["registry_model"]["options"] = []

        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        """Build a LangChain chat model from the selected registry entry."""
        selected = self.registry_model
        if not selected:
            msg = "No model selected. Please select a model from the Registry Model dropdown."
            raise ValueError(msg)

        # Parse the selection: "display_name | model_name | uuid"
        parts = [p.strip() for p in selected.split("|")]
        if len(parts) < 3:
            msg = f"Invalid registry model format: {selected}. Please refresh the dropdown."
            raise ValueError(msg)

        model_id = parts[2]

        # Fetch decrypted config from registry
        config = _get_registry_config(model_id)
        if config is None:
            msg = f"Model {model_id} not found in registry or has been deleted."
            raise ValueError(msg)

        provider = config["provider"].lower()
        model_name = config["model_name"]
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "")
        provider_config = config.get("provider_config", {})
        default_params = config.get("default_params", {})

        # Override with component-level settings if provided
        temperature = self.temperature if self.temperature is not None else default_params.get("temperature", 0.7)
        max_tokens = self.max_tokens or default_params.get("max_tokens") or None
        stream = self.stream

        return self._build_provider_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            provider_config=provider_config,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

    

    @staticmethod
    def _build_provider_model(
        *,
        provider: str,
        model_name: str,
        api_key: str,
        base_url: str,
        provider_config: dict,
        temperature: float,
        max_tokens: int | None,
        stream: bool,
    ) -> LanguageModel:
        """Construct the appropriate LangChain model based on the provider."""
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            kwargs: dict = {
                "model": model_name,
                "api_key": api_key,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "streaming": stream,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return ChatOpenAI(**kwargs)

        if provider == "azure":
            from langchain_openai import AzureChatOpenAI

            return AzureChatOpenAI(
                azure_deployment=provider_config.get("azure_deployment", model_name),
                azure_endpoint=base_url or provider_config.get("azure_endpoint", ""),
                api_key=api_key,
                api_version=provider_config.get("api_version", "2025-10-01-preview"),
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=stream,
            )

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_name,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
                streaming=stream,
            )

        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

        if provider == "groq":
            from langchain_groq import ChatGroq

            kwargs = {
                "model": model_name,
                "api_key": SecretStr(api_key).get_secret_value() if api_key else "",
                "temperature": temperature,
                "max_tokens": max_tokens,
                "streaming": stream,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return ChatGroq(**kwargs)

        if provider == "openai_compatible":
            from langchain_openai import ChatOpenAI

            custom_headers = provider_config.get("custom_headers", {})
            kwargs = {
                "model": model_name,
                "api_key": api_key or "not-needed",
                "base_url": base_url,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "streaming": stream,
            }
            if custom_headers:
                kwargs["default_headers"] = custom_headers
            return ChatOpenAI(**kwargs)

        msg = f"Unsupported provider: {provider}. Supported: openai, azure, anthropic, google, groq, openai_compatible"
        raise ValueError(msg)