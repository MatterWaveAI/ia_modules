"""
LLM Telemetry - OpenTelemetry gen_ai semantic conventions.

Tracks token usage, cost, latency, and model information for all LLM calls.
Follows: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

import time
import logging
from typing import Optional, Any
from contextlib import contextmanager

from .metrics import MetricsCollector
from .tracing import Tracer, SimpleTracer

logger = logging.getLogger(__name__)


class LLMTelemetry:
    """
    Telemetry for LLM API calls using OpenTelemetry gen_ai conventions.

    Metrics follow the gen_ai semantic convention naming:
    - gen_ai.client.token.usage
    - gen_ai.client.operation.duration
    """

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        tracer: Optional[Tracer] = None,
        enabled: bool = True
    ):
        self.enabled = enabled
        self.collector = collector or MetricsCollector()
        self.tracer = tracer or SimpleTracer()

        if self.enabled:
            self._setup_metrics()

    def _setup_metrics(self):
        """Set up gen_ai semantic convention metrics."""

        # Token usage histogram
        self.token_usage = self.collector.histogram(
            "gen_ai_client_token_usage",
            help_text="Token usage per LLM request",
            labels=["gen_ai_operation_name", "gen_ai_system", "gen_ai_response_model", "token_type"],
            buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 50000]
        )

        # Operation duration
        self.operation_duration = self.collector.histogram(
            "gen_ai_client_operation_duration_seconds",
            help_text="LLM operation duration in seconds",
            labels=["gen_ai_operation_name", "gen_ai_system", "gen_ai_response_model"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
        )

        # Request counter
        self.requests = self.collector.counter(
            "gen_ai_client_requests_total",
            help_text="Total LLM API requests",
            labels=["gen_ai_system", "gen_ai_response_model", "status"]
        )

        # Cost tracking
        self.cost = self.collector.counter(
            "gen_ai_client_cost_usd_total",
            help_text="Total LLM cost in USD",
            labels=["gen_ai_system", "gen_ai_response_model"]
        )

        # Tokens per second (throughput)
        self.tokens_per_second = self.collector.histogram(
            "gen_ai_client_tokens_per_second",
            help_text="Token generation throughput",
            labels=["gen_ai_system", "gen_ai_response_model"],
            buckets=[1, 5, 10, 25, 50, 100, 200, 500]
        )

    @contextmanager
    def trace_llm_call(
        self,
        operation: str = "chat",
        system: str = "unknown",
        model: str = "unknown",
        parent_span=None
    ):
        """
        Trace an LLM API call.

        Usage:
            with llm_telemetry.trace_llm_call("chat", "openai", "gpt-4") as ctx:
                response = await litellm.acompletion(...)
                ctx.record_usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    cost_usd=response._hidden_params.get("response_cost", 0)
                )

        Args:
            operation: gen_ai operation name (chat, embedding, completion)
            system: gen_ai system (openai, anthropic, google, ollama)
            model: model identifier
            parent_span: parent span for nesting
        """
        if not self.enabled:
            yield _NoOpLLMContext()
            return

        span = self.tracer.start_span(
            f"gen_ai.{operation}",
            attributes={
                "gen_ai.operation.name": operation,
                "gen_ai.system": system,
                "gen_ai.request.model": model,
            },
            parent=parent_span
        )

        start_time = time.time()

        ctx = _LLMCallContext(
            operation=operation,
            system=system,
            model=model,
            span=span,
            telemetry=self,
            start_time=start_time
        )

        try:
            yield ctx
            span.set_status("ok")
            self.requests.inc(
                gen_ai_system=system,
                gen_ai_response_model=ctx.response_model or model,
                status="success"
            )
        except Exception as e:
            span.set_status("error", str(e))
            span.set_attribute("error.type", type(e).__name__)
            self.requests.inc(
                gen_ai_system=system,
                gen_ai_response_model=ctx.response_model or model,
                status="error"
            )
            raise
        finally:
            duration = time.time() - start_time
            response_model = ctx.response_model or model
            self.operation_duration.observe(
                duration,
                gen_ai_operation_name=operation,
                gen_ai_system=system,
                gen_ai_response_model=response_model
            )
            span.set_attribute("gen_ai.operation.duration_seconds", duration)
            self.tracer.end_span(span)

    def record_usage_direct(
        self,
        operation: str,
        system: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_seconds: float = 0.0
    ):
        """Record LLM usage without span context (for after-the-fact recording)."""
        if not self.enabled:
            return

        # Token usage
        if prompt_tokens > 0:
            self.token_usage.observe(
                prompt_tokens,
                gen_ai_operation_name=operation,
                gen_ai_system=system,
                gen_ai_response_model=model,
                token_type="prompt"
            )
        if completion_tokens > 0:
            self.token_usage.observe(
                completion_tokens,
                gen_ai_operation_name=operation,
                gen_ai_system=system,
                gen_ai_response_model=model,
                token_type="completion"
            )

        # Cost
        if cost_usd > 0:
            self.cost.inc(
                amount=cost_usd,
                gen_ai_system=system,
                gen_ai_response_model=model
            )

        # Throughput
        if duration_seconds > 0 and completion_tokens > 0:
            tps = completion_tokens / duration_seconds
            self.tokens_per_second.observe(
                tps,
                gen_ai_system=system,
                gen_ai_response_model=model
            )

        # Request count
        self.requests.inc(
            gen_ai_system=system,
            gen_ai_response_model=model,
            status="success"
        )

    def get_metrics(self):
        return self.collector.collect_all()

    def get_spans(self, trace_id=None):
        if trace_id:
            return self.tracer.get_spans(trace_id)
        return self.tracer.get_spans()


class _LLMCallContext:
    """Context yielded from trace_llm_call."""

    def __init__(self, operation, system, model, span, telemetry, start_time):
        self.operation = operation
        self.system = system
        self.model = model
        self.response_model = None
        self.span = span
        self.telemetry = telemetry
        self.start_time = start_time

    def record_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
        cost_usd: float = 0.0,
        response_model: Optional[str] = None,
        finish_reason: Optional[str] = None
    ):
        """Record token usage and cost from LLM response."""
        if response_model:
            self.response_model = response_model
            self.span.set_attribute("gen_ai.response.model", response_model)

        if finish_reason:
            self.span.set_attribute("gen_ai.response.finish_reason", finish_reason)

        actual_total = total_tokens or (prompt_tokens + completion_tokens)

        self.span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        self.span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        self.span.set_attribute("gen_ai.usage.total_tokens", actual_total)
        self.span.set_attribute("gen_ai.usage.cost_usd", cost_usd)

        model = self.response_model or self.model
        duration = time.time() - self.start_time

        self.telemetry.record_usage_direct(
            operation=self.operation,
            system=self.system,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            duration_seconds=duration
        )

    def set_attribute(self, key: str, value: Any):
        self.span.set_attribute(key, value)


class _NoOpLLMContext:
    def record_usage(self, **kwargs): pass
    def set_attribute(self, key, value): pass
