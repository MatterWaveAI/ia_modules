"""
Agent Telemetry - Automatic instrumentation for agent execution.

Provides metrics collection and distributed tracing for agents,
message passing, and collaboration patterns.
"""

import time
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from .metrics import MetricsCollector
from .tracing import Tracer, SimpleTracer

logger = logging.getLogger(__name__)


class AgentTelemetry:
    """
    Automatic telemetry for agent execution.

    Mirrors PipelineTelemetry but focused on agent-level metrics:
    - Agent execution count, duration, errors
    - Message bus traffic (sent, received, latency)
    - Iteration tracking for feedback loops
    - State operation counts
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
        """Set up agent-specific metrics"""

        # --- Agent execution metrics ---
        self.agent_executions = self.collector.counter(
            "agent_executions_total",
            help_text="Total agent executions",
            labels=["agent_name", "agent_role", "status"]
        )

        self.agent_duration = self.collector.histogram(
            "agent_execution_duration_seconds",
            help_text="Agent execution duration in seconds",
            labels=["agent_name", "agent_role"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )

        self.active_agents = self.collector.gauge(
            "active_agents",
            help_text="Currently executing agents",
            labels=["agent_role"]
        )

        self.agent_errors = self.collector.counter(
            "agent_errors_total",
            help_text="Total agent errors",
            labels=["agent_name", "agent_role", "error_type"]
        )

        self.agent_iterations = self.collector.counter(
            "agent_iterations_total",
            help_text="Total agent iteration loops",
            labels=["agent_name"]
        )

        # --- Message bus metrics ---
        self.messages_sent = self.collector.counter(
            "agent_messages_sent_total",
            help_text="Total messages sent between agents",
            labels=["sender", "recipient", "message_type"]
        )

        self.messages_received = self.collector.counter(
            "agent_messages_received_total",
            help_text="Total messages received by agents",
            labels=["recipient", "message_type"]
        )

        self.message_latency = self.collector.histogram(
            "agent_message_latency_seconds",
            help_text="Message delivery latency",
            labels=["message_type"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )

        self.pending_messages = self.collector.gauge(
            "agent_pending_messages",
            help_text="Messages pending in agent queues",
            labels=["agent_name"]
        )

        self.message_errors = self.collector.counter(
            "agent_message_errors_total",
            help_text="Message delivery failures",
            labels=["sender", "recipient", "error_type"]
        )

        # --- State operation metrics ---
        self.state_operations = self.collector.counter(
            "agent_state_operations_total",
            help_text="State read/write operations",
            labels=["agent_name", "operation"]  # operation: read, write, snapshot
        )

        # --- Collaboration metrics ---
        self.collaboration_executions = self.collector.counter(
            "agent_collaboration_executions_total",
            help_text="Collaboration pattern executions",
            labels=["pattern", "status"]  # pattern: hierarchical, consensus, debate, peer_to_peer
        )

        self.collaboration_duration = self.collector.histogram(
            "agent_collaboration_duration_seconds",
            help_text="Collaboration pattern duration",
            labels=["pattern"],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
        )

    # ─── Context Managers ────────────────────────────────────────────

    @contextmanager
    def trace_agent_execution(
        self,
        agent_name: str,
        agent_role: str,
        input_data: Optional[Dict[str, Any]] = None,
        parent_span=None
    ):
        """
        Trace an agent execution.

        Usage:
            with agent_telemetry.trace_agent_execution("researcher", "research") as ctx:
                result = await agent.execute(input_data)
                ctx.set_result(result)
        """
        if not self.enabled:
            yield _NoOpAgentContext()
            return

        span = self.tracer.start_span(
            f"agent.{agent_name}.execute",
            attributes={
                "agent.name": agent_name,
                "agent.role": agent_role,
                "agent.type": "execution"
            },
            parent=parent_span
        )

        if input_data:
            span.set_attribute("agent.input_size", len(str(input_data)))

        start_time = time.time()
        self.active_agents.inc(agent_role=agent_role)

        ctx = _AgentExecutionContext(
            agent_name=agent_name,
            agent_role=agent_role,
            span=span,
            telemetry=self
        )

        try:
            yield ctx
            span.set_status("ok")
            self.agent_executions.inc(
                agent_name=agent_name,
                agent_role=agent_role,
                status="success"
            )
        except Exception as e:
            error_type = type(e).__name__
            span.set_status("error", str(e))
            span.set_attribute("error.type", error_type)
            span.set_attribute("error.message", str(e))
            self.agent_executions.inc(
                agent_name=agent_name,
                agent_role=agent_role,
                status="error"
            )
            self.agent_errors.inc(
                agent_name=agent_name,
                agent_role=agent_role,
                error_type=error_type
            )
            raise
        finally:
            duration = time.time() - start_time
            self.agent_duration.observe(
                duration,
                agent_name=agent_name,
                agent_role=agent_role
            )
            span.set_attribute("agent.duration_seconds", duration)
            self.active_agents.dec(agent_role=agent_role)
            self.tracer.end_span(span)

    @contextmanager
    def trace_message_send(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        parent_span=None
    ):
        """Trace a message send operation."""
        if not self.enabled:
            yield _NoOpAgentContext()
            return

        span = self.tracer.start_span(
            f"agent.{sender}.message.send",
            attributes={
                "agent.message.sender": sender,
                "agent.message.recipient": recipient,
                "agent.message.type": message_type
            },
            parent=parent_span
        )

        start_time = time.time()

        try:
            yield span
            span.set_status("ok")
            self.messages_sent.inc(
                sender=sender,
                recipient=recipient,
                message_type=message_type
            )
        except Exception as e:
            span.set_status("error", str(e))
            self.message_errors.inc(
                sender=sender,
                recipient=recipient,
                error_type=type(e).__name__
            )
            raise
        finally:
            latency = time.time() - start_time
            self.message_latency.observe(latency, message_type=message_type)
            self.tracer.end_span(span)

    @contextmanager
    def trace_collaboration(
        self,
        pattern: str,
        participants: Optional[List[str]] = None,
        parent_span=None
    ):
        """Trace a collaboration pattern execution."""
        if not self.enabled:
            yield _NoOpAgentContext()
            return

        span = self.tracer.start_span(
            f"collaboration.{pattern}",
            attributes={
                "collaboration.pattern": pattern,
                "collaboration.participants": ",".join(participants or []),
                "collaboration.participant_count": len(participants or [])
            },
            parent=parent_span
        )

        start_time = time.time()

        try:
            yield span
            span.set_status("ok")
            self.collaboration_executions.inc(pattern=pattern, status="success")
        except Exception as e:
            span.set_status("error", str(e))
            self.collaboration_executions.inc(pattern=pattern, status="error")
            raise
        finally:
            duration = time.time() - start_time
            self.collaboration_duration.observe(duration, pattern=pattern)
            self.tracer.end_span(span)

    # ─── Direct recording methods ────────────────────────────────────

    def record_message_received(self, recipient: str, message_type: str):
        """Record a message received event."""
        if self.enabled:
            self.messages_received.inc(
                recipient=recipient,
                message_type=message_type
            )

    def record_state_operation(self, agent_name: str, operation: str):
        """Record a state read/write/snapshot operation."""
        if self.enabled:
            self.state_operations.inc(
                agent_name=agent_name,
                operation=operation
            )

    def record_iteration(self, agent_name: str):
        """Record an agent iteration."""
        if self.enabled:
            self.agent_iterations.inc(agent_name=agent_name)

    def update_pending_messages(self, agent_name: str, count: int):
        """Update the pending messages gauge for an agent."""
        if self.enabled:
            self.pending_messages.set(float(count), agent_name=agent_name)

    def get_metrics(self):
        """Get all collected metrics."""
        return self.collector.collect_all()

    def get_spans(self, trace_id: Optional[str] = None):
        """Get all spans or spans for a specific trace."""
        if trace_id:
            return self.tracer.get_spans(trace_id)
        return self.tracer.get_spans()  # type: ignore[attr-defined]


class _AgentExecutionContext:
    """Context object yielded from trace_agent_execution."""

    def __init__(self, agent_name: str, agent_role: str, span, telemetry: AgentTelemetry):
        self.agent_name = agent_name
        self.agent_role = agent_role
        self.span = span
        self.telemetry = telemetry

    def set_result(self, result: Any):
        if result:
            self.span.set_attribute("agent.result_size", len(str(result)))

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.span.add_event(name, attributes)

    def set_attribute(self, key: str, value: Any):
        self.span.set_attribute(key, value)

    def record_iteration(self):
        self.telemetry.record_iteration(self.agent_name)


class _NoOpAgentContext:
    """No-op context when telemetry is disabled."""

    def set_result(self, result: Any): pass
    def add_event(self, name: str, attributes=None): pass
    def set_attribute(self, key: str, value: Any): pass
    def record_iteration(self): pass
