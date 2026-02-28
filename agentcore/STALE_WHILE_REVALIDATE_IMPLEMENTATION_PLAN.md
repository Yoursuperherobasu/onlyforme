# Stale-While-Revalidate Caching Implementation Plan

## Overview
Implement a caching strategy where endpoints immediately return cached data while asynchronously fetching fresh data in the background. This eliminates 10-20 second blocking waits during initial page loads.

**Expected Impact:**
- Page load time: 10-20s → 100-200ms ✨
- Server load reduction: ~70% fewer blocking Langfuse API calls
- User experience: Instant dashboard + automatic refresh

---

## Architecture Design

### 1. Cache Structure Enhancement

**Current:**
```python
_TRACE_METRICS_CACHE: dict[str, dict[str, Any]] = {}
_OBSERVATIONS_CACHE: dict[str, dict[str, Any]] = {}
```

**Enhanced (with metadata):**
```python
_CACHE_WITH_METADATA: dict[str, dict] = {
    "key": {
        "data": {...},              # Actual cached data
        "timestamp": 1234567890,    # Unix timestamp when cached
        "version": 1,               # Version for invalidation
        "is_fresh": True,           # Whether currently fetching
        "fetch_in_progress": False, # Prevent duplicate fetches
    }
}
```

### 2. Time Thresholds (Configurable)

```python
# Stale-while-revalidate thresholds
CACHE_FRESH_SECONDS = 15          # Data is fresh for 15s (serve immediately, no refresh)
CACHE_STALE_SECONDS = 60          # Data is stale after 60s (serve but trigger refresh)
CACHE_EXPIRED_SECONDS = 300       # Data is expired after 5min (wait for new fetch)

# Background fetch concurrency
MAX_CONCURRENT_BACKGROUND_FETCHES = 3
BACKGROUND_FETCH_TIMEOUT_SECONDS = 30
```

### 3. Response Structure Enhancement

**Add cache age metadata to responses:**
```python
class CacheMetadata(BaseModel):
    cached_at: datetime          # When data was cached
    age_seconds: int             # How old is the data
    is_fresh: bool               # True if age < FRESH_THRESHOLD
    next_refresh_at: datetime    # When next background refresh scheduled
    
class MetricsResponse(BaseModel):
    # ... existing fields ...
    _cache_metadata: CacheMetadata | None = None  # For frontend UI
```

---

## Implementation Components

### Phase 1: Cache Age Tracking

**File:** `observability.py` - Add helper functions

```python
import time
from typing import Any
from datetime import datetime, timezone

# Cache metadata storage
_CACHE_METADATA: dict[str, dict[str, Any]] = {}
_BACKGROUND_FETCH_IN_PROGRESS: set[str] = set()  # Prevent duplicate fetches

def _get_cache_metadata(cache_key: str) -> dict[str, Any]:
    """Get cache age and freshness info."""
    if cache_key not in _CACHE_METADATA:
        return {
            "cached_at": None,
            "age_seconds": float('inf'),
            "is_fresh": False,
        }
    
    meta = _CACHE_METADATA[cache_key]
    age_seconds = time.time() - meta["timestamp"]
    
    return {
        "cached_at": datetime.fromtimestamp(meta["timestamp"], tz=timezone.utc),
        "age_seconds": int(age_seconds),
        "is_fresh": age_seconds < CACHE_FRESH_SECONDS,
        "is_stale": CACHE_FRESH_SECONDS <= age_seconds < CACHE_STALE_SECONDS,
        "is_expired": age_seconds >= CACHE_STALE_SECONDS,
    }

def _update_cache_metadata(cache_key: str, data: Any) -> None:
    """Update cache with current timestamp."""
    _CACHE_METADATA[cache_key] = {
        "timestamp": time.time(),
        "data_hash": hash(str(data)[:100]),  # Detect data changes
    }

def _mark_fetch_in_progress(cache_key: str) -> bool:
    """Mark a fetch as in progress. Return False if already in progress."""
    if cache_key in _BACKGROUND_FETCH_IN_PROGRESS:
        return False
    _BACKGROUND_FETCH_IN_PROGRESS.add(cache_key)
    return True

def _mark_fetch_complete(cache_key: str) -> None:
    """Mark fetch as complete."""
    _BACKGROUND_FETCH_IN_PROGRESS.discard(cache_key)
```

