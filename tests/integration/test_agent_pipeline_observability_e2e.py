"""
End-to-end integration test: agent pipeline telemetry verification.

Runs a pipeline that executes agents using AgentTelemetry and LLMTelemetry,
exports the resulting spans via OTLP HTTP to the OpenTelemetry Collector, and
then verifies the data appears in Jaeger (traces) and the OTel Collector's
own metrics endpoint.

Requires the Docker observability stack from tests/docker-compose.test.yml:

    docker-compose -f tests/docker-compose.test.yml up -d
    # wait for services to be healthy, then:
    pytest tests/integration/test_agent_pipeline_observability_e2e.py -v -m observability

Port mapping (from docker-compose.test.yml):
    OTel Collector OTLP HTTP  localhost:14318  -> container:4318
    OTel Collector health     localhost:23133  -> container:13133
    OTel Collector metrics    localhost:18889  -> container:8889
    Jaeger UI / API           localhost:16686  -> container:16686
    Prometheus                localhost:19090  -> container:9090

Environment overrides:
    OTEL_COLLECTOR_ENDPOINT   (default: http://localhost:14318)
    JAEGER_URL                (default: http://localhost:16686)
    PROMETHEUS_URL            (default: http://localhost:19090)
"""

import os
import logging
from typing import Any, Dict, Optional

import pytest

requests = pytest.importorskip("requests")
pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")


def _reachable(url: str) -> bool:
    try:
        requests.get(url, timeout=2)
        return True
    except requests.RequestException:
        return False


# Needs the live OTel collector, Jaeger and Prometheus from tests/docker-compose
pytestmark = pytest.mark.skipif(
    not _reachable(os.environ.get("JAEGER_URL", "http://localhost:16686")),
    reason="observability stack not running (JAEGER_URL unreachable)",
)

from opentelemetry import context as otel_context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import set_span_in_context, StatusCode

from ia_modules.agents.core import BaseAgent, AgentRole
from ia_modules.agents.state import StateManager
from ia_modules.telemetry.metrics import MetricsCollector
from ia_modules.telemetry.tracing import Tracer, Span
from ia_modules.telemetry.agent_telemetry import AgentTelemetry
from ia_modules.telemetry.llm_telemetry import LLMTelemetry
from tests.integration import jaeger_query

logger = logging.getLogger(__name__)



# ── Service endpoints ──────────────────────────────────────────────────────────

OTEL_ENDPOINT  = os.environ.get("OTEL_COLLECTOR_ENDPOINT", "http://localhost:14318")
JAEGER_URL     = os.environ.get("JAEGER_URL",              "http://localhost:16686")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL",          "http://localhost:19090")

# Derived URLs — support both docker-compose (mapped ports) and CI (host network)
OTEL_HEALTH_URL   = os.environ.get("OTEL_HEALTH_URL", OTEL_ENDPOINT.replace(":14318", ":23133").replace(":4318", ":13133"))
OTEL_METRICS_URL  = os.environ.get("OTEL_METRICS_URL", OTEL_ENDPOINT.replace(":14318", ":18889").replace(":4318", ":8889") + "/metrics")

# Service name used in all spans – unique enough to filter Jaeger results
SERVICE_NAME = "ia_modules_e2e_test"


# ── OTel Bridge ───────────────────────────────────────────────────────────────

class _OtelBridgedSpan(Span):
    """
    Our Span subclass whose attribute / status mutations are mirrored in real
    time to the underlying OTel SDK span so that all data is exported via OTLP.
    """

    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str],
        attributes: Optional[Dict[str, Any]],
        otel_span: Any,
    ):
        super().__init__(name, trace_id, span_id, parent_span_id, attributes)
        self._otel_span = otel_span
        # Seed the OTel span with any attributes present at construction time
        for k, v in (attributes or {}).items():
            self._safe_set(k, v)

    def _safe_set(self, key: str, value: Any) -> None:
        try:
            self._otel_span.set_attribute(key, value)
        except Exception:
            pass

    def set_attribute(self, key: str, value: Any) -> None:
        super().set_attribute(key, value)
        self._safe_set(key, value)

    def set_status(self, status: str, description: Optional[str] = None) -> None:
        super().set_status(status, description)
        try:
            if status == "error":
                self._otel_span.set_status(StatusCode.ERROR, description or "")
            elif status == "ok":
                self._otel_span.set_status(StatusCode.OK)
        except Exception:
            pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        super().add_event(name, attributes)
        try:
            self._otel_span.add_event(name, attributes or {})
        except Exception:
            pass


