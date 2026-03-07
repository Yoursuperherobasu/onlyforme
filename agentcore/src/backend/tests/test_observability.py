"""Comprehensive observability test suite for AgentCore.

Tests ALL observability features without external services
(no DB, Redis, Langfuse, OTLP collector).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

import agentcore.observability.metrics_registry as mr
import agentcore.observability.otel_metrics as otel_met
import agentcore.observability.otel_tracing as otel_tr

# ── Paths ────────────────────────────────────────────────────────────────
_AGENTCORE_ROOT = Path(__file__).parents[3]  # agentcore/
_DASHBOARD_DIR = _AGENTCORE_ROOT / "dashboards" / "grafana"

# ── Known metric names (for dashboard validation) ────────────────────────
KNOWN_METRICS = {
    "agentcore_agent_runs_total",
    "agentcore_agent_run_duration_ms",
    "agentcore_component_builds_total",
    "agentcore_component_build_duration_ms",
    "agentcore_llm_calls_total",
    "agentcore_llm_tokens_total",
    "agentcore_llm_call_duration_ms",
    "agentcore_errors_total",
    "agentcore_active_sessions",
    "agentcore_login_attempts_total",
    "agentcore_api_errors_total",
    "http_server_requests_total",
    "http_server_request_duration_ms",
}

# ── ENV VARS to clean between tests ─────────────────────────────────────
_OBS_ENV_VARS = [
    "AGENTCORE_METRICS_ENABLED",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "OTEL_FASTAPI_EXCLUDED_URLS",
    "OTEL_DB_INSTRUMENTATION_ENABLED",
    "OTEL_REDIS_INSTRUMENTATION_ENABLED",
    "OTEL_HTTPX_INSTRUMENTATION_ENABLED",
    "OTEL_RESOURCE_ATTRIBUTES",
    "DEPLOYMENT_ENVIRONMENT",
]


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Unset all observability env vars before each test."""
    for var in _OBS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _reset_metrics_registry():
    """Reset all 11 metrics_registry globals to None."""
    yield
    for attr in [
        "_agent_runs_counter",
        "_agent_run_duration",
        "_component_builds_counter",
        "_component_build_duration",
        "_llm_calls_counter",
        "_llm_tokens_counter",
        "_llm_call_duration",
        "_errors_counter",
        "_active_sessions",
        "_login_attempts_counter",
        "_api_errors_counter",
    ]:
        setattr(mr, attr, None)


@pytest.fixture(autouse=True)
def _reset_otel_metrics():
    """Reset otel_metrics globals + shutdown MeterProvider."""
    yield
    try:
        if otel_met._meter_provider is not None:
            otel_met._meter_provider.shutdown()
    except Exception:
        pass
    otel_met._metrics_initialized = False
    otel_met._request_counter = None
    otel_met._request_duration_histogram = None
    otel_met._meter_provider = None


@pytest.fixture(autouse=True)
def _reset_otel_tracing():
    """Reset otel_tracing globals + shutdown TracerProvider."""
    yield
    try:
        if otel_tr._tracer_provider is not None:
            otel_tr._tracer_provider.shutdown()
    except Exception:
        pass
    otel_tr._tracer_provider = None
    otel_tr._sqlalchemy_instrumented = False
    otel_tr._redis_instrumented = False
    otel_tr._httpx_instrumented = False


@pytest.fixture(autouse=True)
def _reset_prometheus_registry():
    """Unregister non-default collectors from prometheus_client REGISTRY."""
    yield
    try:
        from prometheus_client import REGISTRY

        default_names = {"platform_collector", "gc_collector", "process_collector"}
        to_remove = []
        for name, collector in list(REGISTRY._names_to_collectors.items()):
            if name not in default_names:
                to_remove.append(collector)
        for collector in set(to_remove):
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def _reset_otel_global_provider():
    """Reset the OTel global MeterProvider and TracerProvider singletons."""
    yield
    try:
        from opentelemetry import metrics
        from opentelemetry.metrics import _internal as metrics_internal
        from opentelemetry.sdk.metrics import MeterProvider

        existing = metrics.get_meter_provider()
        if isinstance(existing, MeterProvider):
            try:
                existing.shutdown()
            except Exception:
                pass
        # Reset the global singleton via internal module
        metrics_internal._METER_PROVIDER = None
        metrics_internal._METER_PROVIDER_SET_ONCE._done = False
        # Reset the proxy provider so get_meter_provider() returns fresh default
        metrics_internal._PROXY_METER_PROVIDER = (
            metrics_internal._ProxyMeterProvider()
        )
    except (ImportError, AttributeError):
        pass

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        existing = trace.get_tracer_provider()
        if isinstance(existing, TracerProvider):
            try:
                existing.shutdown()
            except Exception:
                pass
        trace._TRACER_PROVIDER = None
        trace._TRACER_PROVIDER_SET_ONCE._done = False
        trace._PROXY_TRACER_PROVIDER = trace.ProxyTracerProvider()
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def in_memory_meter():
    """Create a MeterProvider with InMemoryMetricReader for unit testing."""
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    meter = provider.get_meter("test.meter", "1.0.0")
    yield provider, reader, meter
    try:
        provider.shutdown()
    except Exception:
        pass