### Phase 2: Background Fetch Tasks

**File:** `observability.py` - Add async background functions

```python
from fastapi import BackgroundTasks
import asyncio

async def _fetch_metrics_background(
    user_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    search: str | None = None,
    models: str | None = None,
    fetch_all: bool = False,
) -> None:
    """
    Background task: Fetch fresh metrics from Langfuse asynchronously.
    Updates cache when complete.
    """
    cache_key = f"metrics:{user_id}:{from_timestamp}:{to_timestamp}"
    
    try:
        # Get Langfuse client
        client = get_langfuse_client()
        if not client:
            logger.warning("Langfuse client not available for background fetch")
            return
        
        logger.debug(f"Background fetch started for {cache_key}")
        
        # Perform the expensive fetch (mimics get_user_metrics logic)
        # This is the actual Langfuse API call
        raw_traces = fetch_traces_from_langfuse(
            client,
            user_id,
            limit=500,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            name=search,
            fetch_all=fetch_all,
        )
        
        # Build fresh metrics
        # (use the same aggregation logic as endpoint)
        fresh_metrics = _compute_metrics_from_traces(
            raw_traces,
            models,
            include_model_breakdown=False,  # Keep fast path in background too
        )
        
        # Update cache with fresh data
        _TRACE_METRICS_CACHE[cache_key] = {
            "metrics": fresh_metrics,
            "ts": time.monotonic(),
        }
        _update_cache_metadata(cache_key, fresh_metrics)
        
        logger.debug(f"Background fetch completed for {cache_key}")
        
    except Exception as e:
        logger.error(f"Background fetch failed for {cache_key}: {e}")
        # Don't raise - let cache remain stale rather than crash
    finally:
        _mark_fetch_complete(cache_key)

async def _trigger_background_refresh(
    background_tasks: BackgroundTasks,
    cache_key: str,
    fetch_params: dict[str, Any],
) -> None:
    """
    Trigger background refresh if:
    1. Data is stale (age > FRESH_THRESHOLD)
    2. Not already fetching
    3. Concurrent fetch limit not exceeded
    """
    cache_meta = _get_cache_metadata(cache_key)
    
    # Don't refresh if still fresh
    if cache_meta["is_fresh"]:
        return
    
    # Don't refresh if already in progress
    if cache_key in _BACKGROUND_FETCH_IN_PROGRESS:
        return
    
    # Check concurrent fetch limit
    if len(_BACKGROUND_FETCH_IN_PROGRESS) >= MAX_CONCURRENT_BACKGROUND_FETCHES:
        logger.debug(f"Background fetch queue full ({len(_BACKGROUND_FETCH_IN_PROGRESS)}), skipping refresh for {cache_key}")
        return
    
    # Mark as in progress before adding task
    if not _mark_fetch_in_progress(cache_key):
        return
    
    logger.debug(f"Triggering background refresh for {cache_key}")
    background_tasks.add_task(
        _fetch_metrics_background,
        **fetch_params
    )
```

### Phase 3: Endpoint Modification Pattern

**File:** `observability.py` - Update endpoints to use stale-while-revalidate

