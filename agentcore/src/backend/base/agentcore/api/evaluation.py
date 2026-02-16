"""
Evaluation API Endpoints - Enhanced Version

Features:
- User isolation (only access own scores/traces)
- Integration with existing observability
- LLM-as-a-Judge with proper trace fetching
- Proper error handling
"""

import os
import json
import asyncio
import time
import re
from datetime import datetime, timezone, timedelta
from typing import Annotated, Any, List, Optional, Dict, Union
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy import or_
from agentcore.services.deps import session_scope
# `flow` objects are stored as `Agent` in the DB; import AccessTypeEnum and
# alias `Agent` to `Flow` so the rest of the module can keep using `Flow`.
from agentcore.services.database.models.agent.model import AccessTypeEnum, Agent as Flow

from agentcore.services.auth.utils import get_current_active_user
from agentcore.services.database.models.user.model import User
from agentcore.api.utils import DbSession
from agentcore.api.observability import fetch_traces_from_langfuse, fetch_scores_for_trace

# Try importing litellm for the judge
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None
    LITELLM_AVAILABLE = False
    logger.warning("LiteLLM not installed. LLM Judge features will be disabled.")

# Try importing OpenAI as a fallback for the judge when LiteLLM isn't present
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    openai = None
    OPENAI_AVAILABLE = False

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

_LITELLM_STD_LOGGING_PATCHED = False

# Persistent evaluator configs stored in the database (see Evaluator model)
from agentcore.services.database.models.evaluator.model import Evaluator  # noqa: E402


# =============================================================================
# Response Models
# =============================================================================

class ScoreResponse(BaseModel):
    """Represents a single evaluation score."""
    id: str
    trace_id: str
    agent_name: str | None = None
    name: str
    value: float
    source: str  # "ANNOTATION" (human), "API" (llm judge)
    comment: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    observation_id: str | None = None
    config_id: str | None = None


class CreateScoreRequest(BaseModel):
    """Request to create a manual score (annotation)."""
    trace_id: str
    name: str
    value: float = Field(..., ge=0.0, le=1.0, description="Score between 0 and 1")
    comment: str | None = None
    observation_id: str | None = None


class JudgeRequest(BaseModel):
    """Request to run an LLM judge on a trace."""
    trace_id: str
    criteria: str = Field(..., description="The evaluation criteria (e.g., 'Is the answer helpful?')")
    model: str = "gpt-4o"
    name: str | None = None  # Defaults to criteria if not provided


class JudgeConfig(BaseModel):
    """Saved judge configuration for reuse."""
    id: str | None = None
    name: str
    criteria: str
    model: str = "gpt-4o"
    # target: 'existing' -> evaluate matching existing traces now
    #         'new' -> save evaluator to apply to future traces (not executed immediately)
    target: str = Field("existing", description="'existing' or 'new'")
    # Filtering options to select traces
    trace_id: Optional[str] = None
    agent_id: Optional[str] = None
    flow_name: Optional[str] = None
    session_id: Optional[str] = None
    project_name: Optional[str] = None
    ts_from: Optional[str] = None  # ISO timestamp
    ts_to: Optional[str] = None
    user_id: str | None = None


class EvaluatorCreateRequest(BaseModel):
    name: str
    criteria: str
    model: str = "gpt-4o"
    preset_id: Optional[str] = None
    # target may be a single string ('existing'|'new') or a list like ['existing','new']
    target: Optional[Union[str, List[str]]] = Field(default="existing")
    # Ground truth for evaluation (required for some presets like 'correctness')
    ground_truth: Optional[str] = None
    # Optional filters for selecting traces when target includes 'existing'
    trace_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    flow_name: Optional[str] = None
    session_id: Optional[str] = None
    project_name: Optional[str] = None
    ts_from: Optional[str] = None  # ISO timestamp
    ts_to: Optional[str] = None
    model_api_key: Optional[str] = None


class EvaluatorResponse(BaseModel):
    id: str
    name: str
    criteria: str
    model: str
    user_id: str | None = None
    preset_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    target: Optional[List[str]] = None
    ground_truth: Optional[str] = None
    trace_id: Optional[str] = None
    agent_id: Optional[str] = None
    flow_name: Optional[str] = None
    session_id: Optional[str] = None
    project_name: Optional[str] = None
    ts_from: Optional[str] = None
    ts_to: Optional[str] = None
    created_at: Optional[str] = None


class AnalyticsMetric(BaseModel):
    """Aggregated stats for a specific score name."""
    name: str
    count: int
    average: float
    min: float
    max: float
    p50: float | None = None
    p90: float | None = None


class EvaluationAnalyticsResponse(BaseModel):
    """Analytics response for the dashboard."""
    total_scores: int
    by_name: List[AnalyticsMetric]


class TraceForReview(BaseModel):
    """Trace info for annotation queue."""
    id: str
    name: str | None
    timestamp: datetime | None
    input: Any | None
    output: Any | None
    session_id: str | None
    flow_name: str | None
    has_scores: bool = False
    score_count: int = 0


# =============================================================================
# Helper Functions
# =============================================================================

def get_langfuse_client():
    """Get a Langfuse client using environment variables."""
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")

    if not all([secret_key, public_key, base_url]):
        return None

    try:
        from langfuse import Langfuse
        if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
            os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST")

        client = Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=base_url
        )
        api_obj = getattr(client, "api", None)
        client._is_v3 = bool(
            hasattr(client, "auth_check")
            or (
                api_obj
                and (
                    hasattr(api_obj, "trace")
                    or hasattr(api_obj, "traces")
                )
            )
        )
        return client
    except ImportError:
        logger.warning("Langfuse package not installed")
        return None
    except Exception as e:
        logger.error("Failed to create Langfuse client: {}", str(e))
        return None


def get_attr(obj, *attrs, default=None):
    """Get attribute from object or dict, trying multiple attribute names."""
    for attr in attrs:
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if val is not None:
                return val
        if isinstance(obj, dict) and attr in obj:
            val = obj[attr]
            if val is not None:
                return val
    return default


def _ensure_litellm_logging_compatibility_patch() -> None:
    """Patch LiteLLM standard logging cold-storage hook to avoid proxy-only imports."""
    global _LITELLM_STD_LOGGING_PATCHED

    if not LITELLM_AVAILABLE or _LITELLM_STD_LOGGING_PATCHED:
        return

    try:
        from litellm.litellm_core_utils import litellm_logging as _litellm_logging

        setup_cls = getattr(_litellm_logging, "StandardLoggingPayloadSetup", None)
        if setup_cls is None or not hasattr(setup_cls, "_generate_cold_storage_object_key"):
            _LITELLM_STD_LOGGING_PATCHED = True
            return

        def _disabled_cold_storage_key(*args, **kwargs):
            return None

        setup_cls._generate_cold_storage_object_key = staticmethod(_disabled_cold_storage_key)
        _LITELLM_STD_LOGGING_PATCHED = True
        logger.debug("Applied LiteLLM logging compatibility patch: disabled cold-storage object key generation.")
    except Exception as exc:
        logger.debug("Could not apply LiteLLM logging compatibility patch: {}", str(exc))


def parse_trace_data(trace) -> Dict[str, Any]:
    """Extract and normalize trace data."""
    return {
        "id": get_attr(trace, 'id', 'trace_id', 'traceId'),
        "name": get_attr(trace, 'name', 'display_name', 'trace_name'),
        "timestamp": get_attr(trace, 'timestamp', 'createdAt', 'created_at'),
        "input": get_attr(trace, 'input', 'inputs', 'input_data', 'generation', 'query'),
        "output": get_attr(trace, 'output', 'outputs', 'generation', 'text_output', 'response'),
        "session_id": get_attr(trace, 'session_id', 'sessionId'),
        "user_id": get_attr(trace, 'user_id', 'userId', 'sender', 'user'),
        "metadata": get_attr(trace, 'metadata', 'meta'),
        "tags": get_attr(trace, 'tags', 'labels'),
    }


_KNOWN_LITELLM_PROVIDERS = {
    "openai",
    "azure",
    "anthropic",
    "groq",
    "gemini",
    "google",
    "vertex_ai",
    "bedrock",
    "openrouter",
    "mistral",
    "cohere",
    "huggingface",
    "ollama",
    "togetherai",
    "fireworks_ai",
    "xai",
    "replicate",
    "perplexity",
    "sambanova",
    "deepseek",
    "watsonx",
}


def _split_known_provider_prefix(model: str) -> tuple[str | None, str]:
    """Split known LiteLLM provider prefix from model string if present."""
    value = str(model or "").strip()
    if not value or "/" not in value:
        return None, value
    prefix, tail = value.split("/", 1)
    if prefix.strip().lower() in _KNOWN_LITELLM_PROVIDERS:
        return prefix.strip().lower(), tail.strip()
    return None, value


def _infer_litellm_provider(model: str, api_key: str | None = None) -> str | None:
    """Infer LiteLLM provider from model/API key/environment."""
    explicit_provider = os.getenv("LITELLM_DEFAULT_PROVIDER")
    if explicit_provider:
        value = explicit_provider.strip().lower()
        if value:
            return value

    prefixed_provider, _ = _split_known_provider_prefix(model)
    if prefixed_provider:
        return prefixed_provider

    key = str(api_key or "").strip()
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("sk-or-"):
        return "openrouter"
    if key.startswith("hf_"):
        return "huggingface"
    if key.startswith("xai-"):
        return "xai"
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-"):
        return "openai"

    model_lower = str(model or "").strip().lower()
    if not model_lower:
        return None
    if model_lower.startswith(("gpt-", "o1", "o3", "o4", "text-embedding-")):
        return "openai"
    if "claude" in model_lower:
        return "anthropic"
    if "gemini" in model_lower:
        return "gemini"
    return None


def _normalize_model_name_for_provider(model_name: str, provider_hint: str | None = None) -> str:
    """Normalize human-entered model names into provider-friendly ids."""
    value = str(model_name or "").strip()
    if not value:
        return value

    lowered = value.lower()
    if lowered.startswith("models/"):
        value = value.split("/", 1)[1].strip()

    provider = (provider_hint or "").strip().lower()
    if provider in {"gemini", "google", "vertex_ai"}:
        # Gemini/Google model ids are slug-like (e.g. gemini-2.5-flash-lite).
        value = value.replace("_", "-")
        value = re.sub(r"\s+", "-", value.strip())
        value = re.sub(r"[^A-Za-z0-9._:\-]", "-", value)
        value = re.sub(r"-{2,}", "-", value).strip("-").lower()
        return value

    # Generic cleanup for obvious display labels containing spaces.
    if " " in value:
        compact = re.sub(r"\s+", "-", value.strip())
        compact = re.sub(r"[^A-Za-z0-9._:/\-]", "-", compact)
        compact = re.sub(r"-{2,}", "-", compact).strip("-")
        if compact:
            return compact
    return value


