"""
Tests for PatternService — agentic design patterns using LLMStep.

Tests mock llm_call to avoid real subprocess spawning while verifying
the full pattern logic (iteration, JSON parsing, scoring, etc.).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.pattern_service import PatternService, _parse_json_response
from services.llm_config import LLMCallResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_container():
    """Build a minimal mock container satisfying PatternService.__init__."""
    container = MagicMock()
    container.reliability_service.metrics.record_workflow = AsyncMock()
    container.reliability_service.metrics.record_step = AsyncMock()
    container.ws_manager.broadcast_patterns = AsyncMock()
    return container


def _mock_llm_call(*responses: str):
    """Create a patched llm_call that returns responses in order."""
    call_count = 0

    async def fake_llm_call(system_prompt, user_message, **kwargs):
        nonlocal call_count
        text = responses[call_count] if call_count < len(responses) else "default"
        call_count += 1
        return LLMCallResult(text=text, job_id=f"test-job-{call_count}")

    return patch(
        "services.pattern_service.llm_call",
        side_effect=fake_llm_call,
    )


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_direct_json(self):
        assert _parse_json_response('{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert _parse_json_response(text) == {"a": 1}

    def test_json_array(self):
        assert _parse_json_response('[1, 2, 3]') == [1, 2, 3]

    def test_json_embedded_in_prose(self):
        text = 'Here is the result:\n{"key": "value"}\nDone.'
        assert _parse_json_response(text) == {"key": "value"}

    def test_invalid_json_returns_empty_dict(self):
        assert _parse_json_response("not json at all") == {}

    def test_none_returns_empty_dict(self):
        assert _parse_json_response(None) == {}


# ---------------------------------------------------------------------------
# Reflection Pattern
# ---------------------------------------------------------------------------

class TestReflectionPattern:
    @pytest.mark.asyncio
    async def test_reflection_runs_iterations(self):
        """Reflection should iterate: critique → improve → critique."""
        with _mock_llm_call(
            # Iteration 1: critique (negative words → low score)
            "The output is too brief and unclear. It lacks detail.",
            # Iteration 1: improvement
            "This is a comprehensive and well-structured explanation of the topic.",
            # Iteration 2: critique (positive words → high score)
            "The output is clear, accurate, and complete. Excellent quality.",
        ):
            svc = PatternService(_make_container())
            result = await svc.reflection_example(
                initial_output="AI is useful.",
                criteria={"clarity": "Be clear", "completeness": "Be thorough"},
                max_iterations=3,
            )

        assert result["pattern"] == "reflection"
        assert result["initial_output"] == "AI is useful."
        assert result["total_iterations"] >= 1
        assert len(result["iterations"]) >= 1
        assert 0 <= result["final_quality_score"] <= 1

    @pytest.mark.asyncio
    async def test_reflection_stops_early_on_high_score(self):
        """If first critique is positive enough, stop after 1 iteration."""
        with _mock_llm_call(
            "The output is clear, accurate, complete, thorough, and excellent.",
        ):
            svc = PatternService(_make_container())
            result = await svc.reflection_example(
                initial_output="A very good piece of text.",
                criteria={"quality": "High quality"},
                max_iterations=5,
            )

        assert result["total_iterations"] == 1
        assert result["final_quality_score"] >= 0.85

    @pytest.mark.asyncio
    async def test_reflection_returns_final_output(self):
        """After improvements, final_output should differ from initial."""
        with _mock_llm_call(
            "Too brief, incomplete.",
            "Here is a much improved version with full detail.",
            "Clear, accurate, complete, excellent.",
        ):
            svc = PatternService(_make_container())
            result = await svc.reflection_example(
                initial_output="Short.",
                criteria={"quality": "High"},
                max_iterations=3,
            )

        assert result["final_output"] != "Short."


# ---------------------------------------------------------------------------
# Planning Pattern
# ---------------------------------------------------------------------------

class TestPlanningPattern:
    @pytest.mark.asyncio
    async def test_planning_returns_steps(self):
        """Planning should parse LLM JSON into structured steps."""
        plan_json = json.dumps([
            {
                "description": "Research the topic",
                "reasoning": "Need background info",
                "duration": 30,
                "dependencies": [],
                "success_criteria": ["Sources found"]
            },
            {
                "description": "Write the report",
                "reasoning": "Deliver the result",
                "duration": 60,
                "dependencies": [1],
                "success_criteria": ["Report complete"]
            }
        ])
        with _mock_llm_call(plan_json):
            svc = PatternService(_make_container())
            result = await svc.planning_example(
                goal="Write a research report",
                constraints={"time": "2 hours"},
            )

        assert result["pattern"] == "planning"
        assert result["goal"] == "Write a research report"
        assert result["total_steps"] == 2
        assert result["estimated_total_time"] == 90
        assert result["plan"][0]["subgoal"] == "Research the topic"
        assert result["plan"][1]["dependencies"] == [1]

    @pytest.mark.asyncio
    async def test_planning_handles_wrapped_json(self):
        """Planning should handle JSON wrapped in a dict with 'steps' key."""
        plan_json = json.dumps({
            "steps": [
                {"description": "Step one", "reasoning": "R", "duration": 10, "dependencies": [], "success_criteria": ["Done"]}
            ]
        })
        with _mock_llm_call(plan_json):
            svc = PatternService(_make_container())
            result = await svc.planning_example(goal="Do something")

        assert result["total_steps"] == 1

    @pytest.mark.asyncio
    async def test_planning_handles_bad_json(self):
        """Planning should return empty plan on unparseable response."""
        with _mock_llm_call("I can't create a plan right now."):
            svc = PatternService(_make_container())
            result = await svc.planning_example(goal="Do something")

        assert result["total_steps"] == 0
        assert result["plan"] == []


# ---------------------------------------------------------------------------
# Tool Use Pattern
# ---------------------------------------------------------------------------

class TestToolUsePattern:
    @pytest.mark.asyncio
    async def test_tool_use_returns_analysis(self):
        """Tool use should return structured analysis."""
        analysis_json = json.dumps({
            "analysis": {
                "task_type": "research",
                "required_capabilities": ["search", "analysis"],
                "complexity": "medium"
            },
            "selected_tools": [
                {"tool": "web_search", "reasoning": "Need to find info", "priority": 1}
            ],
            "execution_plan": [
                {"step": 1, "tool": "web_search", "action": "Search", "input": "query", "output": "results"}
            ],
            "reasoning": "Search first, then analyze"
        })
        with _mock_llm_call(analysis_json):
            svc = PatternService(_make_container())
            result = await svc.tool_use_example(
                task="Research quantum computing",
                available_tools=["web_search", "calculator", "llm_analyzer"],
            )

        assert result["pattern"] == "tool_use"
        assert result["task"] == "Research quantum computing"
        assert len(result["selected_tools"]) == 1
        assert result["selected_tools"][0]["tool"] == "web_search"
        assert len(result["execution_plan"]) == 1

    @pytest.mark.asyncio
    async def test_tool_use_handles_bad_json(self):
        """Tool use should return empty fields on bad JSON."""
        with _mock_llm_call("Use the search tool and the calculator."):
            svc = PatternService(_make_container())
            result = await svc.tool_use_example(
                task="Calculate something",
                available_tools=["calculator"],
            )

        assert result["analysis"] == {}
        assert result["selected_tools"] == []


# ---------------------------------------------------------------------------
# Agentic RAG Pattern
# ---------------------------------------------------------------------------

class TestAgenticRAGPattern:
    @pytest.mark.asyncio
    async def test_rag_iterates_on_low_relevance(self):
        """RAG should refine query when relevance is low."""
        eval_low = json.dumps({
            "document_scores": [{"document_number": 1, "title": "Doc 1", "relevance_score": 0.3, "reasoning": "Low match"}],
            "average_relevance": 0.3,
            "reasoning": "Poor match",
            "refinement_suggestion": "Be more specific"
        })
        eval_high = json.dumps({
            "document_scores": [{"document_number": 1, "title": "Doc 1", "relevance_score": 0.9, "reasoning": "Great match"}],
            "average_relevance": 0.9,
            "reasoning": "Excellent match",
            "refinement_suggestion": ""
        })
        with _mock_llm_call(
            eval_low,                           # Iteration 1: evaluate
            "machine learning in healthcare",   # Iteration 1: refine
            eval_high,                          # Iteration 2: evaluate (high → stop)
        ):
            svc = PatternService(_make_container())
            result = await svc.agentic_rag_example(
                initial_query="machine learning",
                max_refinements=3,
            )

        assert result["pattern"] == "agentic_rag"
        assert result["total_iterations"] == 2
        assert result["final_relevance"] == 0.9
        assert result["final_query"] == "machine learning in healthcare"

    @pytest.mark.asyncio
    async def test_rag_stops_early_on_high_relevance(self):
        """RAG should stop if first evaluation is high enough."""
        eval_high = json.dumps({
            "document_scores": [],
            "average_relevance": 0.85,
            "reasoning": "Good match",
            "refinement_suggestion": ""
        })
        with _mock_llm_call(eval_high):
            svc = PatternService(_make_container())
            result = await svc.agentic_rag_example(
                initial_query="specific query",
                max_refinements=5,
            )

        assert result["total_iterations"] == 1
        assert result["final_relevance"] >= 0.75


# ---------------------------------------------------------------------------
# Metacognition Pattern
# ---------------------------------------------------------------------------

class TestMetacognitionPattern:
    @pytest.mark.asyncio
    async def test_metacognition_returns_analysis(self):
        """Metacognition should return structured performance analysis."""
        analysis_json = json.dumps({
            "assessment": {
                "overall_score": 0.72,
                "summary": "Generally good with room for improvement",
                "strengths": ["Fast execution"],
                "weaknesses": ["Error handling"]
            },
            "patterns": ["Sequential execution preferred"],
            "issues": [{"issue": "Slow step 3", "severity": "medium", "impact": "30% slower"}],
            "adjustments": ["Add caching for repeated lookups"],
            "confidence": 0.8
        })
        with _mock_llm_call(analysis_json):
            svc = PatternService(_make_container())
            result = await svc.metacognition_example(
                execution_trace=[
                    {"step": "search", "status": "success", "duration": 1.2},
                    {"step": "analyze", "status": "success", "duration": 3.5},
                ],
                performance_metrics={"accuracy": 0.85, "speed": 0.6},
            )

        assert result["pattern"] == "metacognition"
        assert result["performance_assessment"]["overall_score"] == 0.72
        assert len(result["patterns_detected"]) == 1
        assert len(result["issues_identified"]) == 1
        assert result["confidence_level"] == 0.8

    @pytest.mark.asyncio
    async def test_metacognition_handles_bad_json(self):
        """Metacognition should return defaults on bad JSON."""
        with _mock_llm_call("Performance looks okay overall."):
            svc = PatternService(_make_container())
            result = await svc.metacognition_example(
                execution_trace=[],
                performance_metrics={"accuracy": 0.5},
            )

        assert result["performance_assessment"] == {}
        assert result["confidence_level"] == 0.7  # default


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_raises_429(self):
        """Should raise HTTPException 429 when rate limited."""
        from fastapi import HTTPException

        svc = PatternService(_make_container())
        svc.monitoring_service.check_rate_limits = lambda *a: {
            "allowed": False,
            "reason": "Too many requests",
            "retry_after": 30.0,
        }

        with pytest.raises(HTTPException) as exc_info:
            await svc._monitored_llm_call(
                system_prompt="test",
                user_message="test",
            )
        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# API Endpoint Integration
# ---------------------------------------------------------------------------

class TestPatternAPI:
    """Test that API endpoints call the service correctly."""

    @staticmethod
    def _mock_request():
        """Build a mock FastAPI Request whose app.state holds a real PatternService."""
        req = MagicMock()
        req.app.state.services.pattern_service = PatternService(_make_container())
        return req

    @pytest.mark.asyncio
    async def test_reflection_endpoint(self):
        from api.patterns import run_reflection, ReflectionRequest

        with _mock_llm_call(
            "Clear, accurate, complete, excellent quality.",
        ):
            body = ReflectionRequest(
                initial_output="Test text",
                criteria={"quality": "High"},
                max_iterations=1,
            )
            result = await run_reflection(body, self._mock_request())

        assert result["pattern"] == "reflection"
        assert result["total_iterations"] == 1

    @pytest.mark.asyncio
    async def test_planning_endpoint(self):
        from api.patterns import run_planning, PlanningRequest

        plan_json = json.dumps([
            {"description": "Step 1", "reasoning": "R", "duration": 10, "dependencies": [], "success_criteria": ["Done"]}
        ])
        with _mock_llm_call(plan_json):
            body = PlanningRequest(goal="Build something")
            result = await run_planning(body, self._mock_request())

        assert result["pattern"] == "planning"
        assert result["total_steps"] == 1

    @pytest.mark.asyncio
    async def test_agentic_rag_endpoint(self):
        from api.patterns import run_agentic_rag, AgenticRAGRequest

        eval_json = json.dumps({
            "document_scores": [],
            "average_relevance": 0.9,
            "reasoning": "Good",
            "refinement_suggestion": ""
        })
        with _mock_llm_call(eval_json):
            body = AgenticRAGRequest(query="test query")
            result = await run_agentic_rag(body, self._mock_request())

        assert result["pattern"] == "agentic_rag"
        assert result["final_relevance"] >= 0.75


import json  # noqa: E402 — needed for test data construction
