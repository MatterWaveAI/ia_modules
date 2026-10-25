"""Integration tests for LLM telemetry"""

import pytest
from ia_modules.telemetry.metrics import MetricsCollector
from ia_modules.telemetry.tracing import SimpleTracer
from ia_modules.telemetry.llm_telemetry import LLMTelemetry


@pytest.fixture
def llm_telemetry():
    collector = MetricsCollector()
    tracer = SimpleTracer()
    return LLMTelemetry(collector=collector, tracer=tracer, enabled=True)


class TestLLMTelemetry:

    def test_trace_llm_call_creates_span(self, llm_telemetry):
        with llm_telemetry.trace_llm_call("chat", "openai", "gpt-4o") as ctx:
            ctx.record_usage(
                prompt_tokens=150,
                completion_tokens=50,
                cost_usd=0.003,
                response_model="gpt-4o-2024-08-06",
                finish_reason="stop"
            )

        spans = llm_telemetry.get_spans()
        assert len(spans) == 1
        assert spans[0].name == "gen_ai.chat"
        assert spans[0].attributes["gen_ai.system"] == "openai"
        assert spans[0].attributes["gen_ai.usage.prompt_tokens"] == 150
        assert spans[0].attributes["gen_ai.usage.completion_tokens"] == 50

    def test_token_usage_metrics(self, llm_telemetry):
        with llm_telemetry.trace_llm_call("chat", "anthropic", "claude-sonnet-4-20250514") as ctx:
            ctx.record_usage(prompt_tokens=200, completion_tokens=100, cost_usd=0.005)

        metrics = llm_telemetry.get_metrics()
        token_metrics = [m for m in metrics if "token_usage" in m.name]
        assert len(token_metrics) > 0

        cost_metrics = [m for m in metrics if "cost_usd" in m.name]
        assert len(cost_metrics) > 0

    def test_error_tracking(self, llm_telemetry):
        with pytest.raises(ValueError):
            with llm_telemetry.trace_llm_call("chat", "openai", "gpt-4o") as _ctx:
                raise ValueError("Rate limit exceeded")

        spans = llm_telemetry.get_spans()
        assert spans[0].status == "error"

        metrics = llm_telemetry.get_metrics()
        req_metrics = [m for m in metrics if "requests_total" in m.name]
        error_reqs = [m for m in req_metrics if m.labels.get("status") == "error"]
        assert len(error_reqs) > 0

    def test_direct_usage_recording(self, llm_telemetry):
        llm_telemetry.record_usage_direct(
            operation="chat",
            system="openai",
            model="gpt-4o-mini",
            prompt_tokens=50,
            completion_tokens=25,
            cost_usd=0.0001,
            duration_seconds=0.5
        )

        metrics = llm_telemetry.get_metrics()
        assert len(metrics) > 0

        tps_metrics = [m for m in metrics if "tokens_per_second" in m.name]
        assert len(tps_metrics) > 0

    def test_multiple_providers(self, llm_telemetry):
        # OpenAI call
        with llm_telemetry.trace_llm_call("chat", "openai", "gpt-4o") as ctx:
            ctx.record_usage(prompt_tokens=100, completion_tokens=50, cost_usd=0.002)

        # Anthropic call
        with llm_telemetry.trace_llm_call("chat", "anthropic", "claude-sonnet-4-20250514") as ctx:
            ctx.record_usage(prompt_tokens=100, completion_tokens=80, cost_usd=0.004)

        # Google call
        with llm_telemetry.trace_llm_call("chat", "google", "gemini-2.0-flash") as ctx:
            ctx.record_usage(prompt_tokens=100, completion_tokens=60, cost_usd=0.001)

        metrics = llm_telemetry.get_metrics()
        req_metrics = [m for m in metrics if "requests_total" in m.name]
        # Should have entries for 3 different providers
        assert len(req_metrics) >= 3

    def test_disabled_telemetry_noop(self):
        disabled = LLMTelemetry(enabled=False)

        with disabled.trace_llm_call("chat", "openai", "gpt-4o") as ctx:
            ctx.record_usage(prompt_tokens=100, completion_tokens=50)

        assert len(disabled.get_spans()) == 0

    def test_response_model_override(self, llm_telemetry):
        with llm_telemetry.trace_llm_call("chat", "openai", "gpt-4o") as ctx:
            ctx.record_usage(
                prompt_tokens=100,
                completion_tokens=50,
                response_model="gpt-4o-2024-11-20"
            )

        spans = llm_telemetry.get_spans()
        assert spans[0].attributes["gen_ai.response.model"] == "gpt-4o-2024-11-20"
