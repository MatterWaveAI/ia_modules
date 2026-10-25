"""
Tests for distributed tracing
"""

import pytest
import asyncio
from ia_modules.telemetry import (
    Span,
    SimpleTracer,
    traced,
    trace_context
)


class TestSpan:
    """Test Span class"""

    def test_span_creation(self):
        """Test creating a span"""
        span = Span(
            name="test_operation",
            trace_id="trace-123",
            span_id="span-456"
        )

        assert span.name == "test_operation"
        assert span.trace_id == "trace-123"
        assert span.span_id == "span-456"
        assert span.status == "unset"

    def test_span_with_parent(self):
        """Test creating a child span"""
        span = Span(
            name="child_op",
            trace_id="trace-123",
            span_id="span-789",
            parent_span_id="span-456"
        )

        assert span.parent_span_id == "span-456"

    def test_set_attribute(self):
        """Test setting span attributes"""
        span = Span("test", "trace-1", "span-1")

        span.set_attribute("http.method", "GET")
        span.set_attribute("http.status_code", 200)

        assert span.attributes["http.method"] == "GET"
        assert span.attributes["http.status_code"] == 200

    def test_add_event(self):
        """Test adding events to span"""
        span = Span("test", "trace-1", "span-1")

        span.add_event("database_query", {"query": "SELECT * FROM users"})
        span.add_event("cache_hit")

        assert len(span.events) == 2
        assert span.events[0]['name'] == "database_query"
        assert span.events[1]['name'] == "cache_hit"

    def test_set_status(self):
        """Test setting span status"""
        span = Span("test", "trace-1", "span-1")

        span.set_status("ok")
        assert span.status == "ok"

        span.set_status("error", "Connection timeout")
        assert span.status == "error"
        assert span.attributes["status.description"] == "Connection timeout"

    def test_span_duration(self):
        """Test span duration calculation"""
        import time

        span = Span("test", "trace-1", "span-1")
        time.sleep(0.01)
        span.finish()

        assert span.duration is not None
        assert span.duration >= 0.01

    def test_span_to_dict(self):
        """Test converting span to dictionary"""
        span = Span(
            name="test",
            trace_id="trace-1",
            span_id="span-1",
            attributes={"key": "value"}
        )
        span.finish()

        data = span.to_dict()

        assert data['name'] == "test"
        assert data['trace_id'] == "trace-1"
        assert data['span_id'] == "span-1"
        assert data['attributes'] == {"key": "value"}
        assert 'duration' in data


class TestSimpleTracer:
    """Test SimpleTracer"""

    def test_tracer_creation(self):
        """Test creating a tracer"""
        tracer = SimpleTracer()
        assert tracer is not None
        assert len(tracer.spans) == 0

    def test_start_end_span(self):
        """Test starting and ending a span"""
        tracer = SimpleTracer()

        span = tracer.start_span("operation")
        assert span.name == "operation"
        assert span.trace_id.startswith("trace-")
        assert span.span_id.startswith("span-")

        tracer.end_span(span)

        assert len(tracer.spans) == 1
        assert tracer.spans[0].duration is not None

    def test_nested_spans(self):
        """Test nested/child spans"""
        tracer = SimpleTracer()

        parent = tracer.start_span("parent_operation")
        child = tracer.start_span("child_operation", parent=parent)

        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id

        tracer.end_span(child)
        tracer.end_span(parent)

        assert len(tracer.spans) == 2

    def test_span_with_attributes(self):
        """Test span with initial attributes"""
        tracer = SimpleTracer()

        span = tracer.start_span(
            "http_request",
            attributes={"method": "GET", "url": "/api/users"}
        )

        assert span.attributes["method"] == "GET"
        assert span.attributes["url"] == "/api/users"

        tracer.end_span(span)

    def test_get_spans_by_trace_id(self):
        """Test filtering spans by trace ID"""
        tracer = SimpleTracer()

        span1 = tracer.start_span("op1")
        span2 = tracer.start_span("op2", parent=span1)
        span3 = tracer.start_span("op3")  # Different trace

        tracer.end_span(span1)
        tracer.end_span(span2)
        tracer.end_span(span3)

        trace1_spans = tracer.get_spans(span1.trace_id)
        assert len(trace1_spans) == 2

    def test_clear_spans(self):
        """Test clearing all spans"""
        tracer = SimpleTracer()

        span = tracer.start_span("op")
        tracer.end_span(span)

        assert len(tracer.spans) == 1

        tracer.clear()
        assert len(tracer.spans) == 0


