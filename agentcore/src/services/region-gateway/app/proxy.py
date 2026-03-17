from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from app.auth import spoke_auth
from app.config import RegionEntry, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker (per region)
# ---------------------------------------------------------------------------

@dataclass
class _CircuitState:
    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False

    # Config
    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning("Circuit breaker OPEN (failures=%d)", self.failure_count)

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def should_allow(self) -> bool:
        if not self.is_open:
            return True
        # Allow one probe after recovery timeout
        if time.time() - self.last_failure_time > self.recovery_timeout:
            return True
        return False


# ---------------------------------------------------------------------------
# Region Proxy
# ---------------------------------------------------------------------------

@dataclass
class RegionProxy:
    """Proxies dashboard API calls from hub to spoke backends."""

    _clients: dict[str, httpx.AsyncClient] = field(default_factory=dict)
    _circuits: dict[str, _CircuitState] = field(default_factory=dict)

    def _get_client(self, region: RegionEntry) -> httpx.AsyncClient:
        """Get or create an httpx client for a region (connection reuse)."""
        if region.code not in self._clients:
            settings = get_settings()
            self._clients[region.code] = httpx.AsyncClient(
                base_url=region.api_url,
                timeout=httpx.Timeout(settings.proxy_timeout, connect=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                follow_redirects=True,
            )
        return self._clients[region.code]

    def _get_circuit(self, region_code: str) -> _CircuitState:
        if region_code not in self._circuits:
            self._circuits[region_code] = _CircuitState()
        return self._circuits[region_code]

    async def proxy_dashboard(
        self,
        region: RegionEntry,
        path: str,
        query_params: dict | None = None,
        caller_user_id: str | None = None,
    ) -> dict:
        """Forward a dashboard request to a spoke backend.

        Args:
            region: Target region entry from config.
            path: The dashboard API path e.g. "/api/dashboard/sections/root-maturity"
            query_params: Query string parameters to forward.
            caller_user_id: Root admin user ID for audit trail on spoke side.

        Returns:
            The JSON response body from the spoke.

        Raises:
            httpx.HTTPStatusError: If the spoke returns a non-2xx response.
            RuntimeError: If circuit breaker is open.
        """
        circuit = self._get_circuit(region.code)

        if not circuit.should_allow():
            raise RuntimeError(
                f"Circuit breaker open for region '{region.code}'. "
                f"Last failure {time.time() - circuit.last_failure_time:.0f}s ago."
            )

        client = self._get_client(region)

        # Build headers
        headers: dict[str, str] = {}
        token = await spoke_auth.get_token(region)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if caller_user_id:
            headers["X-Hub-Caller"] = caller_user_id
        headers["X-Hub-Request-Id"] = str(time.time_ns())

        # Forward request with retry (max 1 retry on 502/503/504)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                start = time.monotonic()
                response = await client.get(
                    path,
                    params=query_params or {},
                    headers=headers,
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)

                response.raise_for_status()
                circuit.record_success()

                data = response.json()
                data["_region_proxy"] = {
                    "region_code": region.code,
                    "latency_ms": elapsed_ms,
                    "source": "remote",
                }
                return data

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (502, 503, 504) and attempt == 0:
                    logger.warning(
                        "Spoke '%s' returned %d, retrying (attempt %d)",
                        region.code, e.response.status_code, attempt + 1,
                    )
                    continue
                circuit.record_failure()
                raise

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_error = e
                if attempt == 0:
                    logger.warning(
                        "Spoke '%s' connection error: %s, retrying", region.code, e,
                    )
                    continue
                circuit.record_failure()
                raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected proxy state")

    async def check_health(self, region: RegionEntry) -> dict:
        """Check if a spoke backend is reachable."""
        settings = get_settings()
        client = self._get_client(region)

        headers: dict[str, str] = {}
        token = await spoke_auth.get_token(region)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            start = time.monotonic()
            response = await client.get(
                "/health",
                headers=headers,
                timeout=settings.health_check_timeout,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "healthy" if response.status_code == 200 else "degraded",
                "status_code": response.status_code,
                "latency_ms": elapsed_ms,
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "error": str(e),
                "latency_ms": -1,
            }

    async def close(self) -> None:
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()


# Singleton
region_proxy = RegionProxy()