@pytest.fixture
def sample_app():
    """Minimal FastAPI app with test endpoints."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/test")
    async def test_endpoint():
        return {"result": "ok"}

    @app.get("/api/fail")
    async def fail_endpoint():
        return JSONResponse(status_code=500, content={"error": "boom"})

    @app.get("/api/notfound")
    async def notfound_endpoint():
        return JSONResponse(status_code=404, content={"error": "not found"})

    return app


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _get_metric_names(data) -> dict[str, Any]:
    """Extract metric name -> metric object from InMemoryMetricReader data."""
    result = {}
    if data is None:
        return result
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                result[metric.name] = metric
    return result


def _get_data_points(metric) -> list:
    """Get all data points from a metric regardless of type."""
    if hasattr(metric, "data") and hasattr(metric.data, "data_points"):
        return list(metric.data.data_points)
    return []


# ═══════════════════════════════════════════════════════════════════════════
# Category 1: metrics_registry.py Unit Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricsRegistry:
    """Unit tests for metrics_registry.py using InMemoryMetricReader."""

    def test_init_instruments_creates_all_11(self, in_memory_meter):
        _provider, _reader, meter = in_memory_meter
        mr.init_instruments(meter)
        for attr in [
            "_agent_runs_counter",
            "_agent_run_duration",
            "_component_builds_counter",
            "_component_build_duration",
            "_llm_calls_counter",
            "_llm_tokens_counter",
            "_llm_call_duration",
            "_errors_counter",
            "_active_sessions",
            "_login_attempts_counter",
            "_api_errors_counter",
        ]:
            assert getattr(mr, attr) is not None, f"{attr} should not be None after init"

    def test_init_instruments_idempotent(self, in_memory_meter):
        _provider, _reader, meter = in_memory_meter
        mr.init_instruments(meter)
        first_ref = mr._agent_runs_counter
        mr.init_instruments(meter)
        assert mr._agent_runs_counter is first_ref

    def test_record_agent_run_after_init(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_agent_run("test-agent", "success", 150.0)
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_agent_runs_total" in metrics
        assert "agentcore_agent_run_duration_ms" in metrics

    def test_record_component_build_after_init(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_component_build("LLMNode", "success", 200.0)
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_component_builds_total" in metrics
        assert "agentcore_component_build_duration_ms" in metrics

    def test_record_llm_call_with_tokens(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_llm_call("gpt-4", "openai", 500.0, input_tokens=100, output_tokens=50)
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_llm_calls_total" in metrics
        assert "agentcore_llm_call_duration_ms" in metrics
        assert "agentcore_llm_tokens_total" in metrics
        # Verify token data points have direction labels
        token_metric = metrics["agentcore_llm_tokens_total"]
        points = _get_data_points(token_metric)
        directions = {dict(pt.attributes).get("direction") for pt in points}
        assert "input" in directions
        assert "output" in directions

    def test_record_llm_call_zero_tokens_skips(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_llm_call("gpt-4", "openai", 500.0, input_tokens=0, output_tokens=0)
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_llm_calls_total" in metrics
        # Tokens counter should not appear since both are 0
        assert "agentcore_llm_tokens_total" not in metrics

    def test_record_error_after_init(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_error("ValueError", "api")
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_errors_total" in metrics

    def test_adjust_active_sessions_positive(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.adjust_active_sessions(1)
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_active_sessions" in metrics
        points = _get_data_points(metrics["agentcore_active_sessions"])
        assert any(pt.value == 1 for pt in points)

    def test_adjust_active_sessions_negative(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.adjust_active_sessions(1)
        mr.adjust_active_sessions(-1)
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_active_sessions" in metrics
        points = _get_data_points(metrics["agentcore_active_sessions"])
        assert any(pt.value == 0 for pt in points)

    def test_record_login_attempt_after_init(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_login_attempt("success")
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_login_attempts_total" in metrics

    def test_record_api_error_after_init(self, in_memory_meter):
        _provider, reader, meter = in_memory_meter
        mr.init_instruments(meter)
        mr.record_api_error("404", "/api/missing")
        data = reader.get_metrics_data()
        metrics = _get_metric_names(data)
        assert "agentcore_api_errors_total" in metrics

    # ── No-op safety tests (before init) ──

    def test_record_agent_run_noop_before_init(self):
        mr.record_agent_run("agent", "success", 100.0)  # should not raise

    def test_record_component_build_noop_before_init(self):
        mr.record_component_build("LLM", "success", 50.0)

    def test_record_llm_call_noop_before_init(self):
        mr.record_llm_call("gpt-4", "openai", 300.0, 10, 20)

    def test_record_error_noop_before_init(self):
        mr.record_error("RuntimeError", "worker")

    def test_adjust_active_sessions_noop_before_init(self):
        mr.adjust_active_sessions(1)

    def test_record_login_attempt_noop_before_init(self):
        mr.record_login_attempt("failure")

    def test_record_api_error_noop_before_init(self):
        mr.record_api_error("500", "/api/crash")


# ═══════════════════════════════════════════════════════════════════════════
# Category 2: otel_metrics.py Integration Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestOtelMetrics:
    """Integration tests for otel_metrics.py with sample FastAPI app."""

    def test_is_metrics_enabled_false_by_default(self):
        assert otel_met.is_metrics_enabled() is False

    def test_is_metrics_enabled_true(self, monkeypatch):
        monkeypatch.setenv("AGENTCORE_METRICS_ENABLED", "true")
        assert otel_met.is_metrics_enabled() is True

    def test_is_metrics_enabled_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AGENTCORE_METRICS_ENABLED", "True")
        assert otel_met.is_metrics_enabled() is True
        monkeypatch.setenv("AGENTCORE_METRICS_ENABLED", "TRUE")
        assert otel_met.is_metrics_enabled() is True

    def test_setup_creates_metrics_endpoint(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_endpoint_returns_prometheus_format(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        # Make a request first so there's something to report
        client.get("/api/test")
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")
        # Prometheus output should have metric lines after a request
        assert len(resp.text) > 0

    def test_middleware_records_request_counter(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        client.get("/api/test")
        resp = client.get("/metrics")
        body = resp.text
        # OTel Prometheus exporter may add _total suffix
        assert (
            "http_server_requests_total" in body
            or "http_server_requests_total_total" in body
        )

    def test_middleware_skips_metrics_endpoint(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        # Only hit /metrics (no other requests)
        resp = client.get("/metrics")
        body = resp.text
        # /metrics path should not appear as a recorded route
        assert 'route="/metrics"' not in body

    def test_middleware_records_api_error_on_4xx(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        client.get("/api/notfound")
        resp = client.get("/metrics")
        body = resp.text
        assert (
            "agentcore_api_errors_total" in body
            or "agentcore_api_errors_total_total" in body
        )

    def test_setup_is_idempotent(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        # Second call should not raise
        otel_met.setup_otel_metrics(sample_app)

    def test_shutdown_cleans_up(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        assert otel_met._meter_provider is not None
        otel_met.shutdown_otel_metrics()
        assert otel_met._meter_provider is None


# ═══════════════════════════════════════════════════════════════════════════
# Category 3: otel_tracing.py Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestOtelTracing:
    """Tests for otel_tracing.py."""

    def test_is_tracing_enabled_false_by_default(self):
        assert otel_tr.is_tracing_enabled() is False

    def test_is_tracing_enabled_with_endpoint(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        assert otel_tr.is_tracing_enabled() is True

    def test_is_tracing_enabled_with_service_name(self, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "my-service")
        assert otel_tr.is_tracing_enabled() is True

    def test_excluded_urls_default(self):
        result = otel_tr._get_fastapi_excluded_urls()
        assert result == "/health,/health_check,/metrics"

    def test_excluded_urls_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_FASTAPI_EXCLUDED_URLS", "/custom,/other")
        result = otel_tr._get_fastapi_excluded_urls()
        assert result == "/custom,/other"

    def test_trace_id_middleware_injects_header(self, sample_app, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")
        # Disable httpx instrumentation to avoid side effects
        monkeypatch.setenv("OTEL_HTTPX_INSTRUMENTATION_ENABLED", "false")
        otel_tr.setup_otel_tracing(sample_app)
        client = TestClient(sample_app)
        resp = client.get("/api/test")
        # X-Trace-Id should be present (non-zero trace from FastAPIInstrumentor)
        assert "x-trace-id" in resp.headers

    def test_shutdown_cleans_up(self, sample_app, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")
        monkeypatch.setenv("OTEL_HTTPX_INSTRUMENTATION_ENABLED", "false")
        otel_tr.setup_otel_tracing(sample_app)
        assert otel_tr._tracer_provider is not None
        otel_tr.shutdown_otel_tracing()
        assert otel_tr._tracer_provider is None


# ═══════════════════════════════════════════════════════════════════════════
# Category 4: Grafana Dashboard Validation
# ═══════════════════════════════════════════════════════════════════════════

_DASHBOARD_FILES = [
    "executive-summary.json",
    "performance.json",
    "reliability.json",
    "usage-analytics.json",
]

_METRIC_PATTERN = re.compile(r"\b(agentcore_\w+|http_server_\w+)")
_HISTOGRAM_SUFFIXES = ("_bucket", "_count", "_sum")


def _strip_histogram_suffix(name: str) -> str:
    for suffix in _HISTOGRAM_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _load_dashboard(filename: str) -> dict:
    path = _DASHBOARD_DIR / filename
    with open(path) as f:
        return json.load(f)


@pytest.mark.parametrize("dashboard_file", _DASHBOARD_FILES)
class TestGrafanaDashboards:
    """Validate Grafana dashboard JSON files."""

    def test_valid_json(self, dashboard_file):
        data = _load_dashboard(dashboard_file)
        assert isinstance(data, dict)

    def test_has_datasource_variable(self, dashboard_file):
        data = _load_dashboard(dashboard_file)
        templating = data.get("templating", {})
        var_list = templating.get("list", [])
        ds_vars = [v for v in var_list if v.get("type") == "datasource"]
        assert len(ds_vars) > 0, "Dashboard should have a datasource template variable"
        names = [v.get("name") for v in ds_vars]
        assert "datasource" in names

    def test_has_required_fields(self, dashboard_file):
        data = _load_dashboard(dashboard_file)
        for field in ("title", "uid", "panels", "schemaVersion"):
            assert field in data, f"Dashboard missing required field: {field}"

    def test_panel_queries_reference_known_metrics(self, dashboard_file):
        data = _load_dashboard(dashboard_file)
        panels = data.get("panels", [])
        unknown = set()
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                found = _METRIC_PATTERN.findall(expr)
                for m in found:
                    base = _strip_histogram_suffix(m)
                    if base not in KNOWN_METRICS:
                        unknown.add(base)
        assert not unknown, f"Unknown metrics in {dashboard_file}: {unknown}"

    def test_panels_have_titles(self, dashboard_file):
        data = _load_dashboard(dashboard_file)
        panels = data.get("panels", [])
        for i, panel in enumerate(panels):
            # Row panels may not have titles
            if panel.get("type") == "row":
                continue
            title = panel.get("title", "")
            assert title, f"Panel {i} in {dashboard_file} has no title"

    def test_panels_have_datasource(self, dashboard_file):
        data = _load_dashboard(dashboard_file)
        panels = data.get("panels", [])
        for i, panel in enumerate(panels):
            if panel.get("type") == "row":
                continue
            ds = panel.get("datasource", {})
            uid = ds.get("uid", "") if isinstance(ds, dict) else ""
            assert "$datasource" in uid, (
                f"Panel {i} ({panel.get('title', '?')}) in {dashboard_file} "
                f"does not reference $datasource"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Category 5: Instrumentation Call-Site Verification
# ═══════════════════════════════════════════════════════════════════════════


class TestInstrumentationCallSites:
    """Verify that instrumentation calls exist in the source code."""

    def _read_source(self, rel_path: str) -> str:
        path = _AGENTCORE_ROOT / rel_path
        return path.read_text()

    def test_build_py_has_record_agent_run_success(self):
        source = self._read_source(
            "src/backend/base/agentcore/api/build.py"
        )
        assert 'record_agent_run(' in source
        assert '"success"' in source

    def test_build_py_has_record_agent_run_error(self):
        source = self._read_source(
            "src/backend/base/agentcore/api/build.py"
        )
        assert 'record_agent_run(' in source
        assert '"error"' in source

    def test_node_py_has_record_component_build_success(self):
        source = self._read_source(
            "src/backend/base/agentcore/custom/custom_node/node.py"
        )
        assert 'record_component_build(' in source
        assert '"success"' in source

    def test_node_py_has_record_component_build_error(self):
        source = self._read_source(
            "src/backend/base/agentcore/custom/custom_node/node.py"
        )
        assert 'record_component_build(' in source
        assert '"error"' in source

    def test_main_py_has_record_error(self):
        source = self._read_source(
            "src/backend/base/agentcore/main.py"
        )
        assert "record_error(" in source
        assert "type(exc).__name__" in source

    def test_login_py_has_record_login_success(self):
        source = self._read_source(
            "src/backend/base/agentcore/api/login.py"
        )
        assert 'record_login_attempt("success")' in source

    def test_login_py_has_record_login_failure(self):
        source = self._read_source(
            "src/backend/base/agentcore/api/login.py"
        )
        assert 'record_login_attempt("failure")' in source

    def test_model_py_has_record_llm_call(self):
        source = self._read_source(
            "src/backend/base/agentcore/base/models/model.py"
        )
        assert "record_llm_call(" in source

    def test_build_py_has_adjust_active_sessions(self):
        source = self._read_source(
            "src/backend/base/agentcore/api/build.py"
        )
        assert "adjust_active_sessions(" in source


# ═══════════════════════════════════════════════════════════════════════════
# Category 6: End-to-End Metrics Pipeline
# ═══════════════════════════════════════════════════════════════════════════


class TestE2EPipeline:
    """Full pipeline: FastAPI -> setup_otel_metrics -> requests -> /metrics."""

    def test_full_pipeline_http_counter(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        client.get("/api/test")
        resp = client.get("/metrics")
        body = resp.text
        assert (
            "http_server_requests_total" in body
            or "http_server_requests_total_total" in body
        )

    def test_full_pipeline_business_metrics_appear(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        # Trigger a business metric
        mr.record_agent_run("e2e-agent", "success", 250.0)
        resp = client.get("/metrics")
        body = resp.text
        assert (
            "agentcore_agent_runs_total" in body
            or "agentcore_agent_runs_total_total" in body
        )

    def test_full_pipeline_4xx_increments_api_errors(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        client.get("/api/notfound")
        resp = client.get("/metrics")
        body = resp.text
        assert (
            "agentcore_api_errors_total" in body
            or "agentcore_api_errors_total_total" in body
        )

    def test_full_pipeline_multiple_requests_accumulate(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        for _ in range(5):
            client.get("/api/test")
        resp = client.get("/metrics")
        body = resp.text
        # Find the counter value — should be >= 5
        # Look for lines like: http_server_requests_total_total{...} 5.0
        pattern = re.compile(
            r'http_server_requests_total(?:_total)?\{[^}]*\}\s+(\d+(?:\.\d+)?)'
        )
        matches = pattern.findall(body)
        assert matches, "Should find http_server_requests_total counter in output"
        total = sum(float(v) for v in matches)
        assert total >= 5.0, f"Expected accumulated count >= 5, got {total}"

    def test_full_pipeline_histogram_has_buckets(self, sample_app):
        otel_met.setup_otel_metrics(sample_app)
        client = TestClient(sample_app)
        client.get("/api/test")
        resp = client.get("/metrics")
        body = resp.text
        # Histograms produce _bucket, _count, _sum lines
        assert "http_server_request_duration_ms" in body
        has_bucket = "_bucket{" in body
        has_count = "_count{" in body or "_count " in body
        has_sum = "_sum{" in body or "_sum " in body
        assert has_bucket, "Histogram should produce _bucket lines"
        assert has_count, "Histogram should produce _count lines"
        assert has_sum, "Histogram should produce _sum lines"
