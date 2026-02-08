"""
Observability API Endpoints - Enterprise Edition

These endpoints provide user-isolated access to observability data from Langfuse.
Each user can only see their own traces, token usage, and cost metrics.

Features:
- Session-centric view with drill-down to traces
- Detailed trace view with observations/spans (LLM calls, tool calls)
- Token and cost tracking per model, session, and trace
- Latency metrics
- User isolation at all levels
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Annotated, Any
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from agentcore.services.auth.utils import get_current_active_user
from agentcore.services.database.models.user.model import User
from agentcore.services.database.models.agent.model import Agent
from agentcore.services.database.models.folder.model import Folder
from agentcore.services.deps import get_session
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


router = APIRouter(prefix="/observability", tags=["Observability"])


# =============================================================================
# Response Models - Enterprise Grade
# =============================================================================

class ObservationResponse(BaseModel):
    """
    A single observation (span) within a trace.

    Observations represent individual operations like:
    - LLM calls (generation)
    - Tool/function calls
    - Retrieval operations
    - Custom spans
    """
    id: str
    trace_id: str
    name: str | None = None
    type: str | None = None  # "GENERATION", "SPAN", "EVENT"
    model: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    completion_start_time: datetime | None = None
    latency_ms: float | None = None  # Total latency in milliseconds
    time_to_first_token_ms: float | None = None
    # Token metrics
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    # Cost
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    # Data
    input: Any | None = None
    output: Any | None = None
    metadata: dict | None = None
    level: str | None = None  # "DEBUG", "DEFAULT", "WARNING", "ERROR"
    status_message: str | None = None
    parent_observation_id: str | None = None


class TraceDetailResponse(BaseModel):
    """
    Detailed trace information with all observations.
    """
    id: str
    name: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    timestamp: datetime | None = None
    # Aggregated metrics from observations
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    latency_ms: float | None = None
    # Model breakdown
    models_used: list[str] = []
    # Observations (spans) within this trace
    observations: list[ObservationResponse] = []
    # Metadata
    input: Any | None = None
    output: Any | None = None
    metadata: dict | None = None
    tags: list[str] = []
    # Status
    level: str | None = None
    status: str | None = None


class TraceListItem(BaseModel):
    """Trace item for list views (lighter than full detail)."""
    id: str
    name: str | None = None
    session_id: str | None = None
    timestamp: datetime | None = None
    total_tokens: int = 0
    total_cost: float = 0.0
    latency_ms: float | None = None
    models_used: list[str] = []
    observation_count: int = 0
    level: str | None = None


class TracesListResponse(BaseModel):
    """List of traces with pagination info."""
    traces: list[TraceListItem]
    total: int
    page: int
    limit: int


class SessionDetailResponse(BaseModel):
    """
    Detailed session information with all traces.
    A session represents a chat conversation.
    """
    session_id: str
    trace_count: int = 0
    observation_count: int = 0
    # Aggregated metrics
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None
    # Time range
    first_trace_at: datetime | None = None
    last_trace_at: datetime | None = None
    duration_seconds: float | None = None
    # Model usage within session
    models_used: dict[str, dict] = {}  # model -> {tokens, cost, calls}
    # Traces in this session
    traces: list[TraceListItem] = []


class SessionListItem(BaseModel):
    """Session item for list views."""
    session_id: str
    trace_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None
    first_trace_at: datetime | None = None
    last_trace_at: datetime | None = None
    models_used: list[str] = []
    error_count: int = 0  # Count of ERROR/WARNING observations
    has_errors: bool = False  # Quick flag for UI


class SessionsListResponse(BaseModel):
    """List of sessions."""
    sessions: list[SessionListItem]
    total: int


class ModelUsageItem(BaseModel):
    """Usage metrics for a specific model."""
    model: str
    call_count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None


class DailyUsageItem(BaseModel):
    """Daily usage statistics."""
    date: str
    trace_count: int = 0
    observation_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class MetricsResponse(BaseModel):
    """
    Comprehensive aggregated metrics for enterprise dashboards.
    """
    # Overview counts
    total_traces: int = 0
    total_observations: int = 0
    total_sessions: int = 0
    # Token metrics
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    # Cost metrics
    total_cost_usd: float = 0.0
    # Performance metrics
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    # Breakdown by model
    by_model: list[ModelUsageItem] = []
    # Breakdown by date (last 30 days)
    by_date: list[DailyUsageItem] = []
    # Top flows/traces by usage
    top_flows: list[dict] = []


class LangfuseStatusResponse(BaseModel):
    """Langfuse connection status."""
    connected: bool
    host: str | None = None
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def get_langfuse_client():
    """
    Get a Langfuse client using environment variables.
    Supports both Langfuse SDK v3 and v2.

    IMPORTANT: For data fetching (traces, observations), we use the Langfuse class
    directly, NOT get_client(). The get_client() is for OTEL-based tracing only.

    v3 expects env vars: LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL
    v2 expects env vars: LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST

    Returns the Langfuse client instance with _is_v3 attribute set.
    """
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    # v3 uses LANGFUSE_BASE_URL, v2 uses LANGFUSE_HOST
    base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")

    if not all([secret_key, public_key, base_url]):
        logger.warning("Langfuse credentials not configured. Need LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and LANGFUSE_BASE_URL (or LANGFUSE_HOST)")
        return None

    try:
        # Use Langfuse class directly for data fetching (works in both v2 and v3)
        # Note: get_client() is for OTEL tracing, Langfuse() is for data access
        from langfuse import Langfuse

        # Ensure LANGFUSE_BASE_URL is set for v3 compatibility
        if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
            os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST")

        client = Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=base_url
        )

        # Detect v3 by checking SDK version
        is_v3 = False
        sdk_version = "unknown"
        try:
            import langfuse
            sdk_version = getattr(langfuse, '__version__', 'unknown')
            # v3.x starts with 3.
            if sdk_version.startswith('3.'):
                is_v3 = True
            elif hasattr(client, 'auth_check'):
                # Fallback: auth_check method is more prominent in v3
                is_v3 = True
        except Exception:
            # If version check fails, use auth_check as fallback
            is_v3 = hasattr(client, 'auth_check')

        client._is_v3 = is_v3
        client._sdk_version = sdk_version

        # Health check
        if is_v3:
            try:
                if client.auth_check():
                    logger.info(f"Using Langfuse SDK v3 ({sdk_version}) - auth_check passed")
                else:
                    logger.warning(f"Langfuse v3 ({sdk_version}) auth_check failed")
            except Exception as e:
                logger.debug(f"v3 auth_check error (continuing anyway): {e}")
        else:
            logger.info(f"Using Langfuse SDK v2 ({sdk_version})")

        return client

    except ImportError:
        logger.warning("Langfuse package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to create Langfuse client: {e}")
        return None


def is_v3_client(client) -> bool:
    """Check if the client is a Langfuse v3 client."""
    return getattr(client, '_is_v3', False)


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


def parse_datetime(value) -> datetime | None:
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return None
    return None


def calculate_latency_ms(start_time, end_time) -> float | None:
    """Calculate latency in milliseconds between two timestamps."""
    start = parse_datetime(start_time)
    end = parse_datetime(end_time)
    if start and end:
        return (end - start).total_seconds() * 1000
    return None


def fetch_traces_from_langfuse(
    client,
    user_id: str,
    limit: int = 50,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    name: str | None = None,
    tags: list[str] | None = None,
) -> list:
    """
    Fetch traces from Langfuse using the appropriate SDK method.
    Supports both Langfuse SDK v3 and v2.

    In v3, the primary method is `fetch_traces()` which is a high-level convenience method
    that works the same as v2.

    Args:
        client: Langfuse client
        user_id: User ID to filter by
        limit: Maximum number of traces to fetch
        from_timestamp: Start date filter (inclusive)
        to_timestamp: End date filter (inclusive)
        name: Filter traces by name (partial match)
        tags: Filter traces by tags
    """
    trace_data = []
    # Langfuse API has a max limit of 100 per request
    page_size = min(100, limit)

    sdk_version = getattr(client, '_sdk_version', 'unknown')
    logger.info(f"Langfuse SDK version: {sdk_version}, is_v3: {is_v3_client(client)}")
    logger.info(f"Looking for traces with user_id: {user_id}, limit={limit}, page_size={page_size}")
    if from_timestamp:
        logger.info(f"  from_timestamp: {from_timestamp}")
    if to_timestamp:
        logger.info(f"  to_timestamp: {to_timestamp}")
    if name:
        logger.info(f"  name filter: {name}")

    # ==========================================================================
    # Primary method: fetch_traces() - works in both v2 and v3
    # ==========================================================================
    if hasattr(client, 'fetch_traces'):
        try:
            page = 1
            all_traces = []
            max_pages = (limit + page_size - 1) // page_size

            filter_kwargs = {"user_id": user_id, "limit": page_size}
            if from_timestamp:
                filter_kwargs["from_timestamp"] = from_timestamp
            if to_timestamp:
                filter_kwargs["to_timestamp"] = to_timestamp
            if name:
                filter_kwargs["name"] = name
            if tags:
                filter_kwargs["tags"] = tags

            while page <= max_pages:
                logger.debug(f"Fetching page {page} with filters: {filter_kwargs}")
                response = client.fetch_traces(**filter_kwargs, page=page)

                page_traces = []
                if hasattr(response, 'data'):
                    page_traces = response.data or []
                elif isinstance(response, list):
                    page_traces = response
                elif isinstance(response, dict):
                    page_traces = response.get('data', [])

                logger.debug(f"Page {page} returned {len(page_traces)} traces")

                if not page_traces:
                    break

                all_traces.extend(page_traces)

                if len(page_traces) < page_size:
                    break

                page += 1

            trace_data = all_traces
            logger.info(f"fetch_traces returned {len(trace_data)} traces for user_id={user_id}")

            if trace_data:
                first = trace_data[0]
                logger.debug(f"Sample trace: type={type(first)}, user_id={get_attr(first, 'user_id', 'userId')}")
                return trace_data

        except Exception as e:
            logger.warning(f"fetch_traces with user_id failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    # ==========================================================================
    # Fallback for v3: Try api.trace.list if available
    # ==========================================================================
    if is_v3_client(client) and hasattr(client, 'api') and hasattr(client.api, 'trace'):
        try:
            logger.info("Trying v3 fallback: client.api.trace.list")
            all_traces = []
            page = 1

            while len(all_traces) < limit:
                list_kwargs = {"user_id": user_id, "limit": page_size, "page": page}
                if from_timestamp:
                    list_kwargs["from_timestamp"] = from_timestamp
                if to_timestamp:
                    list_kwargs["to_timestamp"] = to_timestamp

                response = client.api.trace.list(**list_kwargs)
                page_traces = response.data if hasattr(response, 'data') else (response if isinstance(response, list) else [])

                if not page_traces:
                    break
                all_traces.extend(page_traces)
                if len(page_traces) < page_size:
                    break
                page += 1

            trace_data = all_traces[:limit]
            logger.info(f"v3 api.trace.list returned {len(trace_data)} traces")
            if trace_data:
                return trace_data
        except Exception as e:
            logger.warning(f"v3 api.trace.list failed: {e}")


    # ==========================================================================
    # Fallback: fetch without user_id filter and filter manually
    # ==========================================================================
    max_pages = (limit + page_size - 1) // page_size  # ceil division
    if hasattr(client, 'fetch_traces'):
        try:
            page = 1
            all_traces = []
            fallback_kwargs = {"limit": page_size}
            if from_timestamp:
                fallback_kwargs["from_timestamp"] = from_timestamp
            if to_timestamp:
                fallback_kwargs["to_timestamp"] = to_timestamp

            while page <= max_pages:
                logger.info(f"Fallback fetching page {page} without user filter, limit={page_size}")
                response = client.fetch_traces(**fallback_kwargs, page=page)

                page_traces = []
                if hasattr(response, 'data'):
                    page_traces = response.data or []
                elif isinstance(response, list):
                    page_traces = response
                elif isinstance(response, dict):
                    page_traces = response.get('data', [])

                if not page_traces:
                    break

                all_traces.extend(page_traces)

                if len(page_traces) < page_size:
                    break

                page += 1

            logger.info(f"Fallback got {len(all_traces)} total traces, filtering by user_id={user_id}")

            # Filter by user_id
            trace_data = [t for t in all_traces if str(get_attr(t, 'user_id', 'userId') or '') == str(user_id)]
            logger.info(f"After user_id filter: {len(trace_data)} traces")

            # Apply client-side name filter if provided (partial match)
            if name and trace_data:
                name_lower = name.lower()
                trace_data = [t for t in trace_data if name_lower in (get_attr(t, 'name') or '').lower()]
                logger.info(f"After name filter: {len(trace_data)} traces")

            if trace_data:
                return trace_data
            elif all_traces:
                sample_uids = set(str(get_attr(t, 'user_id', 'userId') or '') for t in all_traces[:20] if get_attr(t, 'user_id', 'userId'))
                logger.warning(f"No traces for user_id={user_id}. Sample user_ids: {sample_uids}")

        except Exception as e:
            logger.warning(f"Fallback fetch_traces failed: {e}")

    # ==========================================================================
    # Last resort: Try direct client API (works for both v2 and v3)
    # ==========================================================================
    if hasattr(client, 'client') and hasattr(client.client, 'traces'):
        try:
            logger.info(f"Attempting direct client.traces.list(user_id={user_id})")
            response = client.client.traces.list(user_id=user_id, limit=page_size)
            if hasattr(response, 'data'):
                trace_data = response.data or []
            elif isinstance(response, list):
                trace_data = response
            logger.info(f"Direct traces API returned {len(trace_data)} traces")
            if trace_data:
                return trace_data
        except Exception as e:
            logger.debug(f"Direct traces API failed: {e}")

    logger.warning(f"All methods failed to fetch traces for user_id={user_id}")
    return trace_data


def fetch_observations_for_trace(client, trace_id: str) -> list:
    """
    Fetch observations (spans) for a specific trace.
    Supports both Langfuse SDK v3 and v2.
    """
    observations = []

    # Primary method: fetch_observations() - works in both v2 and v3
    if hasattr(client, 'fetch_observations'):
        try:
            response = client.fetch_observations(trace_id=trace_id, limit=100)
            if hasattr(response, 'data'):
                observations = response.data or []
            elif isinstance(response, list):
                observations = response
            elif isinstance(response, dict) and 'data' in response:
                observations = response.get('data', [])
            if observations:
                return observations
        except Exception as e:
            logger.debug(f"fetch_observations failed for trace {trace_id}: {e}")

    # Fallback for v3: Try api.observations.get_many
    if is_v3_client(client) and hasattr(client, 'api') and hasattr(client.api, 'observations'):
        obs_client = client.api.observations
        if hasattr(obs_client, 'get_many'):
            try:
                response = obs_client.get_many(trace_id=trace_id, limit=100)
                if hasattr(response, 'data'):
                    observations = response.data or []
                elif isinstance(response, list):
                    observations = response
                if observations:
                    return observations
            except Exception as e:
                logger.debug(f"api.observations.get_many failed for trace {trace_id}: {e}")

        if hasattr(obs_client, 'list'):
            try:
                response = obs_client.list(trace_id=trace_id, limit=100)
                if hasattr(response, 'data'):
                    observations = response.data or []
                elif isinstance(response, list):
                    observations = response
                if observations:
                    return observations
            except Exception as e:
                logger.debug(f"api.observations.list failed for trace {trace_id}: {e}")

    # Fallback for v3: Try api.observations_v_2
    if is_v3_client(client) and hasattr(client, 'api') and hasattr(client.api, 'observations_v_2'):
        obs_v2_client = client.api.observations_v_2
        if hasattr(obs_v2_client, 'get_many'):
            try:
                response = obs_v2_client.get_many(trace_id=trace_id, limit=100)
                if hasattr(response, 'data'):
                    observations = response.data or []
                elif isinstance(response, list):
                    observations = response
                if observations:
                    return observations
            except Exception as e:
                logger.debug(f"api.observations_v_2.get_many failed for trace {trace_id}: {e}")

    # Fallback: Try direct client observations API
    if hasattr(client, 'client') and hasattr(client.client, 'observations'):
        try:
            response = client.client.observations.list(trace_id=trace_id, limit=100)
            if hasattr(response, 'data'):
                observations = response.data or []
            elif isinstance(response, list):
                observations = response
            if observations:
                return observations
        except Exception as e:
            logger.debug(f"client.client.observations.list failed for trace {trace_id}: {e}")

    return observations


def parse_observation(obs: Any) -> ObservationResponse:
    """Parse a Langfuse observation into our response model."""
    obs_id = get_attr(obs, 'id', default='')
    trace_id = get_attr(obs, 'trace_id', 'traceId', default='')

    start_time = parse_datetime(get_attr(obs, 'start_time', 'startTime'))
    end_time = parse_datetime(get_attr(obs, 'end_time', 'endTime'))
    completion_start = parse_datetime(get_attr(obs, 'completion_start_time', 'completionStartTime'))

    latency_ms = calculate_latency_ms(start_time, end_time)
    ttft_ms = calculate_latency_ms(start_time, completion_start) if completion_start else None

    # Extract usage data
    usage = get_attr(obs, 'usage', default={})
    if isinstance(usage, dict):
        input_tokens = usage.get('input') or usage.get('inputTokens') or usage.get('prompt_tokens') or 0
        output_tokens = usage.get('output') or usage.get('outputTokens') or usage.get('completion_tokens') or 0
        total_tokens = usage.get('total') or usage.get('totalTokens') or (input_tokens + output_tokens)
    elif hasattr(usage, 'input'):
        input_tokens = usage.input or 0
        output_tokens = getattr(usage, 'output', 0) or 0
        total_tokens = getattr(usage, 'total', 0) or (input_tokens + output_tokens)
    else:
        input_tokens = get_attr(obs, 'input_tokens', 'inputTokens', 'promptTokens', default=0)
        output_tokens = get_attr(obs, 'output_tokens', 'outputTokens', 'completionTokens', default=0)
        total_tokens = input_tokens + output_tokens

    # Extract cost data - Langfuse SDK returns snake_case attributes
    # Try all variants: snake_case (SDK), camelCase (API), and calculated versions
    input_cost = float(get_attr(obs,
        'calculated_input_cost', 'calculatedInputCost',
        'input_cost', 'inputCost', default=0) or 0)
    output_cost = float(get_attr(obs,
        'calculated_output_cost', 'calculatedOutputCost',
        'output_cost', 'outputCost', default=0) or 0)
    total_cost = float(get_attr(obs,
        'calculated_total_cost', 'calculatedTotalCost',
        'total_cost', 'totalCost', default=0) or 0)
    if not total_cost and (input_cost or output_cost):
        total_cost = input_cost + output_cost

    return ObservationResponse(
        id=str(obs_id),
        trace_id=str(trace_id),
        name=get_attr(obs, 'name'),
        type=get_attr(obs, 'type'),
        model=get_attr(obs, 'model'),
        start_time=start_time,
        end_time=end_time,
        completion_start_time=completion_start,
        latency_ms=latency_ms,
        time_to_first_token_ms=ttft_ms,
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        total_tokens=int(total_tokens or 0),
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=total_cost,
        input=get_attr(obs, 'input'),
        output=get_attr(obs, 'output'),
        metadata=get_attr(obs, 'metadata'),
        level=get_attr(obs, 'level'),
        status_message=get_attr(obs, 'status_message', 'statusMessage'),
        parent_observation_id=get_attr(obs, 'parent_observation_id', 'parentObservationId'),
    )


def parse_trace_to_list_item(trace: Any, observations: list | None = None) -> TraceListItem:
    """Parse a trace into a list item (lighter format)."""
    trace_id = get_attr(trace, 'id', default='')
    timestamp = parse_datetime(get_attr(trace, 'timestamp'))

    # If we have observations, aggregate from them
    total_tokens = 0
    total_cost = 0.0
    models_used = set()
    latencies = []

    if observations:
        for obs in observations:
            parsed = parse_observation(obs) if not isinstance(obs, ObservationResponse) else obs
            total_tokens += parsed.total_tokens
            total_cost += parsed.total_cost
            if parsed.model:
                models_used.add(parsed.model)
            if parsed.latency_ms:
                latencies.append(parsed.latency_ms)
    else:
        # Fall back to trace-level data
        total_tokens = get_attr(trace, 'totalTokens', 'total_tokens', default=0) or 0
        total_cost = float(get_attr(trace,
            'calculated_total_cost', 'calculatedTotalCost',
            'total_cost', 'totalCost', default=0) or 0)

    # Calculate trace-level latency from first/last observation or trace times
    latency_ms = max(latencies) if latencies else None

    return TraceListItem(
        id=str(trace_id),
        name=get_attr(trace, 'name'),
        session_id=get_attr(trace, 'session_id', 'sessionId'),
        timestamp=timestamp,
        total_tokens=int(total_tokens),
        total_cost=total_cost,
        latency_ms=latency_ms,
        models_used=list(models_used),
        observation_count=len(observations) if observations else 0,
        level=get_attr(trace, 'level'),
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/status")
async def get_langfuse_status() -> LangfuseStatusResponse:
    """Check if Langfuse is connected and available."""
    host = os.getenv("LANGFUSE_HOST")
    client = get_langfuse_client()

    if not client:
        return LangfuseStatusResponse(
            connected=False,
            host=host,
            message="Langfuse not configured. Set LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and LANGFUSE_HOST in your .env file."
        )

    try:
        # v3 uses auth_check(), v2 uses client.health.health()
        if is_v3_client(client):
            # v3 health check uses auth_check()
            if client.auth_check():
                sdk_version = "v3"
                return LangfuseStatusResponse(
                    connected=True,
                    host=host,
                    message=f"Langfuse connected successfully (SDK {sdk_version})"
                )
            else:
                return LangfuseStatusResponse(
                    connected=False,
                    host=host,
                    message="Langfuse v3 auth_check() failed - check credentials"
                )
        else:
            # v2 health check
            from langfuse.api.core.request_options import RequestOptions
            client.client.health.health(request_options=RequestOptions(timeout_in_seconds=2))
            sdk_version = "v2"
            return LangfuseStatusResponse(
                connected=True,
                host=host,
                message=f"Langfuse connected successfully (SDK {sdk_version})"
            )
    except Exception as e:
        return LangfuseStatusResponse(
            connected=False,
            host=host,
            message=f"Cannot connect to Langfuse: {str(e)}"
        )


@router.get("/debug")
async def debug_langfuse_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """
    Debug endpoint to diagnose observability data issues.
    Shows raw data from Langfuse to help troubleshoot.
    """
    client = get_langfuse_client()
    if not client:
        return {"error": "Langfuse not configured"}

    result = {
        "current_user_id": str(current_user.id),
        "langfuse_methods": [],
        "all_traces_count": 0,
        "user_traces_count": 0,
        "sample_user_ids": [],
        "sample_traces": [],
        "errors": [],
    }

    # Check what methods are available
    for method in ['fetch_traces', 'fetch_observations', 'fetch_trace', 'get_traces']:
        if hasattr(client, method):
            result["langfuse_methods"].append(method)

    # Try to fetch all traces without filter
    try:
        if hasattr(client, 'fetch_traces'):
            response = client.fetch_traces(limit=100)
            all_traces = []
            if hasattr(response, 'data'):
                all_traces = response.data or []
            elif isinstance(response, list):
                all_traces = response
            elif isinstance(response, dict):
                all_traces = response.get('data', [])

            result["all_traces_count"] = len(all_traces)

            # Collect unique user_ids
            user_ids = set()
            for trace in all_traces:
                uid = get_attr(trace, 'user_id', 'userId')
                if uid:
                    user_ids.add(str(uid))

            result["sample_user_ids"] = list(user_ids)[:20]

            # Count traces for current user
            user_traces = [t for t in all_traces if str(get_attr(t, 'user_id', 'userId') or '') == str(current_user.id)]
            result["user_traces_count"] = len(user_traces)

            # Sample trace data (first 3 traces)
            for trace in all_traces[:3]:
                sample = {
                    "id": str(get_attr(trace, 'id', default=''))[:20],
                    "name": get_attr(trace, 'name'),
                    "user_id": str(get_attr(trace, 'user_id', 'userId') or ''),
                    "session_id": get_attr(trace, 'session_id', 'sessionId'),
                    "timestamp": str(get_attr(trace, 'timestamp', default=''))[:30],
                }
                result["sample_traces"].append(sample)

    except Exception as e:
        result["errors"].append(f"fetch_traces error: {str(e)}")
        import traceback
        result["errors"].append(traceback.format_exc())

    return result


@router.get("/debug/trace/{trace_id}")
async def debug_trace_detail(
    trace_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """
    Debug endpoint to see raw trace and observation data.
    Helps troubleshoot why trace details might not be showing.
    """
    client = get_langfuse_client()
    if not client:
        return {"error": "Langfuse not configured"}

    result = {
        "trace_id": trace_id,
        "current_user_id": str(current_user.id),
        "sdk_version": getattr(client, '_sdk_version', 'unknown'),
        "is_v3": is_v3_client(client),
        "trace_found": False,
        "trace_data": None,
        "observations_count": 0,
        "observations_sample": [],
        "errors": [],
    }

    # Fetch trace
    try:
        if hasattr(client, 'fetch_trace'):
            response = client.fetch_trace(trace_id)
            trace = response.data if hasattr(response, 'data') else response
            if trace:
                result["trace_found"] = True
                result["trace_data"] = {
                    "id": get_attr(trace, 'id'),
                    "name": get_attr(trace, 'name'),
                    "user_id": get_attr(trace, 'user_id', 'userId'),
                    "session_id": get_attr(trace, 'session_id', 'sessionId'),
                    "input": str(get_attr(trace, 'input'))[:200] if get_attr(trace, 'input') else None,
                    "output": str(get_attr(trace, 'output'))[:200] if get_attr(trace, 'output') else None,
                }
    except Exception as e:
        result["errors"].append(f"fetch_trace error: {str(e)}")

    # Fetch observations
    try:
        raw_observations = fetch_observations_for_trace(client, trace_id)
        result["observations_count"] = len(raw_observations)

        # Sample first 5 observations
        for obs in raw_observations[:5]:
            obs_sample = {
                "id": get_attr(obs, 'id'),
                "name": get_attr(obs, 'name'),
                "type": get_attr(obs, 'type'),
                "model": get_attr(obs, 'model'),
                "input_preview": str(get_attr(obs, 'input'))[:100] if get_attr(obs, 'input') else None,
                "output_preview": str(get_attr(obs, 'output'))[:100] if get_attr(obs, 'output') else None,
            }
            # Extract usage
            usage = get_attr(obs, 'usage', default={})
            if usage:
                if isinstance(usage, dict):
                    obs_sample["usage"] = usage
                elif hasattr(usage, '__dict__'):
                    obs_sample["usage"] = {k: v for k, v in usage.__dict__.items() if not k.startswith('_')}
            result["observations_sample"].append(obs_sample)
    except Exception as e:
        result["errors"].append(f"fetch_observations error: {str(e)}")
        import traceback
        result["errors"].append(traceback.format_exc())

    return result


@router.get("/traces")
async def get_user_traces(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    page: Annotated[int, Query(ge=1)] = 1,
    session_id: Annotated[str | None, Query()] = None,
    from_date: Annotated[str | None, Query(description="Start date (YYYY-MM-DD). Defaults to 7 days ago.")] = None,
    to_date: Annotated[str | None, Query(description="End date (YYYY-MM-DD). Defaults to today.")] = None,
) -> TracesListResponse:
    """
    Get traces for the current user with aggregated metrics.

    Date filtering:
    - Defaults to last 7 days if no dates specified
    - Use from_date/to_date for custom ranges

    Performance note: This endpoint uses trace-level metrics.
    For detailed observations, use GET /traces/{trace_id}.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        # Parse date range with sensible defaults (last 7 days)
        now = datetime.now(timezone.utc)
        if to_date:
            to_timestamp = datetime.strptime(to_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        else:
            to_timestamp = now

        if from_date:
            from_timestamp = datetime.strptime(from_date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, tzinfo=timezone.utc
            )
        else:
            # Default to last 7 days
            from_timestamp = now - timedelta(days=7)

        # Fetch traces with date filter - request more than needed for filtering
        # but cap at a reasonable limit for performance
        fetch_limit = min(limit * page + 50, 200)  # Fetch enough for pagination + buffer
        raw_traces = fetch_traces_from_langfuse(
            client,
            user_id,
            limit=fetch_limit,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )

        # Filter by session if specified
        if session_id:
            raw_traces = [t for t in raw_traces if get_attr(t, 'session_id', 'sessionId') == session_id]

        # Parse traces WITHOUT fetching observations (use trace-level metrics)
        # This eliminates the N+1 query problem - observations are fetched only in detail view
        traces = []
        for trace in raw_traces:
            trace_id = get_attr(trace, 'id')
            if not trace_id:
                continue
            # Use trace-level metrics, don't fetch observations for list view
            trace_item = parse_trace_to_list_item(trace, observations=None)
            traces.append(trace_item)

        # Sort by timestamp descending
        traces.sort(key=lambda t: t.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # Apply pagination
        total = len(traces)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_traces = traces[start_idx:end_idx]

        return TracesListResponse(
            traces=paginated_traces,
            total=total,
            page=page,
            limit=limit
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching traces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch traces: {str(e)}")


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TraceDetailResponse:
    """
    Get detailed trace information including all observations (spans).
    Shows the full execution timeline with LLM calls, tool calls, etc.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        logger.info(f"Fetching trace detail for trace_id={trace_id}, user_id={current_user.id}")

        # Fetch the trace - try fetch_trace first (works in both v2 and v3)
        trace = None

        # Primary: client.fetch_trace(trace_id)
        if hasattr(client, 'fetch_trace'):
            try:
                response = client.fetch_trace(trace_id)
                trace = response.data if hasattr(response, 'data') else response
            except Exception as e:
                logger.debug(f"fetch_trace failed: {e}")

        # Fallback for v3: client.api.trace.get(trace_id)
        if not trace and is_v3_client(client) and hasattr(client, 'api') and hasattr(client.api, 'trace'):
            try:
                trace = client.api.trace.get(trace_id)
            except Exception as e:
                logger.debug(f"v3 api.trace.get failed: {e}")

        # Fallback for v3: client.client.traces.get(trace_id)
        if not trace and is_v3_client(client) and hasattr(client, 'client') and hasattr(client.client, 'traces'):
            try:
                trace = client.client.traces.get(trace_id)
            except Exception as e:
                logger.debug(f"v3 traces.get failed: {e}")

        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Security check
        trace_user_id = get_attr(trace, 'user_id', 'userId')
        if trace_user_id and str(trace_user_id) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Trace not found")

        # Fetch observations
        raw_observations = fetch_observations_for_trace(client, trace_id)
        observations = [parse_observation(obs) for obs in raw_observations]

        # Sort observations by start time
        observations.sort(key=lambda o: o.start_time or datetime.min.replace(tzinfo=timezone.utc))

        # Aggregate metrics from observations
        total_tokens = sum(o.total_tokens for o in observations)
        input_tokens = sum(o.input_tokens for o in observations)
        output_tokens = sum(o.output_tokens for o in observations)
        total_cost = sum(o.total_cost for o in observations)
        models_used = list(set(o.model for o in observations if o.model))

        # Calculate trace latency
        latency_ms = None
        if observations:
            start_times = [o.start_time for o in observations if o.start_time]
            end_times = [o.end_time for o in observations if o.end_time]
            if start_times and end_times:
                latency_ms = (max(end_times) - min(start_times)).total_seconds() * 1000

        return TraceDetailResponse(
            id=str(get_attr(trace, 'id')),
            name=get_attr(trace, 'name'),
            user_id=trace_user_id,
            session_id=get_attr(trace, 'session_id', 'sessionId'),
            timestamp=parse_datetime(get_attr(trace, 'timestamp')),
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            latency_ms=latency_ms,
            models_used=models_used,
            observations=observations,
            input=get_attr(trace, 'input'),
            output=get_attr(trace, 'output'),
            metadata=get_attr(trace, 'metadata'),
            tags=get_attr(trace, 'tags', default=[]) or [],
            level=get_attr(trace, 'level'),
            status=get_attr(trace, 'status'),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching trace detail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch trace: {str(e)}")


@router.get("/sessions")
async def get_user_sessions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    # Filter parameters
    from_date: Annotated[str | None, Query(description="Start date (YYYY-MM-DD). Defaults to 7 days ago.")] = None,
    to_date: Annotated[str | None, Query(description="End date (YYYY-MM-DD). Defaults to today.")] = None,
    search: Annotated[str | None, Query(description="Search by session ID or trace name")] = None,
) -> SessionsListResponse:
    """
    Get chat sessions for the current user with aggregated metrics.

    Date filtering:
    - Defaults to last 7 days if no dates specified
    - Use from_date/to_date for custom ranges

    Performance note: Uses trace-level metrics for fast loading.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        # Parse date filters with sensible defaults (last 7 days)
        now = datetime.now(timezone.utc)
        if to_date:
            try:
                to_timestamp = datetime.strptime(to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
        else:
            to_timestamp = now

        if from_date:
            try:
                from_timestamp = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
        else:
            # Default to last 7 days
            from_timestamp = now - timedelta(days=7)

        # Fetch traces with date filters - limit to reasonable amount
        raw_traces = fetch_traces_from_langfuse(
            client, user_id, limit=200,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )

        # Group by session - use trace-level metrics (NO observation fetching)
        sessions_data: dict[str, dict] = {}

        for trace in raw_traces:
            session_id = get_attr(trace, 'session_id', 'sessionId')
            if not session_id:
                continue

            timestamp = parse_datetime(get_attr(trace, 'timestamp'))

            # Use trace-level metrics instead of fetching observations (eliminates N+1)
            trace_tokens = get_attr(trace, 'totalTokens', 'total_tokens', default=0) or 0
            trace_cost = float(get_attr(trace,
                'calculated_total_cost', 'calculatedTotalCost',
                'total_cost', 'totalCost', default=0) or 0)

            if session_id not in sessions_data:
                sessions_data[session_id] = {
                    "session_id": session_id,
                    "trace_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "timestamps": [],
                    "models": set(),
                }

            sessions_data[session_id]["trace_count"] += 1
            sessions_data[session_id]["total_tokens"] += trace_tokens
            sessions_data[session_id]["total_cost"] += trace_cost
            if timestamp:
                sessions_data[session_id]["timestamps"].append(timestamp)

        # Build response
        sessions = []
        for sid, data in sessions_data.items():
            timestamps = data["timestamps"]
            sessions.append(SessionListItem(
                session_id=sid,
                trace_count=data["trace_count"],
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
                first_trace_at=min(timestamps) if timestamps else None,
                last_trace_at=max(timestamps) if timestamps else None,
                models_used=list(data["models"]),
            ))

        # Apply search filter (client-side search by session ID)
        if search:
            search_lower = search.lower()
            sessions = [s for s in sessions if search_lower in s.session_id.lower()]

        # Sort by last activity
        sessions.sort(key=lambda s: s.last_trace_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        total_count = len(sessions)
        sessions = sessions[:limit]

        return SessionsListResponse(sessions=sessions, total=total_count)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SessionDetailResponse:
    """
    Get detailed session information including all traces and per-model breakdown.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        # Fetch traces for this user
        raw_traces = fetch_traces_from_langfuse(client, user_id, limit=100)

        # Filter to this session
        session_traces = [t for t in raw_traces if get_attr(t, 'session_id', 'sessionId') == session_id]

        if not session_traces:
            raise HTTPException(status_code=404, detail="Session not found")

        # Process traces and collect metrics
        traces = []
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        total_observations = 0
        latencies = []
        models_used: dict[str, dict] = {}
        timestamps = []

        for trace in session_traces:
            trace_id = get_attr(trace, 'id')
            timestamp = parse_datetime(get_attr(trace, 'timestamp'))
            if timestamp:
                timestamps.append(timestamp)

            # Fetch observations
            try:
                observations = fetch_observations_for_trace(client, str(trace_id))
                parsed_obs = [parse_observation(obs) for obs in observations]
            except:
                parsed_obs = []

            total_observations += len(parsed_obs)

            for obs in parsed_obs:
                total_tokens += obs.total_tokens
                input_tokens += obs.input_tokens
                output_tokens += obs.output_tokens
                total_cost += obs.total_cost
                if obs.latency_ms:
                    latencies.append(obs.latency_ms)

                if obs.model:
                    if obs.model not in models_used:
                        models_used[obs.model] = {"tokens": 0, "cost": 0.0, "calls": 0}
                    models_used[obs.model]["tokens"] += obs.total_tokens
                    models_used[obs.model]["cost"] += obs.total_cost
                    models_used[obs.model]["calls"] += 1

            trace_item = parse_trace_to_list_item(trace, parsed_obs)
            traces.append(trace_item)

        # Sort traces by timestamp
        traces.sort(key=lambda t: t.timestamp or datetime.min.replace(tzinfo=timezone.utc))

        # Calculate session duration
        duration = None
        if len(timestamps) >= 2:
            duration = (max(timestamps) - min(timestamps)).total_seconds()

        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return SessionDetailResponse(
            session_id=session_id,
            trace_count=len(traces),
            observation_count=total_observations,
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            avg_latency_ms=avg_latency,
            first_trace_at=min(timestamps) if timestamps else None,
            last_trace_at=max(timestamps) if timestamps else None,
            duration_seconds=duration,
            models_used=models_used,
            traces=traces,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session detail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch session: {str(e)}")


@router.get("/metrics")
async def get_user_metrics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    # Filter parameters
    from_date: Annotated[str | None, Query(description="Start date (YYYY-MM-DD). Defaults to 7 days ago.")] = None,
    to_date: Annotated[str | None, Query(description="End date (YYYY-MM-DD). Defaults to today.")] = None,
    search: Annotated[str | None, Query(description="Search by trace name")] = None,
    models: Annotated[str | None, Query(description="Comma-separated model names to filter")] = None,
    tz_offset: Annotated[int | None, Query(description="Timezone offset in minutes from UTC (e.g., 330 for IST)")] = None,
    include_model_breakdown: Annotated[bool, Query(description="Include per-model breakdown (slower)")] = False,
) -> MetricsResponse:
    """
    Get comprehensive aggregated metrics for the current user.

    Date filtering:
    - Defaults to last 7 days if no dates specified
    - Use from_date/to_date for custom ranges

    Performance notes:
    - Basic metrics use trace-level data (fast)
    - Set include_model_breakdown=true for per-model stats (slower, fetches observations)
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        # Parse date filters with sensible defaults (last 7 days)
        now = datetime.now(timezone.utc)
        if to_date:
            try:
                to_timestamp = datetime.strptime(to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
        else:
            to_timestamp = now

        if from_date:
            try:
                from_timestamp = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
        else:
            # Default to last N days based on 'days' parameter
            from_timestamp = now - timedelta(days=days)

        # Parse model filter
        model_filter = None
        if models:
            model_filter = [m.strip() for m in models.split(",") if m.strip()]

        # Fetch traces with date filters - limit to reasonable amount for performance
        raw_traces = fetch_traces_from_langfuse(
            client,
            user_id,
            limit=150,  # Reduced from 500 for faster loading
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            name=search,
        )

        # Aggregate metrics
        total_traces = len(raw_traces)
        total_observations = 0
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        latencies = []
        sessions = set()

        model_data: dict[str, dict] = defaultdict(lambda: {
            "call_count": 0, "total_tokens": 0, "input_tokens": 0,
            "output_tokens": 0, "total_cost": 0.0, "latencies": []
        })

        daily_data: dict[str, dict] = defaultdict(lambda: {
            "trace_count": 0, "observation_count": 0, "total_tokens": 0, "total_cost": 0.0
        })

        flow_data: dict[str, dict] = defaultdict(lambda: {
            "count": 0, "tokens": 0, "cost": 0.0
        })

        for trace in raw_traces:
            trace_id = get_attr(trace, 'id')
            trace_name = get_attr(trace, 'name') or 'Unknown'
            session_id = get_attr(trace, 'session_id', 'sessionId')
            timestamp = parse_datetime(get_attr(trace, 'timestamp'))

            if session_id:
                sessions.add(session_id)

            # Apply timezone offset if provided to get local date
            if timestamp and tz_offset is not None:
                local_timestamp = timestamp + timedelta(minutes=tz_offset)
                date_str = local_timestamp.strftime('%Y-%m-%d')
            else:
                date_str = timestamp.strftime('%Y-%m-%d') if timestamp else 'Unknown'
            daily_data[date_str]["trace_count"] += 1

            # Get trace-level cost (Langfuse stores this at trace level)
            trace_cost = float(get_attr(trace,
                'calculated_total_cost', 'calculatedTotalCost',
                'total_cost', 'totalCost', default=0) or 0)

            # Always fetch observations for accurate token counting
            # Tokens are stored at observation level in Langfuse, not trace level
            parsed_obs = []
            try:
                observations = fetch_observations_for_trace(client, str(trace_id))
                parsed_obs = [parse_observation(obs) for obs in observations]
            except Exception:
                parsed_obs = []

            # Calculate tokens from observations (accurate)
            trace_tokens = sum(obs.total_tokens for obs in parsed_obs)
            trace_input_tokens = sum(obs.input_tokens for obs in parsed_obs)
            trace_output_tokens = sum(obs.output_tokens for obs in parsed_obs)

            # Fall back to trace-level tokens if no observations found
            if trace_tokens == 0 and not parsed_obs:
                trace_tokens = get_attr(trace, 'totalTokens', 'total_tokens', default=0) or 0

            total_tokens += trace_tokens
            input_tokens += trace_input_tokens
            output_tokens += trace_output_tokens
            total_cost += trace_cost
            daily_data[date_str]["total_tokens"] += trace_tokens
            daily_data[date_str]["total_cost"] += trace_cost
            flow_data[trace_name]["count"] += 1
            flow_data[trace_name]["tokens"] += trace_tokens
            flow_data[trace_name]["cost"] += trace_cost

            # Process observations
            total_observations += len(parsed_obs)
            daily_data[date_str]["observation_count"] += len(parsed_obs)

            for obs in parsed_obs:
                # Apply model filter if specified
                if model_filter and obs.model:
                    if obs.model not in model_filter:
                        continue

                if obs.latency_ms:
                    latencies.append(obs.latency_ms)

                if obs.model:
                    model_data[obs.model]["call_count"] += 1
                    model_data[obs.model]["total_tokens"] += obs.total_tokens
                    model_data[obs.model]["input_tokens"] += obs.input_tokens
                    model_data[obs.model]["output_tokens"] += obs.output_tokens
                    model_data[obs.model]["total_cost"] += obs.total_cost
                    if obs.latency_ms:
                        model_data[obs.model]["latencies"].append(obs.latency_ms)

        # Calculate performance metrics
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        p95_latency = None
        if latencies:
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]

        # Build model usage list
        by_model = []
        for model, data in model_data.items():
            avg_lat = sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else None
            by_model.append(ModelUsageItem(
                model=model,
                call_count=data["call_count"],
                total_tokens=data["total_tokens"],
                input_tokens=data["input_tokens"],
                output_tokens=data["output_tokens"],
                total_cost=data["total_cost"],
                avg_latency_ms=avg_lat,
            ))
        by_model.sort(key=lambda m: m.total_tokens, reverse=True)

        # Build daily usage list
        by_date = []
        for date, data in sorted(daily_data.items()):
            if date != 'Unknown':
                by_date.append(DailyUsageItem(
                    date=date,
                    trace_count=data["trace_count"],
                    observation_count=data["observation_count"],
                    total_tokens=data["total_tokens"],
                    total_cost=data["total_cost"],
                ))
        by_date = by_date[-days:]  # Keep only last N days

        # Build top flows
        top_flows = [
            {"name": name, "count": data["count"], "tokens": data["tokens"], "cost": data["cost"]}
            for name, data in sorted(flow_data.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
        ]

        return MetricsResponse(
            total_traces=total_traces,
            total_observations=total_observations,
            total_sessions=len(sessions),
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            by_model=by_model,
            by_date=by_date,
            top_flows=top_flows,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")


# =============================================================================
# Agent/Flow Response Models
# =============================================================================

class AgentListItem(BaseModel):
    """Agent/Flow item for list views."""
    agent_id: str
    flow_name: str | None = None
    project_id: str | None = None  # Folder ID
    project_name: str | None = None  # Folder name
    trace_count: int = 0
    session_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None
    models_used: list[str] = []
    last_activity: datetime | None = None
    error_count: int = 0  # Count of ERROR/WARNING level observations


class AgentListResponse(BaseModel):
    """List of agents/flows."""
    agents: list[AgentListItem]
    total: int


class AgentDetailResponse(BaseModel):
    """Detailed agent/flow information."""
    agent_id: str
    flow_name: str | None = None
    trace_count: int = 0
    session_count: int = 0
    observation_count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None
    first_activity: datetime | None = None
    last_activity: datetime | None = None
    models_used: dict[str, dict] = {}  # model -> {tokens, cost, calls}
    sessions: list[SessionListItem] = []
    by_date: list[DailyUsageItem] = []


# =============================================================================
# Project Response Models
# =============================================================================

class ProjectListItem(BaseModel):
    """Project item for list views."""
    project_id: str
    project_name: str | None = None
    agent_count: int = 0
    trace_count: int = 0
    session_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    last_activity: datetime | None = None


class ProjectListResponse(BaseModel):
    """List of projects."""
    projects: list[ProjectListItem]
    total: int


class ProjectDetailResponse(BaseModel):
    """Detailed project information."""
    project_id: str
    project_name: str | None = None
    agent_count: int = 0
    trace_count: int = 0
    session_count: int = 0
    observation_count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None
    first_activity: datetime | None = None
    last_activity: datetime | None = None
    models_used: dict[str, dict] = {}  # model -> {tokens, cost, calls}
    agents: list[AgentListItem] = []
    by_date: list[DailyUsageItem] = []


# =============================================================================
# Helper: Extract flow/project info from trace
# =============================================================================

def extract_flow_project_info(trace) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Extract agent_id, flow_name, project_id, project_name from trace metadata/tags.

    Returns: (agent_id, flow_name, project_id, project_name)
    """
    metadata = get_attr(trace, 'metadata', default={}) or {}
    tags = get_attr(trace, 'tags', default=[]) or []

    # Try to get from metadata first (more reliable)
    agent_id = metadata.get('agent_id')
    flow_name = metadata.get('flow_name')
    project_id = metadata.get('project_id')
    project_name = metadata.get('project_name')

    # Fallback: parse from tags
    if not agent_id or not project_id:
        for tag in tags:
            if isinstance(tag, str):
                if tag.startswith('agent_id:') and not agent_id:
                    agent_id = tag.split(':', 1)[1]
                elif tag.startswith('flow_name:') and not flow_name:
                    flow_name = tag.split(':', 1)[1]
                elif tag.startswith('project_id:') and not project_id:
                    project_id = tag.split(':', 1)[1]
                elif tag.startswith('project_name:') and not project_name:
                    project_name = tag.split(':', 1)[1]

    # Fallback: use trace name as agent_id if not found
    if not agent_id:
        agent_id = get_attr(trace, 'name')

    return agent_id, flow_name, project_id, project_name


# =============================================================================
# Agent/Flow Endpoints
# =============================================================================

def _is_vertex_trace(trace_name: str | None) -> bool:
    """Check if a trace name looks like a vertex-level trace (not a flow trace)."""
    if not trace_name:
        return False
    # Vertex traces typically have patterns like:
    # - vertex_build_ChatOutput-xxxxx
    # - vertex_...-xxxxx
    # - ChatOutput-xxxxx (component names with hash suffix)
    vertex_prefixes = ('vertex_', 'vertex_build_')
    if trace_name.startswith(vertex_prefixes):
        return True
    # Also filter out component-level traces that look like: ComponentName-hash
    # These have format: SomeName-5chars where the suffix is a hash
    if '-' in trace_name:
        parts = trace_name.rsplit('-', 1)
        if len(parts) == 2 and len(parts[1]) == 5 and parts[1].isalnum():
            # Likely a component trace like "ChatOutput-0f2wN"
            return True
    return False


def _match_trace_to_flow(trace, flows_by_id: dict, flows_by_name: dict) -> tuple[str | None, str | None]:
    """
    Match a trace to a flow using metadata or name matching.

    Returns: (agent_id, flow_name) or (None, None) if no match
    """
    trace_name = get_attr(trace, 'name')
    metadata = get_attr(trace, 'metadata', default={}) or {}
    tags = get_attr(trace, 'tags', default=[]) or []

    # Skip vertex-level traces
    if _is_vertex_trace(trace_name):
        return None, None

    # Method 1: Check metadata for agent_id (most reliable)
    agent_id_from_meta = metadata.get('agent_id')
    if agent_id_from_meta and agent_id_from_meta in flows_by_id:
        flow = flows_by_id[agent_id_from_meta]
        return str(flow.id), flow.name

    # Method 2: Check tags for agent_id
    for tag in tags:
        if isinstance(tag, str) and tag.startswith('agent_id:'):
            fid = tag.split(':', 1)[1]
            if fid in flows_by_id:
                flow = flows_by_id[fid]
                return str(flow.id), flow.name

    # Method 3: Match by trace name to flow name
    if trace_name:
        # Exact match
        if trace_name in flows_by_name:
            flow = flows_by_name[trace_name]
            return str(flow.id), flow.name
        # Match "FlowName - UUID" format
        if ' - ' in trace_name:
            name_part = trace_name.rsplit(' - ', 1)[0]
            if name_part in flows_by_name:
                flow = flows_by_name[name_part]
                return str(flow.id), flow.name

    # Method 4: Use flow_name from metadata as a hint
    flow_name_from_meta = metadata.get('flow_name')
    if flow_name_from_meta and flow_name_from_meta in flows_by_name:
        flow = flows_by_name[flow_name_from_meta]
        return str(flow.id), flow.name

    return None, None


@router.get("/agents")
async def get_user_agents(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    from_date: Annotated[str | None, Query(description="Start date (YYYY-MM-DD)")] = None,
    to_date: Annotated[str | None, Query(description="End date (YYYY-MM-DD)")] = None,
) -> AgentListResponse:
    """
    Get all agents/flows for the current user with aggregated metrics.

    Uses database flows as source of truth and matches traces to flows.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)
        logger.info(f"Fetching agents for user_id: {user_id}")

        # Get all user flows from database (source of truth)
        flows_result = await session.exec(
            select(Agent).where(Agent.user_id == current_user.id, Agent.is_component == False)
        )
        user_flows = flows_result.all()

        # Build lookup dictionaries
        flows_by_id = {str(f.id): f for f in user_flows}
        flows_by_name = {f.name: f for f in user_flows}

        # Get all folders (projects) that contain these flows
        folder_ids = set(f.folder_id for f in user_flows if f.folder_id)
        folders_by_id: dict[str, Folder] = {}
        if folder_ids:
            folders_result = await session.exec(
                select(Folder).where(Folder.id.in_(folder_ids))
            )
            folders_by_id = {str(f.id): f for f in folders_result.all()}

        # Build agent_id to folder mapping
        flow_to_folder: dict[str, tuple[str | None, str | None]] = {}
        for flow in user_flows:
            folder_id = str(flow.folder_id) if flow.folder_id else None
            folder_name = folders_by_id.get(folder_id).name if folder_id and folder_id in folders_by_id else None
            flow_to_folder[str(flow.id)] = (folder_id, folder_name)

        logger.info(f"Found {len(user_flows)} flows in database for user")

        # Parse date filters
        from_timestamp = None
        to_timestamp = None
        if from_date:
            try:
                from_timestamp = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
        if to_date:
            try:
                to_timestamp = datetime.strptime(to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")

        # Fetch all traces from Langfuse
        raw_traces = fetch_traces_from_langfuse(
            client, user_id, limit=100,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )

        logger.info(f"Found {len(raw_traces)} traces from Langfuse")

        # Two-pass approach:
        # Pass 1: Identify which sessions belong to which agent (using flow-level traces)
        # Pass 2: Aggregate ALL traces in those sessions (including vertex traces for tokens)

        # Pass 1: Map sessions to agents
        session_to_agent: dict[str, tuple[str, str]] = {}
        agent_flow_traces: dict[str, list] = {}

        for trace in raw_traces:
            agent_id, flow_name = _match_trace_to_flow(trace, flows_by_id, flows_by_name)
            if agent_id:
                session_id = get_attr(trace, 'session_id', 'sessionId')
                if session_id:
                    session_to_agent[session_id] = (agent_id, flow_name)
                if agent_id not in agent_flow_traces:
                    agent_flow_traces[agent_id] = []
                agent_flow_traces[agent_id].append(trace)

        logger.info(f"Found {len(session_to_agent)} sessions mapped to agents")

        # Pass 2: Aggregate ALL traces by session, grouping by agent
        agents_data: dict[str, dict] = {}
        processed_traces: set[str] = set()

        for trace in raw_traces:
            trace_id = get_attr(trace, 'id')
            if trace_id in processed_traces:
                continue
            processed_traces.add(trace_id)

            session_id = get_attr(trace, 'session_id', 'sessionId')
            timestamp = parse_datetime(get_attr(trace, 'timestamp'))

            # Determine which agent this trace belongs to
            agent_id = None
            flow_name = None

            # First check if this trace directly matches an agent
            matched_agent_id, matched_flow_name = _match_trace_to_flow(trace, flows_by_id, flows_by_name)
            if matched_agent_id:
                agent_id, flow_name = matched_agent_id, matched_flow_name
            # Otherwise, check if it's part of an agent's session (vertex traces)
            elif session_id and session_id in session_to_agent:
                agent_id, flow_name = session_to_agent[session_id]

            if not agent_id:
                continue  # Skip traces not associated with any agent

            # Fetch observations for this trace
            try:
                observations = fetch_observations_for_trace(client, str(trace_id))
                parsed_obs = [parse_observation(obs) for obs in observations]
            except:
                parsed_obs = []

            trace_tokens = sum(o.total_tokens for o in parsed_obs)
            trace_cost = sum(o.total_cost for o in parsed_obs)
            models = set(o.model for o in parsed_obs if o.model)
            latencies = [o.latency_ms for o in parsed_obs if o.latency_ms]
            error_count = sum(1 for o in parsed_obs if o.level in ("ERROR", "WARNING"))

            if agent_id not in agents_data:
                agents_data[agent_id] = {
                    "agent_id": agent_id,
                    "flow_name": flow_name,
                    "trace_count": 0,
                    "sessions": set(),
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "models": set(),
                    "latencies": [],
                    "timestamps": [],
                    "error_count": 0,
                }

            # Only count flow-level traces in trace_count (not vertex traces)
            if matched_agent_id:
                agents_data[agent_id]["trace_count"] += 1

            # But aggregate tokens/cost from ALL traces (including vertex)
            agents_data[agent_id]["total_tokens"] += trace_tokens
            agents_data[agent_id]["total_cost"] += trace_cost
            agents_data[agent_id]["models"].update(models)
            agents_data[agent_id]["latencies"].extend(latencies)
            agents_data[agent_id]["error_count"] += error_count
            if session_id:
                agents_data[agent_id]["sessions"].add(session_id)
            if timestamp:
                agents_data[agent_id]["timestamps"].append(timestamp)

        # Build response
        agents = []
        for fid, data in agents_data.items():
            timestamps = data["timestamps"]
            latencies = data["latencies"]
            avg_latency = sum(latencies) / len(latencies) if latencies else None

            # Get project info from flow_to_folder mapping
            project_id, project_name = flow_to_folder.get(fid, (None, None))

            agents.append(AgentListItem(
                agent_id=fid,
                flow_name=data["flow_name"],
                project_id=project_id,
                project_name=project_name,
                trace_count=data["trace_count"],
                session_count=len(data["sessions"]),
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
                avg_latency_ms=avg_latency,
                models_used=list(data["models"]),
                last_activity=max(timestamps) if timestamps else None,
                error_count=data.get("error_count", 0),
            ))

        # Sort by last activity
        agents.sort(key=lambda a: a.last_activity or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        total_count = len(agents)
        agents = agents[:limit]

        return AgentListResponse(agents=agents, total=total_count)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch agents: {str(e)}")


@router.get("/agents/{agent_id}")
async def get_agent_detail(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    from_date: Annotated[str | None, Query(description="Start date (YYYY-MM-DD)")] = None,
    to_date: Annotated[str | None, Query(description="End date (YYYY-MM-DD)")] = None,
    tz_offset: Annotated[int | None, Query(description="Timezone offset in minutes from UTC")] = None,
) -> AgentDetailResponse:
    """
    Get detailed agent/flow information including sessions and metrics breakdown.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        # Get flow from database to verify it exists and get its name
        from uuid import UUID as PyUUID
        try:
            flow_uuid = PyUUID(agent_id)
            flow_result = await session.exec(
                select(Agent).where(Agent.id == flow_uuid, Agent.user_id == current_user.id)
            )
            flow = flow_result.first()
        except ValueError:
            flow = None

        if not flow:
            raise HTTPException(status_code=404, detail="Agent/Flow not found")

        flow_name = flow.name

        # Build lookup for matching traces
        flows_by_id = {str(flow.id): flow}
        flows_by_name = {flow.name: flow}

        # Parse date filters
        from_timestamp = None
        to_timestamp = None
        if from_date:
            try:
                from_timestamp = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format")
        if to_date:
            try:
                to_timestamp = datetime.strptime(to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format")

        # Fetch all traces
        raw_traces = fetch_traces_from_langfuse(
            client, user_id, limit=500,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )

        # Two-pass approach for agent detail
        # Pass 1: Identify this agent's sessions
        agent_sessions: set[str] = set()
        flow_trace_count = 0
        for trace in raw_traces:
            matched_fid, _ = _match_trace_to_flow(trace, flows_by_id, flows_by_name)
            if matched_fid == agent_id:
                flow_trace_count += 1
                session_id = get_attr(trace, 'session_id', 'sessionId')
                if session_id:
                    agent_sessions.add(session_id)

        if flow_trace_count == 0:
            return AgentDetailResponse(
                agent_id=agent_id,
                flow_name=flow_name,
                trace_count=0,
                session_count=0,
                observation_count=0,
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                total_cost=0.0,
                avg_latency_ms=None,
                first_activity=None,
                last_activity=None,
                models_used={},
                sessions=[],
                by_date=[],
            )

        # Pass 2: Process ALL traces that belong to this agent's sessions
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        total_observations = 0
        latencies = []
        models_used: dict[str, dict] = {}
        timestamps = []
        sessions_data: dict[str, dict] = {}
        daily_data: dict[str, dict] = defaultdict(lambda: {
            "trace_count": 0, "observation_count": 0, "total_tokens": 0, "total_cost": 0.0
        })
        processed_traces: set[str] = set()

        for trace in raw_traces:
            trace_id = get_attr(trace, 'id')
            if trace_id in processed_traces:
                continue

            session_id = get_attr(trace, 'session_id', 'sessionId')
            timestamp = parse_datetime(get_attr(trace, 'timestamp'))

            # Check if this trace belongs to this agent
            is_flow_trace = False
            matched_fid, _ = _match_trace_to_flow(trace, flows_by_id, flows_by_name)
            if matched_fid == agent_id:
                is_flow_trace = True
            elif session_id and session_id in agent_sessions:
                # Vertex trace in this agent's session
                pass
            else:
                continue  # Not related to this agent

            processed_traces.add(trace_id)

            # Fetch observations
            try:
                observations = fetch_observations_for_trace(client, str(trace_id))
                parsed_obs = [parse_observation(obs) for obs in observations]
            except:
                parsed_obs = []

            total_observations += len(parsed_obs)

            trace_tokens = 0
            trace_cost = 0.0
            trace_input_tokens = 0
            trace_output_tokens = 0

            for obs in parsed_obs:
                total_tokens += obs.total_tokens
                input_tokens += obs.input_tokens
                output_tokens += obs.output_tokens
                total_cost += obs.total_cost
                trace_tokens += obs.total_tokens
                trace_cost += obs.total_cost
                trace_input_tokens += obs.input_tokens
                trace_output_tokens += obs.output_tokens

                if obs.latency_ms:
                    latencies.append(obs.latency_ms)

                if obs.model:
                    if obs.model not in models_used:
                        models_used[obs.model] = {"tokens": 0, "cost": 0.0, "calls": 0}
                    models_used[obs.model]["tokens"] += obs.total_tokens
                    models_used[obs.model]["cost"] += obs.total_cost
                    models_used[obs.model]["calls"] += 1

            if timestamp:
                timestamps.append(timestamp)
                # Apply timezone offset if provided
                if tz_offset is not None:
                    local_ts = timestamp + timedelta(minutes=tz_offset)
                    date_str = local_ts.strftime('%Y-%m-%d')
                else:
                    date_str = timestamp.strftime('%Y-%m-%d')
                if is_flow_trace:
                    daily_data[date_str]["trace_count"] += 1
                daily_data[date_str]["observation_count"] += len(parsed_obs)
                daily_data[date_str]["total_tokens"] += trace_tokens
                daily_data[date_str]["total_cost"] += trace_cost

            # Build session data
            if session_id:
                if session_id not in sessions_data:
                    sessions_data[session_id] = {
                        "session_id": session_id,
                        "trace_count": 0,
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "timestamps": [],
                        "models": set(),
                    }
                if is_flow_trace:
                    sessions_data[session_id]["trace_count"] += 1
                sessions_data[session_id]["total_tokens"] += trace_tokens
                sessions_data[session_id]["total_cost"] += trace_cost
                if timestamp:
                    sessions_data[session_id]["timestamps"].append(timestamp)
                sessions_data[session_id]["models"].update(o.model for o in parsed_obs if o.model)

        # Build sessions list
        sessions = []
        for sid, data in sessions_data.items():
            ts = data["timestamps"]
            sessions.append(SessionListItem(
                session_id=sid,
                trace_count=data["trace_count"],
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
                first_trace_at=min(ts) if ts else None,
                last_trace_at=max(ts) if ts else None,
                models_used=list(data["models"]),
            ))
        sessions.sort(key=lambda s: s.last_trace_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # Build daily usage
        by_date = []
        for date, data in sorted(daily_data.items()):
            by_date.append(DailyUsageItem(
                date=date,
                trace_count=data["trace_count"],
                observation_count=data["observation_count"],
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
            ))

        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return AgentDetailResponse(
            agent_id=agent_id,
            flow_name=flow_name,
            trace_count=flow_trace_count,
            session_count=len(agent_sessions),
            observation_count=total_observations,
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            avg_latency_ms=avg_latency,
            first_activity=min(timestamps) if timestamps else None,
            last_activity=max(timestamps) if timestamps else None,
            models_used=models_used,
            sessions=sessions,
            by_date=by_date,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent detail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch agent: {str(e)}")


# =============================================================================
# Project Endpoints
# =============================================================================

@router.get("/projects")
async def get_user_projects(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ProjectListResponse:
    """
    Get all projects (folders) for the current user with aggregated metrics.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)
        logger.info(f"Fetching projects for user_id: {user_id}")

        # Get all user folders from database
        folders_result = await session.exec(
            select(Folder).where(Folder.user_id == current_user.id)
        )
        user_folders = folders_result.all()

        # Get all user flows
        flows_result = await session.exec(
            select(Agent).where(Agent.user_id == current_user.id, Agent.is_component == False)
        )
        user_flows = flows_result.all()

        # Build folder lookup and flow-to-folder mapping
        folders_by_id = {str(f.id): f for f in user_folders}
        flow_to_folder: dict[str, str] = {}
        for flow in user_flows:
            if flow.folder_id:
                flow_to_folder[str(flow.id)] = str(flow.folder_id)

        flows_by_id = {str(f.id): f for f in user_flows}
        flows_by_name = {f.name: f for f in user_flows}

        # Fetch all traces
        raw_traces = fetch_traces_from_langfuse(client, user_id, limit=100)

        # Aggregate by project
        projects_data: dict[str, dict] = {}

        for trace in raw_traces:
            # Match trace to flow
            matched_fid, _ = _match_trace_to_flow(trace, flows_by_id, flows_by_name)
            if not matched_fid:
                continue

            # Get folder for this flow
            folder_id = flow_to_folder.get(matched_fid)
            if not folder_id:
                continue

            timestamp = parse_datetime(get_attr(trace, 'timestamp'))
            session_id = get_attr(trace, 'session_id', 'sessionId')

            # Fetch observations
            trace_id = get_attr(trace, 'id')
            try:
                observations = fetch_observations_for_trace(client, str(trace_id))
                parsed_obs = [parse_observation(obs) for obs in observations]
            except:
                parsed_obs = []

            trace_tokens = sum(o.total_tokens for o in parsed_obs)
            trace_cost = sum(o.total_cost for o in parsed_obs)

            if folder_id not in projects_data:
                folder = folders_by_id.get(folder_id)
                projects_data[folder_id] = {
                    "project_id": folder_id,
                    "project_name": folder.name if folder else None,
                    "agents": set(),
                    "trace_count": 0,
                    "sessions": set(),
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "timestamps": [],
                }

            projects_data[folder_id]["agents"].add(matched_fid)
            projects_data[folder_id]["trace_count"] += 1
            projects_data[folder_id]["total_tokens"] += trace_tokens
            projects_data[folder_id]["total_cost"] += trace_cost
            if session_id:
                projects_data[folder_id]["sessions"].add(session_id)
            if timestamp:
                projects_data[folder_id]["timestamps"].append(timestamp)

        # Build response
        projects = []
        for pid, data in projects_data.items():
            timestamps = data["timestamps"]
            projects.append(ProjectListItem(
                project_id=pid,
                project_name=data["project_name"],
                agent_count=len(data["agents"]),
                trace_count=data["trace_count"],
                session_count=len(data["sessions"]),
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
                last_activity=max(timestamps) if timestamps else None,
            ))

        projects.sort(key=lambda p: p.last_activity or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        total_count = len(projects)
        projects = projects[:limit]

        return ProjectListResponse(projects=projects, total=total_count)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")


@router.get("/projects/{project_id}")
async def get_project_detail(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    tz_offset: Annotated[int | None, Query(description="Timezone offset in minutes from UTC")] = None,
) -> ProjectDetailResponse:
    """
    Get detailed project (folder) information including agents and metrics breakdown.
    """
    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse not configured.")

    try:
        user_id = str(current_user.id)

        # Get folder from database
        from uuid import UUID as PyUUID
        try:
            folder_uuid = PyUUID(project_id)
            folder_result = await session.exec(
                select(Folder).where(Folder.id == folder_uuid, Folder.user_id == current_user.id)
            )
            folder = folder_result.first()
        except ValueError:
            folder = None

        if not folder:
            raise HTTPException(status_code=404, detail="Project not found")

        project_name = folder.name

        # Get flows in this folder
        flows_result = await session.exec(
            select(Agent).where(
                Agent.user_id == current_user.id,
                Agent.folder_id == folder.id,
                Agent.is_component == False
            )
        )
        folder_flows = flows_result.all()

        flows_by_id = {str(f.id): f for f in folder_flows}
        flows_by_name = {f.name: f for f in folder_flows}

        if not folder_flows:
            return ProjectDetailResponse(
                project_id=project_id,
                project_name=project_name,
                agent_count=0,
                trace_count=0,
                session_count=0,
                observation_count=0,
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                total_cost=0.0,
                avg_latency_ms=None,
                first_activity=None,
                last_activity=None,
                models_used={},
                agents=[],
                by_date=[],
            )

        # Fetch all traces
        raw_traces = fetch_traces_from_langfuse(client, user_id, limit=100)

        # Aggregate metrics
        agents_data: dict[str, dict] = {}
        total_traces = 0
        total_observations = 0
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        latencies = []
        sessions = set()
        timestamps = []
        models_used: dict[str, dict] = {}
        daily_data: dict[str, dict] = defaultdict(lambda: {
            "trace_count": 0, "observation_count": 0, "total_tokens": 0, "total_cost": 0.0
        })

        for trace in raw_traces:
            matched_fid, matched_fname = _match_trace_to_flow(trace, flows_by_id, flows_by_name)
            if not matched_fid:
                continue

            total_traces += 1
            trace_id = get_attr(trace, 'id')
            session_id = get_attr(trace, 'session_id', 'sessionId')
            timestamp = parse_datetime(get_attr(trace, 'timestamp'))

            if session_id:
                sessions.add(session_id)
            if timestamp:
                timestamps.append(timestamp)

            # Fetch observations
            try:
                observations = fetch_observations_for_trace(client, str(trace_id))
                parsed_obs = [parse_observation(obs) for obs in observations]
            except:
                parsed_obs = []

            total_observations += len(parsed_obs)

            trace_tokens = 0
            trace_cost = 0.0

            for obs in parsed_obs:
                total_tokens += obs.total_tokens
                input_tokens += obs.input_tokens
                output_tokens += obs.output_tokens
                total_cost += obs.total_cost
                trace_tokens += obs.total_tokens
                trace_cost += obs.total_cost

                if obs.latency_ms:
                    latencies.append(obs.latency_ms)

                if obs.model:
                    if obs.model not in models_used:
                        models_used[obs.model] = {"tokens": 0, "cost": 0.0, "calls": 0}
                    models_used[obs.model]["tokens"] += obs.total_tokens
                    models_used[obs.model]["cost"] += obs.total_cost
                    models_used[obs.model]["calls"] += 1

            # Per-agent aggregation
            if matched_fid not in agents_data:
                agents_data[matched_fid] = {
                    "agent_id": matched_fid,
                    "flow_name": matched_fname,
                    "trace_count": 0,
                    "sessions": set(),
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "models": set(),
                    "latencies": [],
                    "timestamps": [],
                }

            agents_data[matched_fid]["trace_count"] += 1
            agents_data[matched_fid]["total_tokens"] += trace_tokens
            agents_data[matched_fid]["total_cost"] += trace_cost
            agents_data[matched_fid]["models"].update(o.model for o in parsed_obs if o.model)
            agents_data[matched_fid]["latencies"].extend(o.latency_ms for o in parsed_obs if o.latency_ms)
            if session_id:
                agents_data[matched_fid]["sessions"].add(session_id)
            if timestamp:
                agents_data[matched_fid]["timestamps"].append(timestamp)
                # Apply timezone offset if provided
                if tz_offset is not None:
                    local_ts = timestamp + timedelta(minutes=tz_offset)
                    date_str = local_ts.strftime('%Y-%m-%d')
                else:
                    date_str = timestamp.strftime('%Y-%m-%d')
                daily_data[date_str]["trace_count"] += 1
                daily_data[date_str]["observation_count"] += len(parsed_obs)
                daily_data[date_str]["total_tokens"] += trace_tokens
                daily_data[date_str]["total_cost"] += trace_cost

        # Build agents list
        agents = []
        for fid, data in agents_data.items():
            ts = data["timestamps"]
            lats = data["latencies"]
            avg_lat = sum(lats) / len(lats) if lats else None
            agents.append(AgentListItem(
                agent_id=fid,
                flow_name=data["flow_name"],
                trace_count=data["trace_count"],
                session_count=len(data["sessions"]),
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
                avg_latency_ms=avg_lat,
                models_used=list(data["models"]),
                last_activity=max(ts) if ts else None,
            ))
        agents.sort(key=lambda a: a.last_activity or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # Build daily usage
        by_date = []
        for date, data in sorted(daily_data.items()):
            by_date.append(DailyUsageItem(
                date=date,
                trace_count=data["trace_count"],
                observation_count=data["observation_count"],
                total_tokens=data["total_tokens"],
                total_cost=data["total_cost"],
            ))

        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return ProjectDetailResponse(
            project_id=project_id,
            project_name=project_name,
            agent_count=len(agents_data),
            trace_count=total_traces,
            session_count=len(sessions),
            observation_count=total_observations,
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            avg_latency_ms=avg_latency,
            first_activity=min(timestamps) if timestamps else None,
            last_activity=max(timestamps) if timestamps else None,
            models_used=models_used,
            agents=agents,
            by_date=by_date,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project detail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch project: {str(e)}")