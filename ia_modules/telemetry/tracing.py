"""
Distributed Tracing Support

OpenTelemetry integration for distributed tracing.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, List
from contextlib import contextmanager
import time
import logging
from functools import wraps


class Span:
    """
    Represents a span in distributed tracing

    A span represents a single operation within a trace.
    """

    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.attributes = attributes or {}
        self.events: list = []
        self.status = "unset"
        self.start_time = time.time()
        self.end_time: Optional[float] = None

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span"""
        self.events.append({
            'name': name,
            'timestamp': time.time(),
            'attributes': attributes or {}
        })

    def set_status(self, status: str, description: Optional[str] = None) -> None:
        """Set span status (ok, error, unset)"""
        self.status = status
        if description:
            self.set_attribute('status.description', description)

    def finish(self) -> None:
        """Finish the span"""
        if self.end_time is None:
            self.end_time = time.time()

    @property
    def duration(self) -> Optional[float]:
        """Get span duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary"""
        return {
            'name': self.name,
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'parent_span_id': self.parent_span_id,
            'attributes': self.attributes,
            'events': self.events,
            'status': self.status,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration
        }


class Tracer(ABC):
    """Base tracer interface"""

    @abstractmethod
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Span] = None
    ) -> Span:
        """Start a new span"""
        pass

    @abstractmethod
    def end_span(self, span: Span) -> None:
        """End a span"""
        pass

    def get_spans(self, trace_id: Optional[str] = None) -> List[Span]:
        """Get spans, optionally filtered by trace ID"""
        return []


class SimpleTracer(Tracer):
    """
    Simple in-memory tracer

    Stores spans in memory for testing/development.
    """

    def __init__(self):
        self.spans: list[Span] = []
        self._current_trace_id = 0
        self._current_span_id = 0
        self.logger = logging.getLogger("SimpleTracer")

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Span] = None
    ) -> Span:
        """Start a new span"""
        trace_id = parent.trace_id if parent else self._generate_trace_id()
        span_id = self._generate_span_id()
        parent_span_id = parent.span_id if parent else None

        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            attributes=attributes
        )

        self.logger.debug(f"Started span: {name} (trace={trace_id}, span={span_id})")
        return span

    def end_span(self, span: Span) -> None:
        """End a span"""
        span.finish()
        self.spans.append(span)
        duration = span.duration or 0.0
        self.logger.debug(f"Ended span: {span.name} (duration={duration:.3f}s)")

    def _generate_trace_id(self) -> str:
        """Generate a trace ID"""
        self._current_trace_id += 1
        return f"trace-{self._current_trace_id:016x}"

    def _generate_span_id(self) -> str:
        """Generate a span ID"""
        self._current_span_id += 1
        return f"span-{self._current_span_id:08x}"

    def get_spans(self, trace_id: Optional[str] = None) -> list[Span]:
        """Get all spans, optionally filtered by trace ID"""
        if trace_id:
            return [s for s in self.spans if s.trace_id == trace_id]
        return self.spans

    def clear(self) -> None:
        """Clear all spans"""
        self.spans.clear()


class OpenTelemetryTracer(Tracer):
    """
    OpenTelemetry tracer

    Integrates with OpenTelemetry for real distributed tracing.
    Requires opentelemetry packages.
    """

    def __init__(self, service_name: str = "ia_modules"):
        self.service_name = service_name
        self.logger = logging.getLogger("OpenTelemetryTracer")

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
            from opentelemetry.sdk.resources import Resource

            # Create resource
            resource = Resource(attributes={
                "service.name": self.service_name
            })

            # Set up provider
            provider = TracerProvider(resource=resource)

            # Add console exporter for development
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)

            # Set global tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer
            self._tracer = trace.get_tracer(__name__)

            self.logger.info(f"Initialized OpenTelemetry tracer for {self.service_name}")

        except ImportError:
            raise ImportError(
                "OpenTelemetry packages required. Install with: "
                "pip install opentelemetry-api opentelemetry-sdk"
            )

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Span] = None
    ) -> Span:
        """Start a new span using OpenTelemetry"""
        # Start OpenTelemetry span
        otel_span = self._tracer.start_span(name)

        # Set attributes
        if attributes:
            for key, value in attributes.items():
                otel_span.set_attribute(key, value)

        # Create our wrapper
        span = Span(
            name=name,
            trace_id=f"{otel_span.get_span_context().trace_id:032x}",
            span_id=f"{otel_span.get_span_context().span_id:016x}",
            parent_span_id=None,  # OpenTelemetry handles hierarchy
            attributes=attributes
        )

        # Store OpenTelemetry span
        span._otel_span = otel_span

        return span

    def end_span(self, span: Span) -> None:
        """End an OpenTelemetry span"""
        if hasattr(span, '_otel_span'):
            span._otel_span.end()
        span.finish()


def traced(tracer: Tracer, span_name: Optional[str] = None):
    """
    Decorator to automatically trace a function

    Usage:
        @traced(tracer, "my_operation")
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        name = span_name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            span = tracer.start_span(name)
            try:
                result = await func(*args, **kwargs)
                span.set_status("ok")
                return result
            except Exception as e:
                span.set_status("error", str(e))
                span.set_attribute("error.type", type(e).__name__)
                raise
            finally:
                tracer.end_span(span)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            span = tracer.start_span(name)
            try:
                result = func(*args, **kwargs)
                span.set_status("ok")
                return result
            except Exception as e:
                span.set_status("error", str(e))
                span.set_attribute("error.type", type(e).__name__)
                raise
            finally:
                tracer.end_span(span)

        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def trace_context(tracer: Tracer, name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Context manager for tracing a block of code

    Usage:
        with trace_context(tracer, "database_query") as span:
            result = db.query()
            span.set_attribute("rows", len(result))
    """
    span = tracer.start_span(name, attributes=attributes)
    try:
        yield span
        span.set_status("ok")
    except Exception as e:
        span.set_status("error", str(e))
        span.set_attribute("error.type", type(e).__name__)
        raise
    finally:
        tracer.end_span(span)