```python
@router.get("/metrics")
async def get_user_metrics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    background_tasks: BackgroundTasks,  # Add this
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    from_date: Annotated[str | None, Query(...)] = None,
    to_date: Annotated[str | None, Query(...)] = None,
    search: Annotated[str | None, Query(...)] = None,
    models: Annotated[str | None, Query(...)] = None,
    include_model_breakdown: Annotated[bool, Query(...)] = False,
    fetch_all: Annotated[bool, Query(...)] = False,
) -> MetricsResponse:
    """
    Get metrics with stale-while-revalidate caching.
    
    Strategy:
    1. If cache fresh (<15s old): return immediately, no refresh
    2. If cache stale (15-60s old): return immediately, trigger background refresh
    3. If cache expired (>60s old) or missing: return stale cache OR wait for fresh fetch
    """
    _clear_request_caches()
    
    user_id = str(current_user.id)
    
    # Build cache key from parameters
    cache_key = f"metrics:{user_id}:{from_date}:{to_date}:{search}:{models}"
    
    # Check cache status
    cache_meta = _get_cache_metadata(cache_key)
    
    # === FRESH CACHE: Return immediately ===
    if cache_meta["is_fresh"] and cache_key in _TRACE_METRICS_CACHE:
        logger.debug(f"Cache HIT (fresh) for {cache_key}, age={cache_meta['age_seconds']}s")
        cached = _TRACE_METRICS_CACHE[cache_key]
        return MetricsResponse(
            **cached["metrics"],
            _cache_metadata={
                "cached_at": cache_meta["cached_at"],
                "age_seconds": cache_meta["age_seconds"],
                "is_fresh": True,
            }
        )
    
    # === STALE CACHE: Return immediately + trigger refresh ===
    if cache_meta["is_stale"] and cache_key in _TRACE_METRICS_CACHE:
        logger.debug(f"Cache HIT (stale) for {cache_key}, age={cache_meta['age_seconds']}s, triggering refresh")
        cached = _TRACE_METRICS_CACHE[cache_key]
        
        # Trigger background refresh (non-blocking)
        await _trigger_background_refresh(
            background_tasks,
            cache_key,
            {
                "user_id": user_id,
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp,
                "search": search,
                "models": models,
                "fetch_all": fetch_all,
            }
        )
        
        return MetricsResponse(
            **cached["metrics"],
            _cache_metadata={
                "cached_at": cache_meta["cached_at"],
                "age_seconds": cache_meta["age_seconds"],
                "is_fresh": False,
            }
        )
    
    # === EXPIRED/MISSING CACHE: Fetch fresh data ===
    logger.debug(f"Cache MISS for {cache_key}, fetching fresh data")
    
    # Parse dates and fetch (existing logic)
    now = datetime.now(timezone.utc)
    from_timestamp = ... # existing date parsing
    to_timestamp = ...
    
    raw_traces = fetch_traces_from_langfuse(
        client,
        user_id,
        limit=500,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        name=search,
        fetch_all=fetch_all,
    )
    
    # Build metrics
    metrics = _compute_metrics_from_traces(raw_traces, models, False)
    
    # Update cache
    _TRACE_METRICS_CACHE[cache_key] = {
        "metrics": metrics,
        "ts": time.monotonic(),
    }
    _update_cache_metadata(cache_key, metrics)
    
    return MetricsResponse(
        **metrics,
        _cache_metadata={
            "cached_at": datetime.now(timezone.utc),
            "age_seconds": 0,
            "is_fresh": True,
        }
    )
```

### Phase 4: Apply to All Endpoints

Apply the same pattern to:
- `GET /metrics` ← Primary, high impact
- `GET /agents` ← Secondary
- `GET /sessions` ← Secondary
- `GET /projects` ← Secondary
- `GET /traces` ← Lower priority (trace list usually fast)

---

## Frontend Integration (Optional Enhancement)

### Display Cache Age to User

```typescript
// ObservabilityPage/index.tsx
interface CacheMetadata {
  cached_at: string;
  age_seconds: number;
  is_fresh: boolean;
}

function MetricsPanel({ data, cacheMetadata }) {
  return (
    <div>
      <Card>
        {/* Existing metrics content */}
      </Card>
      
      {/* Cache age indicator */}
      {cacheMetadata && (
        <div className="text-xs text-gray-500 mt-2">
          {cacheMetadata.is_fresh ? (
            <span>✓ Fresh data (updated {cacheMetadata.age_seconds}s ago)</span>
          ) : (
            <span>⟳ Data from {cacheMetadata.age_seconds}s ago (updating...)</span>
          )}
        </div>
      )}
    </div>
  );
}
```