class OtelBridgeTracer(Tracer):
    """
    Implements the ia_modules Tracer ABC but creates real OTel SDK spans under
    the hood.  Each span is represented both as an _OtelBridgedSpan (for
    in-process assertions) and as a live OTel span (for OTLP export to Jaeger).
    """

    def __init__(self, otel_sdk_tracer: Any):
        self._sdk = otel_sdk_tracer
        self._spans: list = []
        self._otel_spans: Dict[str, Any] = {}
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:016x}"

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Span] = None,
    ) -> _OtelBridgedSpan:
        # Propagate parent context into OTel if we have one
        ctx = otel_context.get_current()
        if parent and isinstance(parent, _OtelBridgedSpan):
            ctx = set_span_in_context(parent._otel_span, ctx)

        otel_span = self._sdk.start_span(name, context=ctx)

        trace_id   = self._next_id("trace")
        span_id    = self._next_id("span")
        parent_id  = parent.span_id if parent else None

        bridge = _OtelBridgedSpan(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            attributes=dict(attributes or {}),
            otel_span=otel_span,
        )
        self._otel_spans[span_id] = otel_span
        return bridge

    def end_span(self, span: Span) -> None:
        span.finish()
        self._spans.append(span)
        otel_span = self._otel_spans.pop(span.span_id, None)
        if otel_span:
            otel_span.end()

    def get_spans(self, trace_id: Optional[str] = None) -> list:
        if trace_id:
            return [s for s in self._spans if s.trace_id == trace_id]
        return list(self._spans)


# ── Simple test agents ────────────────────────────────────────────────────────

class SummaryAgent(BaseAgent):
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        topic = input_data.get("topic", "unknown")
        self.increment_iteration()
        await self.write_state("summary", f"Summary of: {topic}")
        return {"summary": f"Summary of: {topic}", "status": "success"}