class TestTracedDecorator:
    """Test @traced decorator"""

    @pytest.mark.asyncio
    async def test_trace_async_function(self):
        """Test tracing async function"""
        tracer = SimpleTracer()

        @traced(tracer, "async_operation")
        async def async_func():
            await asyncio.sleep(0.01)
            return "result"

        result = await async_func()

        assert result == "result"
        assert len(tracer.spans) == 1
        assert tracer.spans[0].name == "async_operation"
        assert tracer.spans[0].status == "ok"

    def test_trace_sync_function(self):
        """Test tracing sync function"""
        tracer = SimpleTracer()

        @traced(tracer, "sync_operation")
        def sync_func():
            return "result"

        result = sync_func()

        assert result == "result"
        assert len(tracer.spans) == 1
        assert tracer.spans[0].name == "sync_operation"
        assert tracer.spans[0].status == "ok"

    @pytest.mark.asyncio
    async def test_trace_function_with_error(self):
        """Test tracing function that raises error"""
        tracer = SimpleTracer()

        @traced(tracer, "failing_operation")
        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await failing_func()

        assert len(tracer.spans) == 1
        assert tracer.spans[0].status == "error"
        assert tracer.spans[0].attributes["error.type"] == "ValueError"

    def test_trace_without_explicit_name(self):
        """Test decorator uses function name if not specified"""
        tracer = SimpleTracer()

        @traced(tracer)
        def my_function():
            return "ok"

        my_function()

        assert tracer.spans[0].name == "my_function"


class TestTraceContext:
    """Test trace_context context manager"""

    def test_basic_context(self):
        """Test basic context manager usage"""
        tracer = SimpleTracer()

        with trace_context(tracer, "database_query") as span:
            assert span.name == "database_query"
            span.set_attribute("rows", 100)

        assert len(tracer.spans) == 1
        assert tracer.spans[0].status == "ok"
        assert tracer.spans[0].attributes["rows"] == 100

    def test_context_with_error(self):
        """Test context manager with error"""
        tracer = SimpleTracer()

        with pytest.raises(ValueError):
            with trace_context(tracer, "failing_query") as span:
                span.set_attribute("query", "SELECT *")
                raise ValueError("Query failed")

        assert len(tracer.spans) == 1
        assert tracer.spans[0].status == "error"
        assert tracer.spans[0].attributes["error.type"] == "ValueError"

    def test_context_with_attributes(self):
        """Test context manager with initial attributes"""
        tracer = SimpleTracer()

        with trace_context(
            tracer,
            "api_call",
            attributes={"endpoint": "/users", "method": "GET"}
        ) as span:
            span.set_attribute("status_code", 200)

        span_data = tracer.spans[0]
        assert span_data.attributes["endpoint"] == "/users"
        assert span_data.attributes["method"] == "GET"
        assert span_data.attributes["status_code"] == 200


class TestRealWorldScenario:
    """Test real-world tracing scenarios"""

    @pytest.mark.asyncio
    async def test_multi_level_trace(self):
        """Test tracing nested operations"""
        tracer = SimpleTracer()

        @traced(tracer, "fetch_user_data")
        async def fetch_user_data(user_id):
            # Simulate database query
            with trace_context(tracer, "database_query") as span:
                span.set_attribute("table", "users")
                span.set_attribute("user_id", user_id)
                await asyncio.sleep(0.01)

            # Simulate cache update
            with trace_context(tracer, "cache_update") as span:
                span.set_attribute("key", f"user:{user_id}")
                await asyncio.sleep(0.005)

            return {"id": user_id, "name": "Test User"}

        result = await fetch_user_data(123)

        assert result["id"] == 123
        assert len(tracer.spans) == 3  # fetch + db_query + cache

        # Each span gets its own trace (independent operations)
        trace_ids = [s.trace_id for s in tracer.spans]
        assert len(trace_ids) == 3  # Three independent traces

    def test_pipeline_execution_trace(self):
        """Test tracing a simple pipeline execution"""
        tracer = SimpleTracer()

        with trace_context(tracer, "pipeline_execution") as pipeline_span:
            pipeline_span.set_attribute("pipeline.name", "data_processing")

            # Step 1: Fetch data
            with trace_context(tracer, "step_fetch_data") as step_span:
                step_span.set_attribute("step.name", "fetch_data")
                step_span.add_event("data_fetched", {"rows": 1000})

            # Step 2: Transform data
            with trace_context(tracer, "step_transform") as step_span:
                step_span.set_attribute("step.name", "transform")
                step_span.add_event("transform_complete")

            # Step 3: Store data
            with trace_context(tracer, "step_store") as step_span:
                step_span.set_attribute("step.name", "store")
                step_span.add_event("stored", {"destination": "database"})

        assert len(tracer.spans) == 4  # pipeline + 3 steps

        # Verify pipeline span
        pipeline = tracer.spans[-1]
        assert pipeline.name == "pipeline_execution"
        assert pipeline.attributes["pipeline.name"] == "data_processing"
