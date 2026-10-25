"""
Telemetry Integration for IA Modules Pipeline

Provides automatic instrumentation for pipelines and steps with metrics and tracing.
"""

import time
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .metrics import MetricsCollector
from .tracing import Tracer, SimpleTracer
from .agent_telemetry import AgentTelemetry
from .llm_telemetry import LLMTelemetry

logger = logging.getLogger(__name__)


class PipelineTelemetry:
    """
    Automatic telemetry for pipeline execution.

    Provides automatic metrics collection and distributed tracing for pipelines.
    """

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        tracer: Optional[Tracer] = None,
        enabled: bool = True
    ):
        """
        Initialize pipeline telemetry.

        Args:
            collector: Metrics collector instance (creates new if None)
            tracer: Tracer instance (creates new SimpleTracer if None)
            enabled: Whether telemetry is enabled
        """
        self.enabled = enabled
        self.collector = collector or MetricsCollector()
        self.tracer = tracer or SimpleTracer()

        if self.enabled:
            self._setup_metrics()

    def _setup_metrics(self):
        """Set up default pipeline metrics"""
        # Execution metrics
        self.executions = self.collector.counter(
            "pipeline_executions_total",
            help_text="Total pipeline executions",
            labels=["pipeline_name", "status"]
        )

        self.duration = self.collector.histogram(
            "pipeline_duration_seconds",
            help_text="Pipeline execution duration",
            labels=["pipeline_name"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
        )

        self.active_pipelines = self.collector.gauge(
            "active_pipelines",
            help_text="Currently executing pipelines",
            labels=["pipeline_name"]
        )

        # Step metrics
        self.step_duration = self.collector.histogram(
            "step_duration_seconds",
            help_text="Step execution duration",
            labels=["pipeline_name", "step_name"],
            buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
        )

        self.step_errors = self.collector.counter(
            "step_errors_total",
            help_text="Total step errors",
            labels=["pipeline_name", "step_name", "error_type"]
        )

        # Performance metrics
        self.items_processed = self.collector.counter(
            "items_processed_total",
            help_text="Total items processed",
            labels=["pipeline_name"]
        )

        self.api_calls = self.collector.counter(
            "api_calls_total",
            help_text="Total API calls",
            labels=["pipeline_name"]
        )

        self.pipeline_cost = self.collector.counter(
            "pipeline_cost_usd_total",
            help_text="Total pipeline cost in USD",
            labels=["pipeline_name"]
        )

        # Resource metrics
        self.pipeline_memory = self.collector.gauge(
            "pipeline_memory_bytes",
            help_text="Pipeline memory usage",
            labels=["pipeline_name"]
        )

        self.pipeline_cpu = self.collector.gauge(
            "pipeline_cpu_percent",
            help_text="Pipeline CPU usage percentage",
            labels=["pipeline_name"]
        )

    @contextmanager
    def trace_pipeline(self, pipeline_name: str, input_data: Optional[Dict[str, Any]] = None):
        """
        Trace a pipeline execution.

        Usage:
            with telemetry.trace_pipeline("my_pipeline") as ctx:
                # Run pipeline
                result = await pipeline.run()
                ctx.set_result(result)

        Args:
            pipeline_name: Name of the pipeline
            input_data: Optional input data for tracing
        """
        if not self.enabled:
            yield _NoOpContext()
            return

        # Start span
        span = self.tracer.start_span(
            f"pipeline.{pipeline_name}",
            attributes={
                "pipeline.name": pipeline_name,
                "pipeline.type": "execution"
            }
        )

        if input_data:
            span.set_attribute("pipeline.input_size", len(str(input_data)))

        # Start timing
        start_time = time.time()

        # Increment active pipelines
        self.active_pipelines.inc(pipeline_name=pipeline_name)

        ctx = _PipelineContext(
            pipeline_name=pipeline_name,
            span=span,
            telemetry=self
        )

        try:
            yield ctx

            # Success
            span.set_status("ok")
            self.executions.inc(pipeline_name=pipeline_name, status="success")

        except Exception as e:
            # Error
            error_type = type(e).__name__
            span.set_status("error", str(e))
            self.executions.inc(pipeline_name=pipeline_name, status="error")
            span.set_attribute("error.type", error_type)
            span.set_attribute("error.message", str(e))
            raise

        finally:
            # Record duration
            duration = time.time() - start_time
            self.duration.observe(duration, pipeline_name=pipeline_name)
            span.set_attribute("pipeline.duration_seconds", duration)

            # Decrement active pipelines
            self.active_pipelines.dec(pipeline_name=pipeline_name)

            # End span
            self.tracer.end_span(span)

    @contextmanager
    def trace_step(
        self,
        pipeline_name: str,
        step_name: str,
        parent_span=None
    ):
        """
        Trace a step execution.

        Usage:
            with telemetry.trace_step(pipeline_name, step_name) as ctx:
                # Execute step
                result = await step.execute()
                ctx.set_output(result)

        Args:
            pipeline_name: Name of the pipeline
            step_name: Name of the step
            parent_span: Parent span for nesting
        """
        if not self.enabled:
            yield _NoOpContext()
            return

        # Start span
        span = self.tracer.start_span(
            f"step.{step_name}",
            attributes={
                "step.name": step_name,
                "pipeline.name": pipeline_name
            },
            parent=parent_span
        )

        start_time = time.time()

        ctx = _StepContext(
            pipeline_name=pipeline_name,
            step_name=step_name,
            span=span,
            telemetry=self
        )

        try:
            yield ctx
            span.set_status("ok")

        except Exception as e:
            error_type = type(e).__name__
            span.set_status("error", str(e))
            self.step_errors.inc(
                pipeline_name=pipeline_name,
                step_name=step_name,
                error_type=error_type
            )
            span.set_attribute("error.type", error_type)
            span.set_attribute("error.message", str(e))
            raise

        finally:
            duration = time.time() - start_time
            self.step_duration.observe(
                duration,
                pipeline_name=pipeline_name,
                step_name=step_name
            )
            span.set_attribute("step.duration_seconds", duration)
            self.tracer.end_span(span)

    def record_benchmark_result(
        self,
        pipeline_name: str,
        result: Any
    ):
        """
        Record benchmark results as telemetry metrics.

        Bridges benchmark framework with telemetry system.

        Args:
            pipeline_name: Name of the pipeline
            result: Benchmark result to record
        """
        if not self.enabled:
            return

        # Record duration
        if result.total_time > 0:
            self.duration.observe(result.total_time, pipeline_name=pipeline_name)

        # Record items processed
        if result.items_processed > 0:
            self.items_processed.inc(
                amount=result.items_processed,
                pipeline_name=pipeline_name
            )

        # Record API calls
        if result.api_calls_count > 0:
            self.api_calls.inc(
                amount=result.api_calls_count,
                pipeline_name=pipeline_name
            )

        # Record cost
        if result.estimated_cost_usd > 0:
            self.pipeline_cost.inc(
                amount=result.estimated_cost_usd,
                pipeline_name=pipeline_name
            )

        # Record memory (from memory_stats if available)
        if result.memory_stats and 'delta_mb' in result.memory_stats:
            self.pipeline_memory.set(
                result.memory_stats['delta_mb'] * 1024 * 1024,  # Convert to bytes
                pipeline_name=pipeline_name
            )
        elif result.memory_per_operation_mb > 0:
            # Estimate total from per-operation metric
            total_mb = result.memory_per_operation_mb * result.iterations
            self.pipeline_memory.set(
                total_mb * 1024 * 1024,
                pipeline_name=pipeline_name
            )

        # Record CPU
        if result.cpu_stats and 'average_cpu_percent' in result.cpu_stats:
            self.pipeline_cpu.set(
                result.cpu_stats['average_cpu_percent'],
                pipeline_name=pipeline_name
            )
        elif result.cpu_per_operation_percent > 0:
            self.pipeline_cpu.set(
                result.cpu_per_operation_percent,
                pipeline_name=pipeline_name
            )

    def get_metrics(self):
        """Get all collected metrics"""
        return self.collector.collect_all()

    def get_spans(self, trace_id: Optional[str] = None):
        """Get all spans or spans for a specific trace"""
        if trace_id:
            return self.tracer.get_spans(trace_id)
        return self.tracer.get_spans()  # type: ignore[attr-defined]


class _PipelineContext:
    """Context for pipeline execution"""

    def __init__(self, pipeline_name: str, span, telemetry: PipelineTelemetry):
        self.pipeline_name = pipeline_name
        self.span = span
        self.telemetry = telemetry

    def set_result(self, result: Any):
        """Set pipeline result"""
        if result:
            self.span.set_attribute("pipeline.result_size", len(str(result)))

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to pipeline span"""
        self.span.add_event(name, attributes)

    def set_attribute(self, key: str, value: Any):
        """Set attribute on pipeline span"""
        self.span.set_attribute(key, value)

    def record_items(self, count: int):
        """Record items processed"""
        self.telemetry.items_processed.inc(
            amount=count,
            pipeline_name=self.pipeline_name
        )
        self.span.set_attribute("pipeline.items_processed", count)

    def record_cost(self, api_calls: int = 0, cost_usd: float = 0.0):
        """Record API calls and cost"""
        if api_calls > 0:
            self.telemetry.api_calls.inc(
                amount=api_calls,
                pipeline_name=self.pipeline_name
            )
            self.span.set_attribute("pipeline.api_calls", api_calls)

        if cost_usd > 0:
            self.telemetry.pipeline_cost.inc(
                amount=cost_usd,
                pipeline_name=self.pipeline_name
            )
            self.span.set_attribute("pipeline.cost_usd", cost_usd)


class _StepContext:
    """Context for step execution"""

    def __init__(self, pipeline_name: str, step_name: str, span, telemetry: PipelineTelemetry):
        self.pipeline_name = pipeline_name
        self.step_name = step_name
        self.span = span
        self.telemetry = telemetry

    def set_output(self, output: Any):
        """Set step output"""
        if output:
            self.span.set_attribute("step.output_size", len(str(output)))

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to step span"""
        self.span.add_event(name, attributes)

    def set_attribute(self, key: str, value: Any):
        """Set attribute on step span"""
        self.span.set_attribute(key, value)


class _NoOpContext:
    """No-op context when telemetry is disabled"""

    def set_result(self, result: Any):
        pass

    def set_output(self, output: Any):
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        pass

    def set_attribute(self, key: str, value: Any):
        pass

    def record_items(self, count: int):
        pass

    def record_cost(self, api_calls: int = 0, cost_usd: float = 0.0):
        pass


# Global telemetry instances
_global_telemetry: Optional[PipelineTelemetry] = None
_global_agent_telemetry: Optional[AgentTelemetry] = None
_global_llm_telemetry: Optional[LLMTelemetry] = None


def get_telemetry(
    collector: Optional[MetricsCollector] = None,
    tracer: Optional[Tracer] = None,
    enabled: bool = True
) -> PipelineTelemetry:
    """
    Get or create global telemetry instance.

    Args:
        collector: Metrics collector (uses global if None)
        tracer: Tracer (uses global if None)
        enabled: Whether telemetry is enabled

    Returns:
        PipelineTelemetry instance
    """
    global _global_telemetry

    if _global_telemetry is None:
        _global_telemetry = PipelineTelemetry(
            collector=collector,
            tracer=tracer,
            enabled=enabled
        )

    return _global_telemetry


def configure_telemetry(
    collector: Optional[MetricsCollector] = None,
    tracer: Optional[Tracer] = None,
    enabled: bool = True
) -> PipelineTelemetry:
    """
    Configure global telemetry instance.

    Args:
        collector: Metrics collector
        tracer: Tracer
        enabled: Whether telemetry is enabled

    Returns:
        New PipelineTelemetry instance
    """
    global _global_telemetry

    _global_telemetry = PipelineTelemetry(
        collector=collector,
        tracer=tracer,
        enabled=enabled
    )

    return _global_telemetry


def get_agent_telemetry(
    collector: Optional[MetricsCollector] = None,
    tracer: Optional[Tracer] = None,
    enabled: bool = True
) -> AgentTelemetry:
    """Get or create global agent telemetry instance."""
    global _global_agent_telemetry
    if _global_agent_telemetry is None:
        _global_agent_telemetry = AgentTelemetry(
            collector=collector,
            tracer=tracer,
            enabled=enabled
        )
    return _global_agent_telemetry


def get_llm_telemetry(
    collector: Optional[MetricsCollector] = None,
    tracer: Optional[Tracer] = None,
    enabled: bool = True
) -> LLMTelemetry:
    """Get or create global LLM telemetry instance."""
    global _global_llm_telemetry
    if _global_llm_telemetry is None:
        _global_llm_telemetry = LLMTelemetry(
            collector=collector,
            tracer=tracer,
            enabled=enabled
        )
    return _global_llm_telemetry


def configure_agent_telemetry(
    collector: Optional[MetricsCollector] = None,
    tracer: Optional[Tracer] = None,
    enabled: bool = True
) -> AgentTelemetry:
    """Configure global agent telemetry instance."""
    global _global_agent_telemetry
    _global_agent_telemetry = AgentTelemetry(
        collector=collector, tracer=tracer, enabled=enabled
    )
    return _global_agent_telemetry


def configure_llm_telemetry(
    collector: Optional[MetricsCollector] = None,
    tracer: Optional[Tracer] = None,
    enabled: bool = True
) -> LLMTelemetry:
    """Configure global LLM telemetry instance."""
    global _global_llm_telemetry
    _global_llm_telemetry = LLMTelemetry(
        collector=collector, tracer=tracer, enabled=enabled
    )
    return _global_llm_telemetry