class ReviewAgent(BaseAgent):
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        summary = await self.read_state("summary", default="")
        self.increment_iteration()
        await self.write_state("review", f"Approved: {summary}")
        return {"review": "approved", "status": "success"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _query_jaeger_traces(service: str, operation: str, limit: int = 20) -> list:
    return jaeger_query.find_traces(JAEGER_URL, service, operation, limit=limit)


def _wait_for_jaeger_service(service: str, timeout: int = 15) -> list:
    """Poll Jaeger until the service appears (OTel batch + Jaeger indexing delay)."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        services = jaeger_query.services(JAEGER_URL)
        if service in services:
            return services
        time.sleep(1)
    # Final attempt for assertion message
    return jaeger_query.services(JAEGER_URL)


def _wait_for_jaeger_traces(service: str, operation: str, timeout: int = 15) -> list:
    """Poll Jaeger until traces appear for the given operation."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        traces = _query_jaeger_traces(service, operation)
        if traces:
            return traces
        time.sleep(1)
    return []


# ── OTel provider (module-scoped so all tests share one exporter) ─────────────

@pytest.fixture(scope="module")
def otel_provider():
    """TracerProvider wired to the test OTel Collector via OTLP HTTP."""
    resource = Resource.create({
        "service.name": SERVICE_NAME,
        "deployment.environment": "e2e_test",
    })
    exporter = OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces")
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    yield provider

    provider.force_flush(timeout_millis=10_000)
    provider.shutdown()


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.observability
@pytest.mark.integration
class TestAgentPipelineObservabilityE2E:
    """
    E2E: execute agent pipelines, ship spans via OTLP to the Docker OTel
    Collector, and assert the data is queryable in Jaeger.
    """

    # ── pre-flight ─────────────────────────────────────────────────────────

    def test_docker_stack_is_healthy(self):
        """All three Docker services must be healthy before the rest run."""
        # OTel Collector health check extension
        resp = requests.get(OTEL_HEALTH_URL, timeout=5)
        assert resp.status_code == 200, "OTel Collector health check failed"

        # Jaeger query API
        resp = requests.get(f"{JAEGER_URL}/api/v3/services", timeout=5)
        assert resp.status_code == 200, "Jaeger API not responding"

        # Prometheus
        resp = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=5)
        assert resp.status_code == 200, "Prometheus not healthy"

    # ── agent execution spans ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_agent_execution_spans_appear_in_jaeger(self, otel_provider):
        """
        Run two agents (summarizer → reviewer) under AgentTelemetry backed by
        the OtelBridgeTracer.  After flush, both operation spans must appear in
        Jaeger with the correct attributes.
        """
        bridge_tracer = OtelBridgeTracer(
            otel_provider.get_tracer("ia_modules.agents.execution")
        )
        telemetry = AgentTelemetry(
            collector=MetricsCollector(),
            tracer=bridge_tracer,
            enabled=True,
        )

        state = StateManager(thread_id="e2e-exec-001")
        summarizer = SummaryAgent(
            AgentRole(name="summarizer", description="Summarises content"),
            state, enable_telemetry=False,
        )
        reviewer = ReviewAgent(
            AgentRole(name="reviewer", description="Reviews summaries"),
            state, enable_telemetry=False,
        )

        # Execute both agents under tracked spans
        with telemetry.trace_agent_execution(
            "summarizer", "summarizer",
            input_data={"topic": "OpenTelemetry in AI systems"},
        ) as ctx:
            result = await summarizer.execute({"topic": "OpenTelemetry in AI systems"})
            ctx.set_result(result)

        with telemetry.trace_agent_execution("reviewer", "reviewer") as ctx:
            result = await reviewer.execute({})
            ctx.set_result(result)

        # Flush → collector → Jaeger
        otel_provider.force_flush(timeout_millis=5_000)

        # Wait for service to appear in Jaeger (batch + indexing delay)
        services = _wait_for_jaeger_service(SERVICE_NAME)
        assert SERVICE_NAME in services, (
            f"Service '{SERVICE_NAME}' not found in Jaeger. "
            f"Available services: {services}"
        )

        # Verify summarizer span
        traces = _wait_for_jaeger_traces(SERVICE_NAME, "agent.summarizer.execute")
        assert len(traces) >= 1, (
            "No traces found for operation 'agent.summarizer.execute'. "
            "Check the OTel Collector is receiving spans."
        )

        first_span = traces[0]["spans"][0]
        tags = {t["key"]: t["value"] for t in first_span.get("tags", [])}
        assert tags.get("agent.name") == "summarizer"
        assert tags.get("agent.role") == "summarizer"
        assert tags.get("agent.type") == "execution"
        assert int(tags.get("agent.input_size", -1)) > 0, (
            "agent.input_size tag must be set and positive when input_data is provided"
        )
        assert float(tags.get("agent.duration_seconds", -1)) >= 0, (
            "agent.duration_seconds tag must be present and non-negative"
        )

        # Verify reviewer span also present
        traces = _query_jaeger_traces(SERVICE_NAME, "agent.reviewer.execute")
        assert len(traces) >= 1, "No traces for 'agent.reviewer.execute'"

        # In-process assertions
        spans = bridge_tracer.get_spans()
        assert any("agent.summarizer" in s.name for s in spans)
        assert any("agent.reviewer" in s.name for s in spans)
        assert all(s.status == "ok" for s in spans)

        # MetricsCollector counters — both agents recorded as success
        assert telemetry.agent_executions.get(
            agent_name="summarizer", agent_role="summarizer", status="success"
        ) == 1, "summarizer execution not counted"
        assert telemetry.agent_executions.get(
            agent_name="reviewer", agent_role="reviewer", status="success"
        ) == 1, "reviewer execution not counted"

    # ── LLM telemetry spans ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_llm_telemetry_spans_appear_in_jaeger(self, otel_provider):
        """
        Record a simulated LLM call (no real API needed - just the span
        lifecycle) and verify the gen_ai.chat span with token attributes
        appears in Jaeger.
        """
        bridge_tracer = OtelBridgeTracer(
            otel_provider.get_tracer("ia_modules.llm")
        )
        llm_telemetry = LLMTelemetry(
            collector=MetricsCollector(),
            tracer=bridge_tracer,
            enabled=True,
        )

        with llm_telemetry.trace_llm_call("chat", "openai", "gpt-4o") as ctx:
            ctx.record_usage(
                prompt_tokens=120,
                completion_tokens=80,
                cost_usd=0.003,
                response_model="gpt-4o-2024-08-06",
                finish_reason="stop",
            )

        otel_provider.force_flush(timeout_millis=5_000)

        traces = _wait_for_jaeger_traces(SERVICE_NAME, "gen_ai.chat")
        assert len(traces) >= 1, "No gen_ai.chat traces found in Jaeger"

        first_span = traces[0]["spans"][0]
        tags = {t["key"]: t["value"] for t in first_span.get("tags", [])}
        assert tags.get("gen_ai.system") == "openai"
        assert tags.get("gen_ai.operation.name") == "chat"
        assert tags.get("gen_ai.request.model") == "gpt-4o"
        assert tags.get("gen_ai.response.model") == "gpt-4o-2024-08-06"
        assert int(tags.get("gen_ai.usage.prompt_tokens", -1)) == 120
        assert int(tags.get("gen_ai.usage.completion_tokens", -1)) == 80
        assert int(tags.get("gen_ai.usage.total_tokens", -1)) == 200, (
            "total_tokens should be prompt(120) + completion(80) = 200"
        )
        assert float(tags.get("gen_ai.usage.cost_usd", -1)) == pytest.approx(0.003), (
            "gen_ai.usage.cost_usd tag must match value passed to record_usage"
        )
        assert tags.get("gen_ai.response.finish_reason") == "stop", (
            "gen_ai.response.finish_reason tag missing or wrong"
        )
        assert float(tags.get("gen_ai.operation.duration_seconds", -1)) >= 0, (
            "gen_ai.operation.duration_seconds tag must be present and non-negative"
        )

        # MetricsCollector counters — request counted, cost accumulated
        # Note: requests is incremented by both record_usage_direct() and the
        # trace_llm_call() context manager exit, so the count is >= 1.
        assert llm_telemetry.requests.get(
            gen_ai_system="openai",
            gen_ai_response_model="gpt-4o-2024-08-06",
            status="success",
        ) >= 1, "LLM request not counted in MetricsCollector"
        assert llm_telemetry.cost.get(
            gen_ai_system="openai",
            gen_ai_response_model="gpt-4o-2024-08-06",
        ) == pytest.approx(0.003), "LLM cost not accumulated in MetricsCollector"

    # ── Collaboration span with child agent spans ──────────────────────────

    @pytest.mark.asyncio
    async def test_collaboration_trace_with_child_spans_in_jaeger(self, otel_provider):
        """
        Run a hierarchical collaboration (leader + 2 workers).  The
        collaboration span must appear in Jaeger, and at least two agent-level
        child spans must be nested inside the same trace.
        """
        bridge_tracer = OtelBridgeTracer(
            otel_provider.get_tracer("ia_modules.collaboration")
        )
        telemetry = AgentTelemetry(
            collector=MetricsCollector(),
            tracer=bridge_tracer,
            enabled=True,
        )

        state = StateManager(thread_id="e2e-collab-001")
        agent_configs = [
            ("leader",   "Coordinates workers"),
            ("worker_a", "Processes subset A"),
            ("worker_b", "Processes subset B"),
        ]
        agents = [
            SummaryAgent(AgentRole(name=n, description=d), state, enable_telemetry=False)
            for n, d in agent_configs
        ]

        # Collaboration span wraps all agent executions
        with telemetry.trace_collaboration(
            pattern="hierarchical",
            participants=["leader", "worker_a", "worker_b"],
        ) as collab_span:
            for agent in agents:
                with telemetry.trace_agent_execution(
                    agent.role.name,
                    agent.role.name,
                    parent_span=collab_span,
                ) as ctx:
                    result = await agent.execute({"topic": "AI pipeline architecture"})
                    ctx.set_result(result)

        otel_provider.force_flush(timeout_millis=5_000)

        traces = _wait_for_jaeger_traces(SERVICE_NAME, "collaboration.hierarchical")
        assert len(traces) >= 1, "No collaboration.hierarchical trace found in Jaeger"

        first_trace = traces[0]
        operation_names = {s["operationName"] for s in first_trace["spans"]}

        assert "collaboration.hierarchical" in operation_names
        agent_ops = [n for n in operation_names if n.startswith("agent.")]
        assert len(agent_ops) >= 2, (
            f"Expected ≥2 child agent spans in the collaboration trace, "
            f"found: {agent_ops}"
        )

        # Collaboration root span must carry pattern + participant_count tags
        collab_jaeger_spans = [
            s for s in first_trace["spans"]
            if s["operationName"] == "collaboration.hierarchical"
        ]
        assert collab_jaeger_spans, "collaboration.hierarchical span missing from trace"
        collab_tags = {t["key"]: t["value"] for t in collab_jaeger_spans[0].get("tags", [])}
        assert collab_tags.get("collaboration.pattern") == "hierarchical"
        assert collab_tags.get("collaboration.participants") == "leader,worker_a,worker_b"
        assert int(collab_tags.get("collaboration.participant_count", -1)) == 3

        # In-process check: verify collaboration span is "ok"
        spans = bridge_tracer.get_spans()
        collab_spans = [s for s in spans if "collaboration.hierarchical" in s.name]
        assert len(collab_spans) == 1
        assert collab_spans[0].status == "ok"

        # MetricsCollector: collaboration counted as success
        assert telemetry.collaboration_executions.get(
            pattern="hierarchical", status="success"
        ) == 1, "collaboration_executions_total not incremented"

    # ── Agent error propagation ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_agent_error_span_appears_in_jaeger(self, otel_provider):
        """
        An agent that raises an exception must produce an error-status span
        in Jaeger with the error.type attribute set.
        """
        bridge_tracer = OtelBridgeTracer(
            otel_provider.get_tracer("ia_modules.agents.errors")
        )
        telemetry = AgentTelemetry(
            collector=MetricsCollector(),
            tracer=bridge_tracer,
            enabled=True,
        )

        class BrokenAgent(BaseAgent):
            async def execute(self, input_data):
                raise RuntimeError("Simulated agent failure")

        state = StateManager(thread_id="e2e-error-001")
        broken = BrokenAgent(
            AgentRole(name="broken_agent", description="Always fails"),
            state, enable_telemetry=False,
        )

        with pytest.raises(RuntimeError, match="Simulated agent failure"):
            with telemetry.trace_agent_execution("broken_agent", "broken") as _ctx:
                await broken.execute({})

        otel_provider.force_flush(timeout_millis=5_000)

        traces = _wait_for_jaeger_traces(SERVICE_NAME, "agent.broken_agent.execute")
        assert len(traces) >= 1, "Error span not found in Jaeger"

        first_span = traces[0]["spans"][0]
        tags = {t["key"]: t["value"] for t in first_span.get("tags", [])}
        assert tags.get("error.type") == "RuntimeError"
        assert "Simulated agent failure" in tags.get("error.message", ""), (
            "error.message tag must contain the exception message"
        )

        # In-process: span stored with error status
        spans = bridge_tracer.get_spans()
        err_spans = [s for s in spans if "broken_agent" in s.name]
        assert len(err_spans) == 1
        assert err_spans[0].status == "error"

        # MetricsCollector: error counted
        assert telemetry.agent_errors.get(
            agent_name="broken_agent", agent_role="broken", error_type="RuntimeError"
        ) == 1, "agent_errors_total not incremented for RuntimeError"

    # ── OTel Collector received spans ──────────────────────────────────────

    def test_otel_collector_received_spans(self):
        """
        The OTel Collector's own Prometheus metrics endpoint must show that at
        least one span was accepted by the OTLP receiver by the time this test
        runs (all earlier tests sent spans).
        """
        try:
            resp = requests.get(OTEL_METRICS_URL, timeout=5)
        except Exception as exc:
            raise AssertionError(f"OTel Collector metrics endpoint not reachable: {exc}") from exc

        assert resp.status_code == 200
        text = resp.text
        assert "ia_modules_otelcol_receiver_accepted_spans_total" in text, (
            "Expected 'ia_modules_otelcol_receiver_accepted_spans_total' metric in OTel Collector output. "
            "No spans may have been accepted yet."
        )

        # Extract the counter value and assert it is > 0
        otlp_line = next(
            (
                line for line in text.splitlines()
                if line.startswith("ia_modules_otelcol_receiver_accepted_spans_total{")
                and "otlp" in line
            ),
            None,
        )
        assert otlp_line is not None, (
            "No ia_modules_otelcol_receiver_accepted_spans_total line with "
            "receiver='otlp' found in collector metrics. "
            "Earlier tests may not have exported spans successfully."
        )
        parts = otlp_line.rsplit(" ", 1)
        assert len(parts) == 2, f"Unexpected metric line format: {otlp_line!r}"
        accepted = float(parts[1])
        assert accepted > 0, (
            f"Collector accepted {accepted} OTLP spans; expected > 0. "
            "Earlier tests may not have exported successfully."
        )