def _build_model_name_variants(model_name: str, provider_hint: str | None = None) -> list[str]:
    """Build ordered model-name variants from a user-entered model field."""
    raw = str(model_name or "").strip()
    if not raw:
        return []

    variants: list[str] = []
    normalized = _normalize_model_name_for_provider(raw, provider_hint)
    if normalized and normalized != raw:
        variants.append(normalized)
    variants.append(raw)

    if "/" in raw:
        _, tail = raw.split("/", 1)
        tail = tail.strip()
        if tail:
            tail_normalized = _normalize_model_name_for_provider(tail, provider_hint)
            if tail_normalized and tail_normalized not in variants:
                variants.append(tail_normalized)
            if tail not in variants:
                variants.append(tail)

    deduped: list[str] = []
    seen: set[str] = set()
    for value in variants:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _build_litellm_model_candidates(model: str, api_key: str | None = None) -> list[str]:
    """Build model candidates for LiteLLM retries with provider inference."""
    raw = str(model or "").strip()
    if not raw:
        return []

    provider, raw_tail = _split_known_provider_prefix(raw)
    inferred_provider = _infer_litellm_provider(raw, api_key)
    provider_hint = provider or inferred_provider
    candidates: list[str] = []

    def add_candidate(value: str) -> None:
        value = value.strip()
        if value and value not in candidates:
            candidates.append(value)

    if provider:
        tail_variants = _build_model_name_variants(raw_tail, provider_hint=provider)
        for tail in tail_variants:
            add_candidate(f"{provider}/{tail}")
        add_candidate(raw)
    else:
        name_variants = _build_model_name_variants(raw, provider_hint=provider_hint)
        if inferred_provider:
            for name in name_variants:
                add_candidate(f"{inferred_provider}/{name}")
        for name in name_variants:
            add_candidate(name)

    # OpenAI-compatible fallback for custom model names when base URL is configured.
    openai_base = os.getenv("OPENAI_API_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if not provider and openai_base:
        for name in _build_model_name_variants(raw, provider_hint="openai"):
            add_candidate(f"openai/{name}")

    return candidates


def _is_litellm_provider_error(exc: Exception) -> bool:
    """Return True when LiteLLM error indicates provider/model prefix mismatch."""
    message = str(exc).lower()
    return (
        "llm provider not provided" in message
        or "pass in the llm provider" in message
        or "provider not found" in message
        or "unknown provider" in message
    )


def _is_litellm_retryable_model_error(exc: Exception) -> bool:
    """Return True when retrying with alternate model candidates may succeed."""
    if _is_litellm_provider_error(exc):
        return True

    message = str(exc).lower()
    return (
        "unexpected model name format" in message
        or "generatecontentrequest.model" in message
        or "invalid_argument" in message
        or "invalid model" in message
        or "model not found" in message
        or "unknown model" in message
    )


def _resolve_api_base_for_model(model: str) -> str | None:
    """Resolve provider-specific API base from environment when available."""
    provider, _ = _split_known_provider_prefix(model)
    # Global override first.
    global_base = os.getenv("LITELLM_API_BASE")
    if global_base:
        return global_base

    if provider == "openai":
        return os.getenv("OPENAI_API_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if provider == "groq":
        return os.getenv("GROQ_API_BASE_URL") or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_BASE_URL")
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_BASE_URL") or "https://openrouter.ai/api/v1"
    if provider in {"gemini", "google", "vertex_ai"}:
        return (
            os.getenv("GEMINI_API_BASE_URL")
            or os.getenv("GOOGLE_API_BASE_URL")
            or os.getenv("VERTEX_API_BASE_URL")
        )
    return None


def _resolve_openai_fallback_api_key(model: str, explicit_api_key: str | None = None) -> str | None:
    """Resolve API key for OpenAI SDK fallback based on model/provider."""
    value = str(explicit_api_key or "").strip()
    if value:
        return value

    provider = _infer_litellm_provider(model)
    env_by_provider: dict[str, list[str]] = {
        "openai": ["OPENAI_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "vertex_ai": ["VERTEX_API_KEY", "GOOGLE_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "cohere": ["COHERE_API_KEY"],
        "togetherai": ["TOGETHERAI_API_KEY", "TOGETHER_API_KEY"],
        "fireworks_ai": ["FIREWORKS_API_KEY"],
        "xai": ["XAI_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "perplexity": ["PERPLEXITY_API_KEY"],
        "sambanova": ["SAMBANOVA_API_KEY"],
    }

    env_names = env_by_provider.get(provider or "", [])
    env_names = list(dict.fromkeys([*env_names, "OPENAI_API_KEY"]))
    for env_name in env_names:
        env_value = str(os.getenv(env_name) or "").strip()
        if env_value:
            return env_value
    return None


def _model_name_for_openai_fallback(model: str) -> str:
    """Strip provider prefixes (e.g. 'groq/') for OpenAI-compatible SDK calls."""
    _, tail = _split_known_provider_prefix(model)
    value = tail.strip() if tail else str(model or "").strip()
    return value or str(model or "").strip()


def _is_openai_retryable_model_error(exc: Exception) -> bool:
    """Return True when retrying with another model candidate may succeed."""
    message = str(exc).lower()
    return (
        "model not found" in message
        or "unknown model" in message
        or "invalid model" in message
        or "does not exist" in message
        or "unexpected model name format" in message
        or "llm provider not provided" in message
        or "provider not found" in message
        or "generatecontentrequest.model" in message
    )


def _is_openai_response_format_error(exc: Exception) -> bool:
    """Return True when provider rejects JSON response_format."""
    message = str(exc).lower()
    return "response_format" in message or "json_object" in message


def _extract_openai_chat_content(resp: Any) -> str:
    """Extract message content from OpenAI chat completion response variants."""
    choices = resp.get("choices", []) if isinstance(resp, dict) else getattr(resp, "choices", [])
    if not choices:
        raise RuntimeError("OpenAI judge returned no choices")

    first_choice = choices[0]
    if isinstance(first_choice, dict):
        message = first_choice.get("message", {}) or {}
        content = message.get("content")
    else:
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None

    if isinstance(content, list):
        # Some OpenAI-compatible providers return structured content blocks.
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if text:
                text_parts.append(str(text))
        content = "".join(text_parts)

    if content is None:
        raise RuntimeError("OpenAI judge returned empty content")
    return str(content)


async def _call_openai_judge_completion(
    *,
    model_candidates: list[str],
    model_api_key: str | None,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, str]:
    """Call OpenAI SDK (v1/v2 or legacy) with retries across model candidates."""
    if openai is None:
        raise RuntimeError("OpenAI SDK not available")

    last_error: Exception | None = None
    for candidate_model in model_candidates:
        request_model = _model_name_for_openai_fallback(candidate_model)
        api_base = _resolve_api_base_for_model(candidate_model)
        api_key = _resolve_openai_fallback_api_key(candidate_model, explicit_api_key=model_api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            if hasattr(openai, "AsyncOpenAI"):
                client_kwargs: dict[str, Any] = {}
                if api_key:
                    client_kwargs["api_key"] = api_key
                if api_base:
                    client_kwargs["base_url"] = api_base
                async_client = openai.AsyncOpenAI(**client_kwargs)
                try:
                    resp = await async_client.chat.completions.create(
                        model=request_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                    )
                except Exception as response_format_exc:
                    if not _is_openai_response_format_error(response_format_exc):
                        raise
                    resp = await async_client.chat.completions.create(
                        model=request_model,
                        messages=messages,
                    )
                finally:
                    close_func = getattr(async_client, "close", None)
                    if callable(close_func):
                        try:
                            await close_func()
                        except Exception:
                            pass
            elif hasattr(openai, "OpenAI"):
                client_kwargs = {}
                if api_key:
                    client_kwargs["api_key"] = api_key
                if api_base:
                    client_kwargs["base_url"] = api_base

                def _sync_call_v1():
                    sync_client = openai.OpenAI(**client_kwargs)
                    try:
                        try:
                            return sync_client.chat.completions.create(
                                model=request_model,
                                messages=messages,
                                response_format={"type": "json_object"},
                            )
                        except Exception as response_format_exc:
                            if not _is_openai_response_format_error(response_format_exc):
                                raise
                            return sync_client.chat.completions.create(
                                model=request_model,
                                messages=messages,
                            )
                    finally:
                        close_func = getattr(sync_client, "close", None)
                        if callable(close_func):
                            try:
                                close_func()
                            except Exception:
                                pass

                resp = await asyncio.to_thread(_sync_call_v1)
            else:
                if api_key:
                    openai.api_key = api_key
                if api_base:
                    openai.api_base = api_base

                chat_completion = getattr(openai, "ChatCompletion", None)
                if chat_completion and hasattr(chat_completion, "acreate"):
                    resp = await chat_completion.acreate(
                        model=request_model,
                        messages=messages,
                    )
                elif chat_completion and hasattr(chat_completion, "create"):
                    def _sync_call_legacy():
                        return chat_completion.create(
                            model=request_model,
                            messages=messages,
                        )

                    resp = await asyncio.to_thread(_sync_call_legacy)
                else:
                    raise RuntimeError("OpenAI SDK does not expose a supported chat completion API")

            content = _extract_openai_chat_content(resp)
            return content, request_model
        except Exception as e:
            last_error = e
            logger.warning("OpenAI judge call failed for model={}: {}", candidate_model, str(e))
            if _is_openai_retryable_model_error(e):
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI judge call failed without a response")


def _submit_score_to_langfuse(
    client: Any,
    *,
    trace_id: str,
    name: str,
    value: float,
    comment: str | None = None,
    observation_id: str | None = None,
    source: str | None = None,
) -> None:
    """Submit score using SDK-compatible method across Langfuse versions."""
    payload: Dict[str, Any] = {
        "trace_id": trace_id,
        "name": name,
        "value": value,
        "comment": comment,
    }
    if observation_id:
        payload["observation_id"] = observation_id
    if source:
        payload["source"] = source

    payload_variants = [payload]
    if "source" in payload:
        payload_variants.append({k: v for k, v in payload.items() if k != "source"})
    if "observation_id" in payload:
        payload_variants.append({k: v for k, v in payload.items() if k != "observation_id"})
    if "source" in payload and "observation_id" in payload:
        payload_variants.append({k: v for k, v in payload.items() if k not in {"source", "observation_id"}})

    def _call_with_compatible_kwargs(func) -> bool:
        last_error: TypeError | None = None
        for kwargs in payload_variants:
            try:
                func(**kwargs)
                return True
            except TypeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return False

    # v2-style helper
    if hasattr(client, "score"):
        if _call_with_compatible_kwargs(client.score):
            return

    # v3-style helper
    if hasattr(client, "create_score"):
        if _call_with_compatible_kwargs(client.create_score):
            return

    # Direct API fallbacks (SDK internals)
    if hasattr(client, "api"):
        api_obj = getattr(client, "api")
        for attr in ("score", "scores"):
            score_api = getattr(api_obj, attr, None)
            if score_api and hasattr(score_api, "create"):
                if _call_with_compatible_kwargs(score_api.create):
                    return

    if hasattr(client, "client") and hasattr(client.client, "scores"):
        scores_client = client.client.scores
        if hasattr(scores_client, "create"):
            if _call_with_compatible_kwargs(scores_client.create):
                return

    raise RuntimeError("No supported score submission method found on Langfuse client")


def _extract_trace_run_id(trace_dict: Dict[str, Any]) -> str | None:
    """Extract run identifier from trace metadata/tags."""
    metadata = trace_dict.get("metadata")
    if isinstance(metadata, dict):
        run_id = metadata.get("run_id") or metadata.get("runId")
        if run_id:
            return str(run_id)

    tags = trace_dict.get("tags") or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("run_id:"):
                value = tag.split(":", 1)[1].strip()
                if value:
                    return value
    return None


def _extract_trace_user_id(trace_dict: Dict[str, Any]) -> str | None:
    """Extract user id from top-level fields or metadata/tags."""
    user_id = trace_dict.get("user_id")
    if user_id:
        return str(user_id)

    metadata = trace_dict.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("user_id") or metadata.get("userId")
        if value:
            return str(value)

    tags = trace_dict.get("tags") or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("user_id:"):
                value = tag.split(":", 1)[1].strip()
                if value:
                    return value
    return None


def _normalize_agent_id(agent_id: str | None) -> str | None:
    """Normalize flow identifiers from UI/API inputs."""
    if not agent_id:
        return None
    value = str(agent_id).strip()
    if value.startswith("lb:"):
        value = value.split("lb:", 1)[1]
    return value or None


def _normalize_targets(target: Union[str, List[str], None]) -> List[str]:
    """Normalize target input to a lowercase list."""
    if target is None:
        return ["existing"]
    if isinstance(target, str):
        values = [target]
    elif isinstance(target, list):
        values = target
    else:
        values = []
    normalized = [str(t).strip().lower() for t in values if str(t).strip()]
    return list(dict.fromkeys(normalized))


def _normalize_agent_ids(agent_ids: Optional[List[str]]) -> List[str]:
    """Normalize and de-duplicate flow ids."""
    if not agent_ids:
        return []
    normalized: List[str] = []
    for agent_id in agent_ids:
        value = _normalize_agent_id(agent_id)
        if value:
            normalized.append(value)
    return list(dict.fromkeys(normalized))


def _extract_trace_agent_id(trace_dict: Dict[str, Any]) -> str | None:
    """Extract flow id from trace metadata/tags."""
    metadata = trace_dict.get("metadata")
    if isinstance(metadata, dict):
        agent_id = _normalize_agent_id(metadata.get("agent_id") or metadata.get("flowId"))
        if agent_id:
            return agent_id

    tags = trace_dict.get("tags") or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("agent_id:"):
                agent_id = _normalize_agent_id(tag.split(":", 1)[1])
                if agent_id:
                    return agent_id
    return None


def _extract_trace_flow_name(trace_dict: Dict[str, Any]) -> str | None:
    """Extract flow name from trace metadata/tags/name."""
    metadata = trace_dict.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("flow_name") or metadata.get("flowName")
        if value:
            return str(value)

    tags = trace_dict.get("tags") or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("flow_name:"):
                return tag.split(":", 1)[1]

    name = trace_dict.get("name")
    return str(name) if name else None


def _extract_trace_project_name(trace_dict: Dict[str, Any]) -> str | None:
    """Extract project name from trace metadata/tags."""
    metadata = trace_dict.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("project_name") or metadata.get("projectName")
        if value:
            return str(value)

    tags = trace_dict.get("tags") or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("project_name:"):
                return tag.split(":", 1)[1]
    return None


def _parse_trace_timestamp(value: Any) -> datetime | None:
    """Parse trace timestamp from datetime/string/epoch variants."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        epoch = float(value)
        # Handle millisecond epoch values.
        if epoch > 10_000_000_000:
            epoch = epoch / 1000.0
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _trace_matches_evaluator_filters(
    trace_dict: Dict[str, Any],
    *,
    trace_id: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
    agent_ids: Optional[List[str]] = None,
    flow_name: str | None = None,
    project_name: str | None = None,
    ts_from: datetime | None = None,
    ts_to: datetime | None = None,
) -> bool:
    """Check whether a trace satisfies evaluator filters."""
    trace_trace_id = str(trace_dict.get("id") or "")
    trace_run_id = _extract_trace_run_id(trace_dict)
    trace_session_id = str(trace_dict.get("session_id") or "")
    trace_agent_id = _extract_trace_agent_id(trace_dict)
    trace_flow_name = _extract_trace_flow_name(trace_dict) or ""
    trace_project_name = _extract_trace_project_name(trace_dict) or ""
    trace_ts = _parse_trace_timestamp(trace_dict.get("timestamp"))

    normalized_agent_id = _normalize_agent_id(agent_id)
    normalized_agent_ids = set(_normalize_agent_ids(agent_ids))

    if trace_id and str(trace_id) not in {trace_trace_id, str(trace_run_id or "")}:
        return False
    if session_id and str(session_id) != trace_session_id:
        return False

    # Strict flow filtering: if filters are present and trace does not expose a matching agent_id, reject.
    if normalized_agent_id:
        if not trace_agent_id or trace_agent_id != normalized_agent_id:
            return False
    if normalized_agent_ids:
        if not trace_agent_id or trace_agent_id not in normalized_agent_ids:
            return False

    if flow_name and flow_name.lower() not in trace_flow_name.lower():
        return False
    if project_name and project_name.lower() not in trace_project_name.lower():
        return False

    if ts_from and trace_ts and trace_ts < ts_from:
        return False
    if ts_to and trace_ts and trace_ts > ts_to:
        return False
    if (ts_from or ts_to) and trace_ts is None:
        return False

    return True


def _parse_iso_datetime_or_400(value: str | None, field_name: str) -> datetime | None:
    """Parse ISO datetime and raise HTTP 400 on invalid values."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}. Use ISO datetime format.")


def _fetch_trace_by_id(client, trace_id: str) -> Any | None:
    """Fetch a trace by id using available SDK methods."""
    if not trace_id:
        return None

    fetch_methods = [
        ("fetch_trace", lambda: client.fetch_trace(trace_id)),
        ("client.traces.get", lambda: client.client.traces.get(trace_id)),
        ("api.trace.get", lambda: client.api.trace.get(trace_id)),
    ]

    for method_name, method in fetch_methods:
        try:
            if method_name == "fetch_trace" and not hasattr(client, "fetch_trace"):
                continue
            if method_name == "client.traces.get":
                if not (hasattr(client, "client") and hasattr(client.client, "traces")):
                    continue
            if method_name == "api.trace.get":
                if not (hasattr(client, "api") and hasattr(client.api, "trace")):
                    continue

            response = method()
            if response is None:
                continue
            return response.data if hasattr(response, "data") else response
        except Exception as e:
            logger.debug(
                "Trace fetch via {} failed for trace_id={}: {}",
                method_name,
                trace_id,
                str(e),
            )

    return None


def _choose_trace_candidate(
    traces: List[Any],
    *,
    requested_trace_id: str,
    user_id: str,
    session_id: str | None = None,
    agent_id: str | None = None,
    flow_name: str | None = None,
    project_name: str | None = None,
    timestamp: datetime | None = None,
) -> Dict[str, Any] | None:
    """Choose the best matching trace from a list using contextual scoring."""
    normalized_agent_id = _normalize_agent_id(agent_id)
    requested_session = str(session_id) if session_id else None
    requested_flow_name = str(flow_name).lower() if flow_name else None
    requested_project_name = str(project_name).lower() if project_name else None
    requested_user_id = str(user_id) if user_id else None

    scored_candidates: List[tuple[float, Dict[str, Any]]] = []
    for raw_trace in traces or []:
        trace_dict = parse_trace_data(raw_trace)
        candidate_trace_id = str(trace_dict.get("id") or "")
        if not candidate_trace_id:
            continue

        candidate_user_id = str(_extract_trace_user_id(trace_dict) or "")
        candidate_session_id = str(trace_dict.get("session_id") or "")
        candidate_agent_id = _extract_trace_agent_id(trace_dict)
        candidate_flow_name = (_extract_trace_flow_name(trace_dict) or "").lower()
        candidate_project_name = (_extract_trace_project_name(trace_dict) or "").lower()
        candidate_run_id = _extract_trace_run_id(trace_dict)
        candidate_ts = _parse_trace_timestamp(trace_dict.get("timestamp"))

        # Keep user isolation strict if the trace payload includes user id.
        if requested_user_id and candidate_user_id and candidate_user_id != requested_user_id:
            continue

        # Exclude explicit conflicts for session/flow when candidate provides those fields.
        if requested_session and candidate_session_id and candidate_session_id != requested_session:
            continue
        if normalized_agent_id and candidate_agent_id and candidate_agent_id != normalized_agent_id:
            continue
        if requested_project_name and candidate_project_name and requested_project_name not in candidate_project_name:
            continue

        score = 0.0
        if requested_trace_id and candidate_trace_id == requested_trace_id:
            score += 500.0
        if requested_trace_id and candidate_run_id and str(candidate_run_id) == requested_trace_id:
            score += 450.0
        if requested_session and candidate_session_id == requested_session:
            score += 140.0
        if normalized_agent_id and candidate_agent_id == normalized_agent_id:
            score += 120.0
        if requested_flow_name and requested_flow_name in candidate_flow_name:
            score += 50.0
        if requested_project_name and requested_project_name in candidate_project_name:
            score += 35.0

        if timestamp and candidate_ts:
            delta_seconds = abs((candidate_ts - timestamp).total_seconds())
            if delta_seconds <= 2:
                score += 100.0
            elif delta_seconds <= 10:
                score += 80.0
            elif delta_seconds <= 30:
                score += 60.0
            elif delta_seconds <= 120:
                score += 40.0
            elif delta_seconds <= 600:
                score += 15.0
            else:
                score -= 20.0

        scored_candidates.append((score, trace_dict))

    if not scored_candidates:
        return None

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_trace = scored_candidates[0]

    # Confidence gate to avoid evaluating the wrong trace.
    enough_context = bool(
        (session_id and str(best_trace.get("session_id") or "") == str(session_id))
        or (
            normalized_agent_id
            and _extract_trace_agent_id(best_trace)
            and _extract_trace_agent_id(best_trace) == normalized_agent_id
        )
        or (
            requested_trace_id
            and (
                str(best_trace.get("id") or "") == requested_trace_id
                or _extract_trace_run_id(best_trace) == requested_trace_id
            )
        )
    )
    if not enough_context and best_score < 180.0:
        return None

    return best_trace


async def _resolve_trace_for_judge(
    client,
    *,
    trace_id: str,
    user_id: str,
    session_id: str | None = None,
    agent_id: str | None = None,
    flow_name: str | None = None,
    project_name: str | None = None,
    timestamp: datetime | None = None,
    max_attempts: int = 8,
) -> tuple[str | None, Dict[str, Any] | None]:
    """Resolve the canonical Langfuse trace id and trace payload for judging."""
    trace_id = str(trace_id)
    resolved_timestamp = _parse_trace_timestamp(timestamp) or datetime.now(timezone.utc)

    for attempt in range(1, max_attempts + 1):
        # Step 1: direct fetch by id (fast-path for existing traces)
        fetched_trace = _fetch_trace_by_id(client, trace_id)
        if fetched_trace:
            trace_dict = parse_trace_data(fetched_trace)
            fetched_id = str(trace_dict.get("id") or trace_id)
            fetched_user_id = str(trace_dict.get("user_id") or "")
            if not fetched_user_id or fetched_user_id == str(user_id):
                return fetched_id, trace_dict
            logger.warning(
                f"Resolved trace {fetched_id} belongs to different user_id={fetched_user_id}; expected={user_id}"
            )

        # Step 2: fallback lookup by context among user traces.
        window_minutes = min(2 + (attempt * 3), 30)
        from_ts = resolved_timestamp - timedelta(minutes=window_minutes)
        to_ts = resolved_timestamp + timedelta(minutes=window_minutes)
        try:
            traces = fetch_traces_from_langfuse(
                client,
                user_id=str(user_id),
                limit=200,
                from_timestamp=from_ts,
                to_timestamp=to_ts,
            )
        except Exception as e:
            logger.debug(
                "Context trace lookup failed for trace_ref={} attempt={}/{}: {}",
                trace_id,
                attempt,
                max_attempts,
                str(e),
            )
            traces = []

        candidate = _choose_trace_candidate(
            traces,
            requested_trace_id=trace_id,
            user_id=str(user_id),
            session_id=session_id,
            agent_id=agent_id,
            flow_name=flow_name,
            project_name=project_name,
            timestamp=resolved_timestamp,
        )
        if candidate:
            return str(candidate.get("id")), candidate

        # final wide search without strict time window in case ingestion lag is high
        if attempt == max_attempts:
            try:
                traces = fetch_traces_from_langfuse(
                    client,
                    user_id=str(user_id),
                    limit=400,
                )
                candidate = _choose_trace_candidate(
                    traces,
                    requested_trace_id=trace_id,
                    user_id=str(user_id),
                    session_id=session_id,
                    agent_id=agent_id,
                    flow_name=flow_name,
                    project_name=project_name,
                    timestamp=resolved_timestamp,
                )
                if candidate:
                    return str(candidate.get("id")), candidate
            except Exception as e:
                logger.debug("Wide trace lookup failed for trace_ref={}: {}", trace_id, str(e))

        await asyncio.sleep(min(0.5 * attempt, 3.0))

    return None, None


async def run_llm_judge_task(
    client,
    trace_id: str,
    criteria: str,
    score_name: str,
    model: str,
    user_id: str,
    model_api_key: str | None = None,
    preset_id: str | None = None,
    ground_truth: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
    flow_name: str | None = None,
    project_name: str | None = None,
    timestamp: datetime | None = None,
):
    """Background task to run LLM judge."""
    if not LITELLM_AVAILABLE and not OPENAI_AVAILABLE:
        logger.error("LiteLLM not installed and OpenAI SDK not available, cannot run judge")
        return

    try:
        # 1. Resolve canonical trace id and fetch trace payload.
        logger.info(
            f"Resolving trace for evaluation: trace_ref={trace_id}, session_id={session_id}, agent_id={agent_id}"
        )
        resolved_trace_id, trace_dict = await _resolve_trace_for_judge(
            client,
            trace_id=str(trace_id),
            user_id=str(user_id),
            session_id=session_id,
            agent_id=agent_id,
            flow_name=flow_name,
            project_name=project_name,
            timestamp=timestamp,
        )
        if not resolved_trace_id or not trace_dict:
            logger.error(
                f"Judge failed: could not resolve trace for trace_ref={trace_id}, "
                f"user_id={user_id}, session_id={session_id}, agent_id={agent_id}"
            )
            return
        if resolved_trace_id != str(trace_id):
            logger.info(f"Resolved trace_ref={trace_id} to canonical trace_id={resolved_trace_id}")
        trace_input = trace_dict.get('input', '')
        trace_output = trace_dict.get('output', '')

        # Convert to string if needed
        if not isinstance(trace_input, str):
            trace_input = json.dumps(trace_input)
        if not isinstance(trace_output, str):
            trace_output = json.dumps(trace_output)

        # 2. Construct Prompt
        if ground_truth:
            system_prompt = (
                "You are an impartial AI judge evaluating an AI assistant's interaction. "
                "You will be given the Input (User Query), the Output (AI Response), and the Ground Truth (Expected Answer). "
                "Your task is to evaluate the Output against the Ground Truth based strictly on the provided Criteria. "
                "Provide a score between 0.0 (worst) and 1.0 (perfect) and explain your reasoning."
            )
        else:
            system_prompt = (
                "You are an impartial AI judge evaluating an AI assistant's interaction. "
                "You will be given the Input (User Query) and the Output (AI Response). "
                "Your task is to evaluate the Output based strictly on the provided Criteria. "
                "Provide a score between 0.0 (worst) and 1.0 (perfect) and explain your reasoning."
            )
        
        if ground_truth:
            user_prompt = f"""### Criteria
{criteria}

### Input
{trace_input}

### Ground Truth (Expected Answer)
{ground_truth}

### Output (Actual Response)
{trace_output}

### Instructions
Evaluate the Output by comparing it to the Ground Truth based on the Criteria.
Provide a numeric score between 0 and 5 inclusive (0 worst, 5 best).
Respond with a JSON object containing:
- "score_0_5": A number between 0 and 5.
- "reason": A concise explanation of your scoring (1-3 sentences).

Respond ONLY with valid JSON, no markdown formatting."""
        else:
            user_prompt = f"""### Criteria
{criteria}

### Input
{trace_input}

### Output
{trace_output}

### Instructions
Evaluate the Output based on the Criteria.
Provide a numeric score between 0 and 5 inclusive (0 worst, 5 best).
Respond with a JSON object containing:
- "score_0_5": A number between 0 and 5.
- "reason": A concise explanation of your scoring (1-3 sentences).

Respond ONLY with valid JSON, no markdown formatting."""

        # 3. Call LLM (with provider/model normalization retries)
        model_candidates = _build_litellm_model_candidates(model, model_api_key)
        if not model_candidates:
            logger.error(f"Judge failed: invalid empty model for trace_ref={trace_id}")
            return

        logger.info(f"Calling LLM judge with model candidates: {model_candidates}")

        # If LiteLLM is available, prefer it (supports provider/model resolution).
        if LITELLM_AVAILABLE:
            _ensure_litellm_logging_compatibility_patch()

            # Reduce noisy/proxy-related logger side effects in worker context.
            try:
                litellm.suppress_debug_info = True
                litellm.turn_off_message_logging = True
                litellm.logging = False
            except Exception:
                pass

            response = None
            used_model = model_candidates[0]
            last_error: Exception | None = None

            for candidate_model in model_candidates:
                acall_kwargs = dict(
                    model=candidate_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                )
                acall_kwargs["no-log"] = True
                if model_api_key:
                    acall_kwargs["api_key"] = model_api_key

                api_base = _resolve_api_base_for_model(candidate_model)
                if api_base:
                    acall_kwargs["api_base"] = api_base

                try:
                    response = await litellm.acompletion(**acall_kwargs)
                    used_model = candidate_model
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("LLM judge call failed for model={}: {}", candidate_model, str(e))
                    if _is_litellm_retryable_model_error(e):
                        continue
                    raise

            if response is None:
                if last_error:
                    raise last_error
                raise RuntimeError("LLM judge call failed without a response")

            content = response.choices[0].message.content

        else:
            # Fallback to OpenAI SDK if available.
            content, used_model = await _call_openai_judge_completion(
                model_candidates=model_candidates,
                model_api_key=model_api_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

        # Clean up markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)

        # Extract 0-5 score and reason
        raw_score = result.get("score_0_5") if result.get("score_0_5") is not None else result.get("score")
        try:
            score_0_5 = float(raw_score)
        except Exception:
            score_0_5 = 0.0
        reason = result.get("reason", "No reason provided")

        # Clamp to 0-5
        score_0_5 = max(0.0, min(5.0, score_0_5))

        # Normalize to 0-1 for Langfuse value field but include raw in comment
        normalized_value = score_0_5 / 5.0

        # 4. Submit Score to Langfuse
        logger.info(f"Submitting score to Langfuse: {score_name} raw={score_0_5} normalized={normalized_value}")
        score_comment_data = {
            "criteria": criteria,
            "model": used_model,
            "requested_model": model,
            "reason": reason,
            "source": "llm-judge",
            "raw_score_0_5": score_0_5,
            "preset_id": preset_id,
            "requested_trace_id": str(trace_id),
            "resolved_trace_id": str(resolved_trace_id),
        }
        if ground_truth:
            score_comment_data["ground_truth"] = ground_truth
        score_comment = json.dumps(score_comment_data)
        _submit_score_to_langfuse(
            client,
            trace_id=str(resolved_trace_id),
            name=score_name,
            value=normalized_value,
            comment=score_comment,
        )
        
        # Flush to ensure immediate send
        if hasattr(client, "flush"):
            client.flush()
        
        logger.info(
            f"Judge completed for trace_ref={trace_id}, trace_id={resolved_trace_id}: "
            f"{score_name}={normalized_value}"
        )

    except json.JSONDecodeError as e:
        logger.error("LLM Judge JSON parsing error for trace_ref={}: {}", trace_id, str(e))
        logger.error("Response content: {}", content)
    except Exception as e:
        logger.opt(exception=True).error("LLM Judge error for trace_ref={}: {}", trace_id, str(e))


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/status")
async def get_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Dict[str, Any]:
    """Check if evaluation features are available."""
    client = get_langfuse_client()
    
    return {
        "langfuse_available": client is not None,
        "llm_judge_available": LITELLM_AVAILABLE or OPENAI_AVAILABLE,
        "user_id": str(current_user.id)
    }


@router.get("/scores")
async def get_scores(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    page: Annotated[int, Query(ge=1)] = 1,
    trace_id: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
) -> Dict[str, Any]:
    """
    List evaluation scores for the current user.
    Uses user_id when available, with trace-based fallback for providers that do not
    persist score-level user_id.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        trace_lookup: Dict[str, Dict[str, Any]] = {}
        user_trace_ids: set[str] = set()
        trace_owner_cache: Dict[str, bool] = {}
        try:
            user_traces = fetch_traces_from_langfuse(client, user_id=user_id, limit=2000)
            for raw_trace in user_traces or []:
                trace_dict = parse_trace_data(raw_trace)
                trace_key = str(trace_dict.get("id") or "")
                if not trace_key:
                    continue
                trace_lookup[trace_key] = trace_dict
                user_trace_ids.add(trace_key)
        except Exception as trace_error:
            logger.debug("Failed to prefetch user traces for score listing: {}", str(trace_error))

        def _extract_scores_payload(response: Any) -> tuple[list[Any], int | None]:
            if response is None:
                return [], None

            rows: list[Any] = []
            total_items: int | None = None
            if hasattr(response, "data"):
                rows = list(response.data or [])
                meta = getattr(response, "meta", None)
                if isinstance(meta, dict):
                    total_items = meta.get("total_items") or meta.get("total")
                elif meta is not None:
                    total_items = (
                        getattr(meta, "total_items", None)
                        or getattr(meta, "total", None)
                    )
            elif isinstance(response, dict):
                rows = list(response.get("data") or [])
                meta = response.get("meta")
                if isinstance(meta, dict):
                    total_items = meta.get("total_items") or meta.get("total")
            elif isinstance(response, list):
                rows = response
                total_items = len(rows)
            return rows, total_items

        def _list_scores_page(page_num: int, page_limit: int, *, include_user_filter: bool) -> tuple[list[Any], int | None]:
            if not (hasattr(client, "client") and hasattr(client.client, "scores")):
                return [], None

            kwargs: Dict[str, Any] = {
                "page": page_num,
                "limit": page_limit,
            }
            if trace_id:
                kwargs["trace_id"] = trace_id
            if name:
                kwargs["name"] = name
            if include_user_filter:
                kwargs["user_id"] = user_id

            try:
                response = client.client.scores.list(**kwargs)
            except TypeError:
                kwargs.pop("user_id", None)
                response = client.client.scores.list(**kwargs)
            return _extract_scores_payload(response)

        def _list_global_scores(max_rows: int = 2000) -> list[Any]:
            """Best-effort global score scan across SDK variants."""
            rows_out: list[Any] = []
            seen_keys: set[str] = set()
            page_size = min(100, max_rows)
            max_pages = max(1, (max_rows + page_size - 1) // page_size)

            def _append(rows: list[Any]) -> None:
                for row in rows or []:
                    row_id = str(get_attr(row, "id", default="") or "")
                    row_trace_id = str(get_attr(row, "trace_id", "traceId", default="") or "")
                    row_name = str(get_attr(row, "name", default="score") or "score")
                    row_ts = str(get_attr(row, "timestamp", "created_at", "createdAt", default="") or "")
                    dedupe_key = row_id or f"{row_trace_id}::{row_name}::{row_ts}"
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)
                    rows_out.append(row)

            # Method 1: v3 score_v_2.get
            if hasattr(client, "api") and hasattr(client.api, "score_v_2"):
                for page_num in range(1, max_pages + 1):
                    kwargs: Dict[str, Any] = {"limit": page_size, "page": page_num}
                    try:
                        payload = client.api.score_v_2.get(**kwargs)
                    except Exception:
                        break
                    page_rows, _ = _extract_scores_payload(payload)
                    if not page_rows:
                        break
                    _append(page_rows)
                    if len(rows_out) >= max_rows or len(page_rows) < page_size:
                        break

            # Method 2: v3 api.scores.list/api.score.list
            if len(rows_out) < max_rows and hasattr(client, "api"):
                for attr in ("scores", "score"):
                    score_api = getattr(client.api, attr, None)
                    if not score_api or not hasattr(score_api, "list"):
                        continue
                    for page_num in range(1, max_pages + 1):
                        kwargs = {"limit": page_size, "page": page_num}
                        try:
                            payload = score_api.list(**kwargs)
                        except Exception:
                            break
                        page_rows, _ = _extract_scores_payload(payload)
                        if not page_rows:
                            break
                        _append(page_rows)
                        if len(rows_out) >= max_rows or len(page_rows) < page_size:
                            break
                    if len(rows_out) >= max_rows:
                        break

            # Method 3: direct scores client without user filter
            if len(rows_out) < max_rows and hasattr(client, "client") and hasattr(client.client, "scores"):
                for page_num in range(1, max_pages + 1):
                    kwargs = {"limit": page_size, "page": page_num}
                    try:
                        payload = client.client.scores.list(**kwargs)
                    except Exception:
                        break
                    page_rows, _ = _extract_scores_payload(payload)
                    if not page_rows:
                        break
                    _append(page_rows)
                    if len(rows_out) >= max_rows or len(page_rows) < page_size:
                        break

            return rows_out[:max_rows]

        def _score_belongs_to_user(score_row: Any) -> bool:
            score_user_id = get_attr(score_row, "user_id", "userId")
            if score_user_id is not None:
                return str(score_user_id) == user_id

            score_trace_id = str(get_attr(score_row, "trace_id", "traceId", default="") or "")
            if not score_trace_id:
                return False
            if score_trace_id in trace_owner_cache:
                return trace_owner_cache[score_trace_id]
            if score_trace_id in user_trace_ids:
                trace_owner_cache[score_trace_id] = True
                return True

            # Last-resort ownership check: resolve trace and compare trace user_id.
            try:
                trace_raw = _fetch_trace_by_id(client, score_trace_id)
                if trace_raw:
                    trace_dict = parse_trace_data(trace_raw)
                    trace_lookup[score_trace_id] = trace_dict
                    trace_user_id = str(_extract_trace_user_id(trace_dict) or "")
                    if trace_user_id:
                        is_owner = trace_user_id == user_id
                    else:
                        # Some deployments don't populate user_id on traces/scores.
                        # If we cannot establish ownership via user metadata at all,
                        # allow the score as a best-effort fallback.
                        is_owner = not user_trace_ids
                    trace_owner_cache[score_trace_id] = is_owner
                    if is_owner:
                        user_trace_ids.add(score_trace_id)
                    return is_owner
            except Exception as owner_error:
                logger.debug(
                    "Could not verify trace ownership for score trace_id={}: {}",
                    score_trace_id,
                    str(owner_error),
                )

            if not user_trace_ids:
                logger.debug(
                    "Score ownership fallback: accepting trace_id={} without user metadata",
                    score_trace_id,
                )
                trace_owner_cache[score_trace_id] = True
                return True

            trace_owner_cache[score_trace_id] = False
            return False

        def _score_matches_name(score_row: Any) -> bool:
            if not name:
                return True
            score_name = str(get_attr(score_row, "name", default="") or "")
            return name.lower() in score_name.lower()

        raw_scores: list[Any] = []
        total = 0
        unscoped_collected: list[Any] = []

        # Primary fetch with user filter.
        primary_rows, primary_total = _list_scores_page(page, limit, include_user_filter=True)
        primary_rows = [
            row for row in primary_rows
            if _score_belongs_to_user(row) and _score_matches_name(row)
        ]
        if primary_rows:
            raw_scores = primary_rows
            total = (
                int(primary_total)
                if primary_total is not None and len(primary_rows) > 0
                else len(primary_rows)
            )
        else:
            # Fallback: some score records do not carry user_id; scan without user filter,
            # then enforce user isolation with trace ownership checks.
            collected: list[Any] = []
            seen_keys: set[str] = set()
            unscoped_seen_keys: set[str] = set()
            target_count = page * limit
            scan_limit = min(200, max(50, limit))
            max_scan_pages = 10

            for scan_page in range(1, max_scan_pages + 1):
                scan_rows, _ = _list_scores_page(scan_page, scan_limit, include_user_filter=False)
                if not scan_rows:
                    break

                for row in scan_rows:
                    row_trace_id = str(get_attr(row, "trace_id", "traceId", default="") or "")
                    if trace_id and row_trace_id != str(trace_id):
                        continue
                    if not _score_matches_name(row):
                        continue

                    # Keep an unscoped copy in case ownership metadata is completely absent.
                    row_id_for_unscoped = str(get_attr(row, "id", default="") or "")
                    unscoped_dedupe_key = row_id_for_unscoped or (
                        f"{row_trace_id}::{get_attr(row, 'name', default='score')}::"
                        f"{get_attr(row, 'timestamp', 'created_at', 'createdAt', default='')}"
                    )
                    if unscoped_dedupe_key not in unscoped_seen_keys:
                        unscoped_seen_keys.add(unscoped_dedupe_key)
                        unscoped_collected.append(row)

                    if not _score_belongs_to_user(row):
                        continue

                    row_id = str(get_attr(row, "id", default="") or "")
                    dedupe_key = row_id or (
                        f"{row_trace_id}::{get_attr(row, 'name', default='score')}::"
                        f"{get_attr(row, 'timestamp', 'created_at', 'createdAt', default='')}"
                    )
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)
                    collected.append(row)

                if len(collected) >= target_count:
                    break
                if len(scan_rows) < scan_limit:
                    break

            # If the direct list endpoint is empty, try broader SDK-specific score APIs.
            if not collected and not unscoped_collected:
                global_scan_rows = _list_global_scores(max_rows=max(1000, page * limit * 10))
                logger.info(
                    "Global score scan fallback collected {} row(s) for user_id={}",
                    len(global_scan_rows),
                    user_id,
                )
                for row in global_scan_rows:
                    row_trace_id = str(get_attr(row, "trace_id", "traceId", default="") or "")
                    if trace_id and row_trace_id != str(trace_id):
                        continue
                    if not _score_matches_name(row):
                        continue

                    row_id_for_unscoped = str(get_attr(row, "id", default="") or "")
                    unscoped_dedupe_key = row_id_for_unscoped or (
                        f"{row_trace_id}::{get_attr(row, 'name', default='score')}::"
                        f"{get_attr(row, 'timestamp', 'created_at', 'createdAt', default='')}"
                    )
                    if unscoped_dedupe_key not in unscoped_seen_keys:
                        unscoped_seen_keys.add(unscoped_dedupe_key)
                        unscoped_collected.append(row)

                    if not _score_belongs_to_user(row):
                        continue

                    row_id = str(get_attr(row, "id", default="") or "")
                    dedupe_key = row_id or (
                        f"{row_trace_id}::{get_attr(row, 'name', default='score')}::"
                        f"{get_attr(row, 'timestamp', 'created_at', 'createdAt', default='')}"
                    )
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)
                    collected.append(row)

            total = len(collected)
            start = (page - 1) * limit
            raw_scores = collected[start:start + limit]

            # If ownership metadata is unavailable, fall back to unscoped rows so the
            # UI remains usable in single-tenant/local deployments.
            if not raw_scores and not user_trace_ids and unscoped_collected:
                logger.warning(
                    "Score ownership metadata unavailable for user_id={}; using unscoped score fallback",
                    user_id,
                )
                total = len(unscoped_collected)
                raw_scores = unscoped_collected[start:start + limit]

        # Final fallback: collect scores per user-owned trace using observability's
        # robust score fetcher when list-based score APIs are empty/incompatible.
        if not raw_scores and (user_trace_ids or trace_id or unscoped_collected):
            logger.info(
                "Score list API returned no rows for user_id={}; using per-trace score fallback",
                user_id,
            )
            trace_candidates: list[str] = []
            if trace_id:
                trace_candidates = [str(trace_id)]
            elif user_trace_ids:
                trace_candidates = list(user_trace_ids)
            else:
                trace_candidates = list(
                    dict.fromkeys(
                        str(get_attr(row, "trace_id", "traceId", default="") or "")
                        for row in unscoped_collected
                        if str(get_attr(row, "trace_id", "traceId", default="") or "")
                    )
                )

            # Expand trace candidates with canonical ids and run_ids, as score writes may
            # target a different id than the one returned by list endpoints.
            expanded_trace_candidates: list[str] = []
            for candidate_id in trace_candidates:
                candidate_id = str(candidate_id or "").strip()
                if not candidate_id:
                    continue
                if candidate_id not in expanded_trace_candidates:
                    expanded_trace_candidates.append(candidate_id)

                trace_dict = trace_lookup.get(candidate_id)
                if not trace_dict:
                    try:
                        trace_raw = _fetch_trace_by_id(client, candidate_id)
                        if trace_raw:
                            trace_dict = parse_trace_data(trace_raw)
                            resolved_id = str(trace_dict.get("id") or "")
                            if resolved_id:
                                trace_lookup[resolved_id] = trace_dict
                            trace_lookup[candidate_id] = trace_dict
                    except Exception as resolve_error:
                        logger.debug(
                            "Failed resolving canonical trace id for candidate {}: {}",
                            candidate_id,
                            str(resolve_error),
                        )

                if trace_dict:
                    resolved_id = str(trace_dict.get("id") or "")
                    if resolved_id and resolved_id not in expanded_trace_candidates:
                        expanded_trace_candidates.append(resolved_id)
                    run_id = _extract_trace_run_id(trace_dict)
                    if run_id and run_id not in expanded_trace_candidates:
                        expanded_trace_candidates.append(str(run_id))

            if expanded_trace_candidates:
                trace_candidates = expanded_trace_candidates
                logger.info(
                    "Expanded per-trace score fallback candidates to {} ids",
                    len(trace_candidates),
                )

            collected_rows: list[dict[str, Any]] = []
            seen_keys: set[str] = set()
            max_traces_to_scan = 500

            for trace_key in trace_candidates[:max_traces_to_scan]:
                if not trace_key:
                    continue
                try:
                    trace_scores = fetch_scores_for_trace(
                        client,
                        trace_id=trace_key,
                        user_id=user_id,
                        limit=200,
                    )
                except Exception as trace_score_error:
                    logger.debug(
                        "Per-trace score fetch failed for trace_id={}: {}",
                        trace_key,
                        str(trace_score_error),
                    )
                    continue

                for trace_score in trace_scores:
                    score_name = str(get_attr(trace_score, "name", default="") or "")
                    if name and name.lower() not in score_name.lower():
                        continue

                    score_id = str(get_attr(trace_score, "id", default="") or "")
                    created_at = get_attr(trace_score, "created_at", "timestamp", default=None)
                    dedupe_key = score_id or f"{trace_key}::{score_name}::{created_at}"
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)

                    source_value = get_attr(trace_score, "source", default=None)
                    if hasattr(source_value, "value"):
                        source_value = source_value.value

                    collected_rows.append(
                        {
                            "id": score_id,
                            "trace_id": trace_key,
                            "name": score_name or "Score",
                            "value": float(get_attr(trace_score, "value", default=0.0) or 0.0),
                            "source": str(source_value) if source_value is not None else "API",
                            "comment": get_attr(trace_score, "comment", default=None),
                            "created_at": created_at,
                            "observation_id": get_attr(trace_score, "observation_id", "observationId", default=None),
                            "config_id": get_attr(trace_score, "config_id", "configId", default=None),
                            "user_id": user_id,
                        }
                    )

            def _score_sort_key(row: dict[str, Any]) -> datetime:
                parsed = _parse_trace_timestamp(row.get("created_at"))
                return parsed or datetime.min.replace(tzinfo=timezone.utc)

            collected_rows.sort(key=_score_sort_key, reverse=True)
            total = len(collected_rows)
            start = (page - 1) * limit
            raw_scores = collected_rows[start:start + limit]
            logger.info(
                "Per-trace score fallback produced {} row(s); returning {} row(s) for page={} limit={}",
                total,
                len(raw_scores),
                page,
                limit,
            )

        # Parse to response model (including agent/flow name).
        items: list[ScoreResponse] = []
        for s in raw_scores:
            score_trace_id = str(get_attr(s, "trace_id", "traceId", default="") or "")
            trace_dict = trace_lookup.get(score_trace_id)
            if score_trace_id and not trace_dict:
                try:
                    trace_raw = _fetch_trace_by_id(client, score_trace_id)
                    if trace_raw:
                        trace_dict = parse_trace_data(trace_raw)
                        trace_lookup[score_trace_id] = trace_dict
                except Exception as trace_error:
                    logger.debug("Failed to fetch trace {} for score enrichment: {}", score_trace_id, str(trace_error))

            agent_name = _extract_trace_flow_name(trace_dict or {}) if trace_dict else None
            if not agent_name and trace_dict:
                trace_name = trace_dict.get("name")
                agent_name = str(trace_name) if trace_name else None

            source = get_attr(s, "source")
            if hasattr(source, "value"):
                source = source.value

            score_id = str(get_attr(s, "id", default="") or "")
            items.append(ScoreResponse(
                id=score_id or f"{score_trace_id}:{get_attr(s, 'name', default='score')}",
                trace_id=score_trace_id,
                agent_name=agent_name,
                name=str(get_attr(s, "name", default="Score") or "Score"),
                value=float(get_attr(s, "value", default=0.0) or 0.0),
                source=str(source) if source is not None else "API",
                comment=get_attr(s, "comment"),
                user_id=str(get_attr(s, "user_id", "userId")) if get_attr(s, "user_id", "userId") else None,
                created_at=get_attr(s, "timestamp", "createdAt", "created_at"),
                observation_id=get_attr(s, "observation_id", "observationId"),
                config_id=get_attr(s, "config_id", "configId"),
            ))

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    except Exception as e:
        logger.opt(exception=True).error("Error fetching scores: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_score(
    payload: CreateScoreRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Dict[str, str]:
    """
    Create a manual score (Annotation).
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)
        
        # Verify trace belongs to user (optional but recommended)
        # For now we trust the frontend only shows user's traces
        
        _submit_score_to_langfuse(
            client,
            trace_id=payload.trace_id,
            observation_id=payload.observation_id,
            name=payload.name,
            value=payload.value,
            comment=payload.comment,
            source="ANNOTATION",
        )
        
        # Flush to ensure it sends
        if hasattr(client, "flush"):
            client.flush()
        
        logger.info(f"User {user_id} created score for trace {payload.trace_id}")
        
        return {"status": "success", "message": "Score created successfully"}

    except Exception as e:
        logger.opt(exception=True).error("Error creating score: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/judge")
async def run_judge(
    payload: JudgeRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Dict[str, str]:
    """
    Trigger an LLM-as-a-Judge evaluation for a trace.
    Runs in the background to not block API.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")
    
    if not (LITELLM_AVAILABLE or OPENAI_AVAILABLE):
        raise HTTPException(status_code=501, detail="LLM Judge not available (LiteLLM/OpenAI missing)")

    user_id = str(current_user.id)
    
    # Use criteria as score name if not provided
    score_name = payload.name or f"Judge: {payload.criteria[:50]}"

    # Run in background to not block API
    background_tasks.add_task(
        run_llm_judge_task,
        client=client,
        trace_id=payload.trace_id,
        criteria=payload.criteria,
        score_name=score_name,
        model=payload.model,
        user_id=user_id
    )

    logger.info(f"User {user_id} started judge for trace {payload.trace_id}")

    return {
        "status": "queued",
        "message": "Evaluation started in background. Refresh scores in a few seconds."
    }


@router.get("/analytics")
async def get_analytics(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> EvaluationAnalyticsResponse:
    """
    Get aggregated evaluation metrics for the dashboard.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)
        
        # Fetch recent scores for aggregation
        scores_data = []
        if hasattr(client, 'client') and hasattr(client.client, 'scores'):
            response = client.client.scores.list(user_id=user_id, limit=1000)
            if hasattr(response, 'data'):
                scores_data = response.data
            elif isinstance(response, list):
                scores_data = response

        # Group by name
        grouped: Dict[str, List[float]] = defaultdict(list)
        for s in scores_data:
            name = get_attr(s, 'name')
            val = float(get_attr(s, 'value', 0.0))
            if name and val is not None:
                grouped[name].append(val)

        # Calculate stats
        metrics = []
        for name, values in grouped.items():
            values.sort()
            count = len(values)
            avg = sum(values) / count
            
            metrics.append(AnalyticsMetric(
                name=name,
                count=count,
                average=avg,
                min=values[0],
                max=values[-1],
                p50=values[int(count * 0.5)] if count > 0 else None,
                p90=values[int(count * 0.9)] if count >= 10 else values[-1] if count > 0 else None
            ))

        return EvaluationAnalyticsResponse(
            total_scores=len(scores_data),
            by_name=metrics
        )

    except Exception as e:
        logger.opt(exception=True).error("Error fetching analytics: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/pending")
async def get_pending_reviews(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: DbSession,
    trace_id: Annotated[Optional[str], Query()] = None,
    flow_name: Annotated[Optional[str], Query()] = None,
    session_id: Annotated[Optional[str], Query()] = None,
    user_id_filter: Annotated[Optional[str], Query()] = None,
    ts_from: Annotated[Optional[str], Query()] = None,
    ts_to: Annotated[Optional[str], Query()] = None,
    limit: int = 20,
) -> List[TraceForReview]:
    """
    Get recent traces that might need review (Annotation Queue).
    Returns traces belonging to user with score status.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)
        
        # Fetch recent traces for this user via shared helper (observability)
        fetch_limit = max(limit * 10, 100)
        try:
            traces_data = fetch_traces_from_langfuse(client, user_id=user_id, limit=fetch_limit)
            logger.info(f"Fetched {len(traces_data or [])} traces for user_id={user_id} (limit={fetch_limit})")
            sample_ids = [str(get_attr(t, 'id') or get_attr(t, 'trace_id') or '') for t in (traces_data or [])[:5]]
            logger.debug(f"Sample trace ids: {sample_ids}")
        except Exception as e:
            logger.warning("fetch_traces_from_langfuse failed: {}", str(e))
            traces_data = []

        # Fetch all scores for these traces
        score_counts = defaultdict(int)
        if hasattr(client, 'client') and hasattr(client.client, 'scores'):
            scores_response = client.client.scores.list(user_id=user_id, limit=1000)
            scores_data = []
            if hasattr(scores_response, 'data'):
                scores_data = scores_response.data
            elif isinstance(scores_response, list):
                scores_data = scores_response
            
            for score in scores_data:
                trace_id = get_attr(score, 'trace_id', 'traceId')
                if trace_id:
                    score_counts[trace_id] += 1

        # Get flow names from database for better context
        flow_query = select(Flow).where(Flow.user_id == current_user.id)
        db_flows = (await session.execute(flow_query)).scalars().all()
        flow_names = {str(flow.id): flow.name for flow in db_flows}

        # Apply filtering and build response
        result = []
        for t in traces_data:
            trace_dict = parse_trace_data(t)
            tid = trace_dict.get('id')
            if not tid:
                continue

            # filter by trace id exact match
            if trace_id and str(tid) != str(trace_id):
                continue

            # filter by flow name substring match (uses metadata or agent_id)
            metadata = trace_dict.get('metadata') or {}
            inferred_flow_name = None
            if isinstance(metadata, dict):
                inferred_flow_name = metadata.get('flow_name') or metadata.get('flowId') or metadata.get('agent_id')
            if not inferred_flow_name:
                # fallback to DB lookup using flow id stored in metadata
                agent_id = metadata.get('agent_id') if isinstance(metadata, dict) else None
                if agent_id:
                    inferred_flow_name = flow_names.get(str(agent_id))

            if flow_name:
                if not inferred_flow_name or flow_name.lower() not in str(inferred_flow_name).lower():
                    continue

            # filter by session id
            if session_id and str(trace_dict.get('session_id') or '').lower().find(session_id.lower()) < 0:
                continue

            # filter by user id
            if user_id_filter and str(trace_dict.get('user_id') or '').lower().find(user_id_filter.lower()) < 0:
                continue

            # filter by timestamp range if provided (ISO format)
            if ts_from or ts_to:
                try:
                    ts_val = None
                    ts = trace_dict.get('timestamp')
                    if isinstance(ts, (int, float)):
                        ts_val = datetime.fromtimestamp(float(ts) / 1000.0, timezone.utc)
                    else:
                        try:
                            ts_val = datetime.fromisoformat(str(ts))
                        except Exception:
                            ts_val = None

                    if ts_val:
                        if ts_from:
                            try:
                                tfrom = datetime.fromisoformat(ts_from)
                                if ts_val < tfrom:
                                    continue
                            except Exception:
                                pass
                        if ts_to:
                            try:
                                tto = datetime.fromisoformat(ts_to)
                                if ts_val > tto:
                                    continue
                            except Exception:
                                pass
                except Exception:
                    pass

            score_count = score_counts.get(str(tid), 0)

            result.append(TraceForReview(
                id=str(tid),
                name=trace_dict.get('name'),
                timestamp=trace_dict.get('timestamp'),
                input=trace_dict.get('input'),
                output=trace_dict.get('output'),
                session_id=trace_dict.get('session_id'),
                flow_name=inferred_flow_name,
                has_scores=score_count > 0,
                score_count=score_count
            ))

            if len(result) >= limit:
                break

        return result

    except Exception as e:
        logger.opt(exception=True).error("Error fetching pending queue: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Presets Configuration
# =============================================================================

EVALUATION_PRESETS = [
    {
        "id": "correctness",
        "name": "Correctness",
        "description": "Evaluate if the output is factually correct compared to the ground truth.",
        "criteria": "Evaluate the correctness of the generation against the ground truth on a scale 0-1. Consider:\n- Factual accuracy: Does the output match the ground truth?\n- Completeness: Are all key points from the ground truth covered?\n- Precision: Is the information accurate without hallucinations?",
        "requires_ground_truth": True,
    },
    {
        "id": "helpfulness",
        "name": "Helpfulness",
        "description": "Evaluate how helpful the response is to the user's query.",
        "criteria": "Evaluate how helpful the output is in addressing the user's input on a scale 0-1. Consider:\n- Relevance: Does it directly address what was asked?\n- Clarity: Is the response easy to understand?\n- Actionability: Can the user act on this information?",
        "requires_ground_truth": False,
    },
    {
        "id": "conciseness",
        "name": "Conciseness",
        "description": "Evaluate if the response is appropriately concise without unnecessary verbosity.",
        "criteria": "Evaluate the conciseness of the output on a scale 0-1. Consider:\n- Brevity: Is it as short as possible while being complete?\n- Focus: Does it avoid tangential information?\n- Efficiency: Does it convey the message without redundancy?",
        "requires_ground_truth": False,
    },
    {
        "id": "coherence",
        "name": "Coherence",
        "description": "Evaluate if the response flows logically and makes sense.",
        "criteria": "Evaluate the coherence and logical flow of the output on a scale 0-1. Consider:\n- Logical structure: Do ideas connect naturally?\n- Internal consistency: Are there contradictions?\n- Clarity of thought: Is the reasoning easy to follow?",
        "requires_ground_truth": False,
    },
    {
        "id": "relevance",
        "name": "Relevance",
        "description": "Evaluate how relevant the response is to the input query.",
        "criteria": "Evaluate the relevance of the output to the input query on a scale 0-1. Consider:\n- Topic alignment: Does it stay on topic?\n- Query understanding: Does it address the user's intent?\n- Information pertinence: Is all information provided relevant?",
        "requires_ground_truth": False,
    },
]


def get_preset_by_id(preset_id: str | None) -> Dict[str, Any] | None:
    """Return preset configuration by id."""
    if not preset_id:
        return None
    for preset in EVALUATION_PRESETS:
        if str(preset.get("id")) == str(preset_id):
            return preset
    return None


def validate_ground_truth_requirement(preset_id: str | None, ground_truth: str | None) -> None:
    """Validate whether ground truth is provided for presets that require it."""
    preset = get_preset_by_id(preset_id)
    if preset and preset.get("requires_ground_truth") and not (ground_truth or "").strip():
        raise HTTPException(
            status_code=400,
            detail=f"Ground truth is required for preset '{preset.get('name', preset_id)}'.",
        )


async def run_saved_evaluators_for_new_trace(
    *,
    trace_id: str,
    user_id: str,
    agent_id: str | None = None,
    flow_id: str | None = None,
    flow_name: str | None = None,
    session_id: str | None = None,
    project_name: str | None = None,
    timestamp: datetime | None = None,
) -> int:
    """Run all saved evaluators targeting new traces for a just-finished trace."""
    logger.info(
        f"🔍 EVALUATOR FUNCTION CALLED: trace={trace_id}, user={user_id}, "
        f"flow_id={flow_id}, agent_id={agent_id}, flow_name={flow_name}"
    )
    
    if not (LITELLM_AVAILABLE or OPENAI_AVAILABLE):
        logger.warning("⚠️ LiteLLM/OpenAI not available, skipping evaluators")
        return 0

    try:
        user_uuid = UUID(str(user_id))
    except Exception:
        logger.warning(f"Invalid user_id for new-trace evaluation: {user_id}")
        return 0

    client = get_langfuse_client()
    if not client:
        logger.warning("⚠️ Langfuse client not available, skipping evaluators")
        return 0

    requested_timestamp = _parse_trace_timestamp(timestamp) or datetime.now(timezone.utc)
    trace_ref_id = str(trace_id)
    
    # Use flow_id or agent_id (they're aliases)
    agent_id = agent_id or flow_id

    trace_dict: Dict[str, Any] = {
        "id": trace_ref_id,
        "session_id": session_id,
        "timestamp": requested_timestamp,
        "metadata": {
            "agent_id": _normalize_agent_id(agent_id),
            "flow_name": flow_name,
            "project_name": project_name,
            "run_id": trace_ref_id,
        },
    }

    resolved_trace_id, resolved_trace_dict = await _resolve_trace_for_judge(
        client,
        trace_id=trace_ref_id,
        user_id=str(user_id),
        session_id=session_id,
        agent_id=agent_id,
        flow_name=flow_name,
        project_name=project_name,
        timestamp=requested_timestamp,
        max_attempts=4,
    )
    if resolved_trace_dict:
        trace_dict = resolved_trace_dict

    try:
        async with session_scope() as session:
            stmt = select(Evaluator).where(Evaluator.user_id == user_uuid)
            rows = await session.exec(stmt)
            evaluators = rows.all()
    except Exception as e:
        logger.warning("Failed loading evaluators for new trace {}: {}", trace_id, str(e))
        return 0

    logger.info(f"📋 Found {len(evaluators)} evaluator(s) for user {user_id}")
    
    scheduled = 0
    for idx, evaluator in enumerate(evaluators, 1):
        logger.info(
            f"🔎 Evaluator {idx}/{len(evaluators)}: name='{evaluator.name}', "
            f"target={evaluator.target}, agent_id={evaluator.agent_id}, "
            f"agent_ids={evaluator.agent_ids}, flow_name={evaluator.flow_name}"
        )
        
        targets = _normalize_targets(evaluator.target)
        if "new" not in targets:
            logger.info(f"  ⏭️ Skipping: target={targets} (not 'new')")
            continue

        logger.info(
            f"  🎯 Checking filters: trace_dict_agent_id={trace_dict.get('metadata', {}).get('agent_id')}, "
            f"trace_dict_flow_name={trace_dict.get('metadata', {}).get('flow_name')}"
        )
        
        matches = _trace_matches_evaluator_filters(
            trace_dict,
            trace_id=evaluator.trace_id,
            session_id=evaluator.session_id,
            agent_id=evaluator.agent_id,
            agent_ids=evaluator.agent_ids,
            flow_name=evaluator.flow_name,
            project_name=evaluator.project_name,
            ts_from=evaluator.ts_from,
            ts_to=evaluator.ts_to,
        )
        
        if not matches:
            logger.info(f"  ❌ Skipping: trace does not match filters")
            continue
        
        logger.info(f"  ✅ MATCH! Scheduling evaluation for '{evaluator.name}'")

        # Skip invalid evaluator definitions instead of failing all.
        try:
            validate_ground_truth_requirement(evaluator.preset_id, evaluator.ground_truth)
        except HTTPException as e:
            logger.warning(
                f"Skipping evaluator {evaluator.id} for trace {trace_id}: {e.detail}"
            )
            continue

        asyncio.create_task(
            run_llm_judge_task(
                client=client,
                trace_id=str(resolved_trace_id or trace_ref_id),
                criteria=evaluator.criteria,
                score_name=f"Evaluator: {evaluator.name}",
                model=evaluator.model or "gpt-4o",
                user_id=str(user_id),
                model_api_key=evaluator.model_api_key,
                preset_id=evaluator.preset_id,
                ground_truth=evaluator.ground_truth,
                session_id=session_id,
                agent_id=agent_id,
                flow_name=flow_name,
                project_name=project_name,
                timestamp=requested_timestamp,
            )
        )
        scheduled += 1

    if scheduled:
        logger.info(
            f"✅ Scheduled {scheduled} new-trace evaluator(s) for trace_ref={trace_ref_id}, "
            f"resolved_trace_id={resolved_trace_id}, user_id={user_id}"
        )
    else:
        logger.info(
            f"⚠️ No evaluators scheduled for trace {trace_ref_id}. "
            f"Total evaluators checked: {len(evaluators)}"
        )
    return scheduled


@router.get("/presets")
async def list_evaluation_presets(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> List[Dict[str, Any]]:
    """List available evaluation presets with their requirements."""
    return EVALUATION_PRESETS


@router.get("/models")
async def list_evaluation_models(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Dict[str, Any]:
    """Return flows accessible to the current user as a normalized model list.

    This endpoint intentionally uses the application's standard auth (JWT/cookie)
    so the frontend can fetch the Model Catalogue without requiring an API key.
    """
    try:
        async with session_scope() as session:
            stmt = (
                select(Flow)
                .where(
                    or_(
                        Flow.is_component == False,  # noqa: E712
                        Flow.is_component.is_(None),
                    )
                )
                .where(
                    or_(
                        Flow.user_id == current_user.id,
                        Flow.access_type == AccessTypeEnum.PUBLIC,
                    )
                )
            )
            _res = await session.exec(stmt)
            flows = _res.all()

        def to_payload(flow: Flow) -> dict:
            updated = flow.updated_at
            try:
                updated_dt = datetime.fromisoformat(updated) if isinstance(updated, str) else updated
            except Exception:
                updated_dt = None
            created_ts = int(updated_dt.timestamp()) if updated_dt else int(time.time())
            return {
                "id": f"lb:{flow.endpoint_name or flow.id}",
                "name": flow.name,
                "object": "model",
                "created": created_ts,
                "owned_by": str(flow.user_id) if flow.user_id else None,
                "root": f"lb:{flow.endpoint_name or flow.id}",
                "parent": None,
                "permission": [],
                "metadata": {
                    "display_name": flow.name,
                    "description": flow.description,
                    "endpoint_name": flow.endpoint_name,
                    # New canonical key used across the codebase
                    "agent_id": str(flow.id),
                    # Legacy aliases expected by some frontend codepaths — keep for compatibility
                    "flow_id": str(flow.id),
                    "flow_ids": [str(flow.id)],
                    "access": flow.access_type.value if flow.access_type else AccessTypeEnum.PRIVATE.value,
                },
            }

        return {"object": "list", "data": [to_payload(f) for f in flows]}
    except Exception as e:
        logger.opt(exception=True).error("Error listing evaluation models: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configs")
async def create_evaluator_config(
    payload: EvaluatorCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> EvaluatorResponse:
    """Create a reusable evaluator configuration and optionally run on existing traces."""
    try:
        normalized_target = _normalize_targets(payload.target)
        invalid_targets = [target for target in normalized_target if target not in {"existing", "new"}]
        if invalid_targets:
            raise HTTPException(status_code=400, detail=f"Invalid target value(s): {', '.join(invalid_targets)}")
        normalized_agent_id = _normalize_agent_id(payload.agent_id)
        normalized_agent_ids = _normalize_agent_ids(payload.agent_ids)
        validate_ground_truth_requirement(payload.preset_id, payload.ground_truth)

        from_ts = _parse_iso_datetime_or_400(payload.ts_from, "ts_from")
        to_ts = _parse_iso_datetime_or_400(payload.ts_to, "ts_to")

        async with session_scope() as session:
            evaluator = Evaluator(
                name=payload.name,
                criteria=payload.criteria,
                model=payload.model,
                preset_id=payload.preset_id,
                ground_truth=payload.ground_truth,
                target=normalized_target,
                trace_id=payload.trace_id,
                agent_id=normalized_agent_id,
                agent_ids=normalized_agent_ids or None,
                flow_name=payload.flow_name,
                session_id=payload.session_id,
                project_name=payload.project_name,
                ts_from=from_ts,
                ts_to=to_ts,
                model_api_key=payload.model_api_key,
                user_id=current_user.id,
            )
            session.add(evaluator)
            await session.commit()
            await session.refresh(evaluator)

        eid = str(evaluator.id)
        logger.info(
            f"evaluation - Created evaluator config in DB: id={eid}, user={current_user.id}, target={normalized_target}"
        )

        # If target includes 'existing', fetch matching traces and enqueue judge tasks.
        if "existing" in normalized_target:
            client = get_langfuse_client()
            if client:
                try:
                    traces = fetch_traces_from_langfuse(
                        client,
                        user_id=str(current_user.id),
                        limit=1000,
                        from_timestamp=from_ts,
                        to_timestamp=to_ts,
                    )

                    matched = []
                    for trace in traces or []:
                        trace_dict = parse_trace_data(trace)
                        if _trace_matches_evaluator_filters(
                            trace_dict,
                            trace_id=payload.trace_id,
                            session_id=payload.session_id,
                            agent_id=normalized_agent_id,
                            agent_ids=normalized_agent_ids,
                            flow_name=payload.flow_name,
                            project_name=payload.project_name,
                            ts_from=from_ts,
                            ts_to=to_ts,
                        ):
                            matched.append(trace_dict)

                    enqueued = 0
                    for matched_trace in matched:
                        matched_trace_id = str(matched_trace.get("id"))
                        background_tasks.add_task(
                            run_llm_judge_task,
                            client=client,
                            trace_id=matched_trace_id,
                            criteria=payload.criteria,
                            score_name=f"Evaluator: {payload.name}",
                            model=payload.model,
                            user_id=str(current_user.id),
                            model_api_key=payload.model_api_key,
                            preset_id=payload.preset_id,
                            ground_truth=payload.ground_truth,
                            session_id=str(matched_trace.get("session_id") or "") or None,
                            agent_id=_extract_trace_agent_id(matched_trace),
                            flow_name=_extract_trace_flow_name(matched_trace),
                            project_name=_extract_trace_project_name(matched_trace),
                            timestamp=_parse_trace_timestamp(matched_trace.get("timestamp")),
                        )
                        enqueued += 1

                    logger.info(f"evaluation - Enqueued {enqueued} judge tasks for evaluator id={eid}")
                except Exception as e:
                    logger.warning("Failed to enqueue evaluator for existing traces: {}", str(e))

        return EvaluatorResponse(**evaluator.to_response())
    except HTTPException:
        raise
    except Exception as e:
        logger.opt(exception=True).error("Error creating evaluator config: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs")
async def list_evaluator_configs(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> List[EvaluatorResponse]:
    """List evaluator configs for the current user."""
    try:
        async with session_scope() as session:
            stmt = select(Evaluator).where(Evaluator.user_id == current_user.id)
            res = await session.exec(stmt)
            evaluators = res.all()
        return [EvaluatorResponse(**e.to_response()) for e in evaluators]
    except Exception as e:
        logger.opt(exception=True).error("Error listing evaluator configs: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configs/{config_id}")
async def update_evaluator_config(
    config_id: str,
    payload: EvaluatorCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> EvaluatorResponse:
    """Update an existing evaluator config."""
    try:
        validate_ground_truth_requirement(payload.preset_id, payload.ground_truth)
        normalized_target = _normalize_targets(payload.target)
        invalid_targets = [target for target in normalized_target if target not in {"existing", "new"}]
        if invalid_targets:
            raise HTTPException(status_code=400, detail=f"Invalid target value(s): {', '.join(invalid_targets)}")
        normalized_agent_id = _normalize_agent_id(payload.agent_id)
        normalized_agent_ids = _normalize_agent_ids(payload.agent_ids)
        from_ts = _parse_iso_datetime_or_400(payload.ts_from, "ts_from")
        to_ts = _parse_iso_datetime_or_400(payload.ts_to, "ts_to")

        # Fetch evaluator from DB
        async with session_scope() as session:
            try:
                eval_obj = await session.get(Evaluator, UUID(config_id))
            except Exception:
                raise HTTPException(status_code=404, detail="Evaluator not found")
            if not eval_obj or str(current_user.id) != str(eval_obj.user_id):
                raise HTTPException(status_code=404, detail="Evaluator not found")

            eval_obj.name = payload.name
            eval_obj.criteria = payload.criteria
            eval_obj.model = payload.model
            eval_obj.preset_id = payload.preset_id
            eval_obj.ground_truth = payload.ground_truth
            eval_obj.target = normalized_target
            eval_obj.trace_id = payload.trace_id
            eval_obj.agent_id = normalized_agent_id
            eval_obj.agent_ids = normalized_agent_ids or None
            eval_obj.flow_name = payload.flow_name
            eval_obj.session_id = payload.session_id
            eval_obj.project_name = payload.project_name
            eval_obj.ts_from = from_ts
            eval_obj.ts_to = to_ts
            eval_obj.model_api_key = payload.model_api_key

            session.add(eval_obj)
            await session.commit()
            await session.refresh(eval_obj)

        return EvaluatorResponse(**eval_obj.to_response())
    except HTTPException:
        raise
    except Exception as e:
        logger.opt(exception=True).error("Error updating evaluator config: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configs/{config_id}")
async def delete_evaluator_config(
    config_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Dict[str, str]:
    """Delete an evaluator config."""
    try:
        async with session_scope() as session:
            try:
                eval_obj = await session.get(Evaluator, UUID(config_id))
            except Exception:
                raise HTTPException(status_code=404, detail="Evaluator not found")
            if not eval_obj or str(current_user.id) != str(eval_obj.user_id):
                raise HTTPException(status_code=404, detail="Evaluator not found")
            await session.delete(eval_obj)
            await session.commit()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.opt(exception=True).error("Error deleting evaluator config: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))


class PreviewRequest(BaseModel):
    trace_id: str
    criteria: str
    model: str = "gpt-4o"
    name: str | None = None


@router.post("/preview")
async def preview_evaluation(
    payload: PreviewRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Dict[str, Any]:
    """Return the system and user prompt that would be sent to the LLM for a given trace + criteria."""
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        trace_response = client.fetch_trace(payload.trace_id)
        trace_data = trace_response.data if hasattr(trace_response, "data") else trace_response
        if not trace_data:
            raise HTTPException(status_code=404, detail="Trace not found")

        trace_dict = parse_trace_data(trace_data)

        system_prompt = (
            "You are an impartial AI judge evaluating an AI assistant's interaction. "
            "You will be given the Input (User Query) and the Output (AI Response). "
            "Your task is to evaluate the Output based strictly on the provided Criteria. "
            "Provide a score between 0.0 (worst) and 1.0 (perfect) and explain your reasoning."
        )

        trace_input = trace_dict.get('input', '')
        trace_output = trace_dict.get('output', '')
        if not isinstance(trace_input, str):
            trace_input = json.dumps(trace_input)
        if not isinstance(trace_output, str):
            trace_output = json.dumps(trace_output)

        user_prompt = f"""### Criteria
{payload.criteria}

### Input
{trace_input}

### Output
{trace_output}

### Instructions
Evaluate the Output based on the Criteria.
Respond with a JSON object containing:
- \"score\": A float between 0.0 and 1.0 (where 1.0 is perfect).
- \"reason\": A concise explanation of your scoring (2-3 sentences).

Respond ONLY with valid JSON, no markdown formatting."""

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "trace": trace_dict,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.opt(exception=True).error("Error creating preview: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))
