"""
Integration Tests for Pattern Service with LLM Monitoring

Tests that pattern service correctly integrates with monitoring for
rate limiting, cost tracking, and usage statistics.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, MagicMock


def _make_llm_result(text: str):
    """Build an object mimicking LLMCallResult with .text attribute."""
    return SimpleNamespace(text=text, job_id=None, event_count=0)


def _mock_llm_call_side_effect(system_prompt: str, user_message: str, **kwargs):
    """Return canned LLMCallResult based on the system_prompt content.

    Uses distinctive phrases from each pattern's prompt to avoid ambiguity.
    """
    prompt_lower = (system_prompt + " " + user_message).lower()
    # Reflection: critique step
    if "critical evaluator" in prompt_lower:
        return _make_llm_result(
            "The output is acceptable. Clarity is good. The content is complete."
        )
    # Reflection: improvement step
    if "expert editor" in prompt_lower:
        return _make_llm_result(
            "This is an improved version with better clarity and completeness."
        )
    # Tool use: analyze and select tools
    if "available tools" in prompt_lower:
        return _make_llm_result(
            '{"analysis": {"task_type": "test", "required_capabilities": ["search"], "complexity": "low"}, '
            '"selected_tools": [{"tool": "search", "reasoning": "needed", "priority": 1}], '
            '"execution_plan": [{"step": 1, "tool": "search", "action": "search", "input": "query", "output": "results"}], '
            '"reasoning": "search is best"}'
        )
    # Planning: goal decomposition
    if "break down this goal" in prompt_lower:
        return _make_llm_result(
            '[{"description": "Step 1", "reasoning": "Important", "duration": 30, '
            '"dependencies": [], "success_criteria": ["Done"]}]'
        )
    # RAG: query refinement
    if "refining search queries" in prompt_lower:
        return _make_llm_result("refined search query with better keywords")
    # RAG: document evaluation
    if "evaluating document relevance" in prompt_lower:
        return _make_llm_result(
            '{"document_scores": [{"document_number": 1, "title": "Doc 1", '
            '"relevance_score": 0.9, "reasoning": "relevant"}], '
            '"average_relevance": 0.9, "reasoning": "good results", '
            '"refinement_suggestion": "none needed"}'
        )
    # Metacognition: performance analysis
    if "analyzing your own performance" in prompt_lower:
        return _make_llm_result(
            '{"assessment": {"overall_score": 0.8, "summary": "Good", '
            '"strengths": ["fast"], "weaknesses": ["none"]}, '
            '"patterns": ["consistent"], "issues": [], '
            '"adjustments": ["none needed"], "confidence": 0.9}'
        )
    return _make_llm_result("Mock response for the given prompt")


def _make_mock_container():
    """Build a minimal mock container that satisfies PatternService.__init__."""
    container = MagicMock()
    container.reliability_service.metrics.record_workflow = AsyncMock()
    container.reliability_service.metrics.record_step = AsyncMock()
    container.ws_manager.broadcast_patterns = AsyncMock()
    return container


@pytest.fixture
def pattern_service_with_mock():
    """Pattern service with llm_call mocked out."""
    mock_llm = AsyncMock(side_effect=_mock_llm_call_side_effect)
    with patch("backend.services.pattern_service.llm_call", mock_llm):
        from backend.services.pattern_service import PatternService
        container = _make_mock_container()
        service = PatternService(container)
        yield service


class TestPatternServiceMonitoring:
    """Test pattern service monitoring integration"""

    @pytest.mark.asyncio
    async def test_monitored_llm_call_returns_string(self, pattern_service_with_mock):
        """Monitored call returns plain string"""
        service = pattern_service_with_mock

        result = await service._monitored_llm_call(
            system_prompt="Test system prompt",
            user_message="Test user message",
            temperature=0.7,
            max_tokens=1000,
            step_name="test",
        )

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_monitored_call_enforces_rate_limits(self, pattern_service_with_mock):
        """Rate limits are enforced on monitored calls"""
        service = pattern_service_with_mock

        # Exhaust rate limit
        service.monitoring_service.request_limiter.tokens = 0

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service._monitored_llm_call(
                system_prompt="Test",
                user_message="Test",
                temperature=0.7,
                max_tokens=1000,
                step_name="test",
            )

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_reflection_pattern_tracks_requests(self, pattern_service_with_mock):
        """Reflection pattern execution tracks request count"""
        service = pattern_service_with_mock

        await service.reflection_example(
            initial_output="This is a test output that needs improvement.",
            criteria={
                "clarity": "Text should be clear and easy to understand",
                "completeness": "All key points should be covered"
            },
            max_iterations=2
        )

        stats = service.monitoring_service.get_stats()
        assert stats["total_requests"] > 0

    @pytest.mark.asyncio
    async def test_multiple_calls_accumulate_requests(self, pattern_service_with_mock):
        """Multiple calls accumulate request counts"""
        service = pattern_service_with_mock

        for _ in range(3):
            await service._monitored_llm_call(
                system_prompt="Test",
                user_message="Test",
                temperature=0.7,
                max_tokens=500,
                step_name="test",
            )

        stats = service.monitoring_service.get_stats()
        assert stats["total_requests"] == 3


class TestPatternServiceWithAdapter:
    """Test pattern service with adapter integration"""

    @pytest.mark.asyncio
    async def test_reflection_produces_result(self, pattern_service_with_mock):
        """Reflection pattern produces valid result structure"""
        service = pattern_service_with_mock

        result = await service.reflection_example(
            initial_output="Test output",
            criteria={"clarity": "Must be clear"},
            max_iterations=1
        )

        assert result["pattern"] == "reflection"
        assert "final_output" in result
        assert "iterations" in result
        assert result["total_iterations"] >= 1

    @pytest.mark.asyncio
    async def test_planning_produces_result(self, pattern_service_with_mock):
        """Planning pattern produces valid result structure"""
        service = pattern_service_with_mock

        result = await service.planning_example(
            goal="Research machine learning"
        )

        assert result["pattern"] == "planning"
        assert "plan" in result

    @pytest.mark.asyncio
    async def test_tool_use_produces_result(self, pattern_service_with_mock):
        """Tool use pattern produces valid result structure"""
        service = pattern_service_with_mock

        result = await service.tool_use_example(
            task="Search for information",
            available_tools=["search", "calculator"]
        )

        assert result["pattern"] == "tool_use"
        assert "selected_tools" in result
        assert "execution_plan" in result

    @pytest.mark.asyncio
    async def test_metacognition_produces_result(self, pattern_service_with_mock):
        """Metacognition pattern produces valid result structure"""
        service = pattern_service_with_mock

        result = await service.metacognition_example(
            execution_trace=[{"action": "search", "status": "ok"}],
            performance_metrics={"accuracy": 0.85, "speed": 0.9}
        )

        assert result["pattern"] == "metacognition"
        assert "performance_assessment" in result
        assert "strategy_adjustments" in result


class TestAPIEndpoints:
    """Test API endpoint functions call through to PatternService correctly"""

    @pytest.mark.asyncio
    async def test_run_reflection_endpoint(self):
        """run_reflection delegates to PatternService.reflection_example"""
        from backend.api.patterns import run_reflection, ReflectionRequest

        mock_service = AsyncMock()
        mock_service.reflection_example.return_value = {"pattern": "reflection"}

        mock_request = MagicMock()
        mock_request.app.state.services.pattern_service = mock_service

        body = ReflectionRequest(
            initial_output="test",
            criteria={"clarity": "be clear"},
        )
        result = await run_reflection(body, mock_request)
        assert result == {"pattern": "reflection"}
        mock_service.reflection_example.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_planning_endpoint(self):
        """run_planning delegates to PatternService.planning_example"""
        from backend.api.patterns import run_planning, PlanningRequest

        mock_service = AsyncMock()
        mock_service.planning_example.return_value = {"pattern": "planning"}

        mock_request = MagicMock()
        mock_request.app.state.services.pattern_service = mock_service

        body = PlanningRequest(goal="build a house")
        result = await run_planning(body, mock_request)
        assert result == {"pattern": "planning"}
        mock_service.planning_example.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_agentic_rag_endpoint(self):
        """run_agentic_rag delegates to PatternService.agentic_rag_example"""
        from backend.api.patterns import run_agentic_rag, AgenticRAGRequest

        mock_service = AsyncMock()
        mock_service.agentic_rag_example.return_value = {"pattern": "agentic_rag"}

        mock_request = MagicMock()
        mock_request.app.state.services.pattern_service = mock_service

        body = AgenticRAGRequest(query="machine learning basics")
        result = await run_agentic_rag(body, mock_request)
        assert result == {"pattern": "agentic_rag"}
        mock_service.agentic_rag_example.assert_awaited_once()


class TestRateLimitingIntegration:
    """Test rate limiting integration"""

    @pytest.mark.asyncio
    async def test_rate_limit_with_retry_after(self, pattern_service_with_mock):
        """Rate limit response includes retry-after header"""
        service = pattern_service_with_mock

        service.monitoring_service.request_limiter.consume(
            service.monitoring_service.request_limiter.capacity
        )

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service._monitored_llm_call(
                system_prompt="Test",
                user_message="Test",
                temperature=0.7,
                max_tokens=1000,
                step_name="test",
            )

        assert "Retry-After" in exc_info.value.headers
        retry_after = int(exc_info.value.headers["Retry-After"])
        assert retry_after >= 0


class TestCostCalculationIntegration:
    """Test cost calculation integration"""

    @pytest.mark.asyncio
    async def test_different_providers_different_costs(self):
        """Different providers calculate different costs"""
        from backend.services.llm_monitoring_service import CostCalculator

        tokens = {"input": 1000, "output": 500}

        openai_cost = CostCalculator.calculate_cost(
            "openai", "gpt-4o", tokens["input"], tokens["output"]
        )

        anthropic_cost = CostCalculator.calculate_cost(
            "anthropic", "claude-3-5-sonnet-20241022", tokens["input"], tokens["output"]
        )

        gemini_cost = CostCalculator.calculate_cost(
            "google", "gemini-2.5-flash", tokens["input"], tokens["output"]
        )

        assert openai_cost != anthropic_cost
        assert anthropic_cost != gemini_cost
        assert openai_cost != gemini_cost

        # Gemini Flash should be cheapest
        assert gemini_cost < openai_cost
        assert gemini_cost < anthropic_cost


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