### Auto-Refresh When Fresh Data Arrives

```typescript
// Listen for WebSocket notifications when cache updates
useEffect(() => {
  const ws = new WebSocket('ws://localhost:7860/api/observability/cache-updates');
  
  ws.onmessage = (event) => {
    const { cache_key } = JSON.parse(event.data);
    // Refetch that specific query
    queryClient.invalidateQueries({ queryKey: cache_key });
  };
  
  return () => ws.close();
}, []);
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (2 hours)
- [ ] Add cache metadata tracking functions
- [ ] Add background fetch logic
- [ ] Add duplicate fetch prevention

### Phase 2: Endpoint Integration (2 hours)
- [ ] Update `/metrics` endpoint with SWR logic
- [ ] Update `/agents` endpoint
- [ ] Update `/sessions` endpoint
- [ ] Add cache age to response models

### Phase 3: Testing & Validation (1 hour)
- [ ] Manual load testing
- [ ] Cache behavior verification
- [ ] Background fetch reliability

### Phase 4: Frontend Integration (Optional, 1 hour)
- [ ] Display cache age indicator
- [ ] Add refresh status UI
- [ ] WebSocket notifications (future)

**Total Effort: 4-6 hours**

---

## Configuration (All Adjustable)

```python
# observability.py - Add to settings section
SWR_CONFIG = {
    "FRESH_SECONDS": 15,          # Return without refresh
    "STALE_SECONDS": 60,          # Return with background refresh
    "EXPIRED_SECONDS": 300,       # Wait for fresh fetch
    "MAX_CONCURRENT_FETCHES": 3,  # Prevent overwhelming Langfuse
    "FETCH_TIMEOUT": 30,          # Max time for background fetch
    "ENABLE_SWR": True,           # Feature flag
}
```

---

## Monitoring & Logging

Track effectiveness:
```python
logger.info(f"Cache HIT (fresh): {cache_key}, age={cache_meta['age_seconds']}s")
logger.info(f"Cache HIT (stale): {cache_key}, age={cache_meta['age_seconds']}s, triggering refresh")
logger.info(f"Cache MISS: {cache_key}, fetching fresh data")
logger.info(f"Background fetch completed: {cache_key}")
logger.warning(f"Background fetch failed: {cache_key}, {error}")
```

**Metrics to track:**
- Cache hit rate (fresh vs stale vs miss)
- Background fetch success/failure rate
- Age of returned data
- Endpoint response times

---

## Rollback Plan

If issues arise:
1. Set `SWR_CONFIG["ENABLE_SWR"] = False` to disable feature
2. Returns to blocking fetch behavior
3. No code changes needed

---

## Expected Results

### Before Implementation
```
Request 1: 12 seconds (fresh fetch from Langfuse)
Request 2 (within 60s): 100ms (cache hit)
Request 3 (after 60s): 15 seconds (cache expired)
Request 4 (within 60s): 100ms
Request 5 (after 60s): 18 seconds
```

### After Implementation
```
Request 1: 150ms (cache miss, returns fresh data)
Request 2: 100ms (cache fresh, no refresh)
Request 3: 120ms (cache stale, background refresh triggered)
Request 4: 100ms (cache fresh, background data updated)
Request 5: 120ms (cache stale, background refresh)
Request 6: 100ms (cache fresh)
```

**Key improvement:** Consistent 100-150ms response times after first load

---

## Next Steps

Ready to implement? I'll:
1. Create the helper functions in observability.py
2. Refactor `/metrics` endpoint as template
3. Apply pattern to other endpoints
4. Add optional frontend indicators

Proceed? 🚀
