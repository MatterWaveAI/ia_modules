"""
Pattern Service — agentic design patterns using the unified Step primitives.

Patterns Implemented:
1. Reflection: Self-critique and iterative improvement
2. Planning: Multi-step goal decomposition
3. Tool Use: Dynamic capability selection
4. Agentic RAG: Query refinement and relevance evaluation
5. Metacognition: Self-monitoring and strategy adjustment

Each pattern uses LLMStep (via llm_call) for LLM interactions,
the same primitive used by the collaboration patterns and pipeline editor.
"""

from typing import Awaitable, Callable, Dict, List, Any, Optional
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
from functools import wraps
import json
import logging
import re
import time
import uuid

from .llm_config import llm_call
from .llm_monitoring_service import LLMMonitoringService

logger = logging.getLogger(__name__)

WSCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class _WorkflowTracker:
    """Per-request counter for one in-flight pattern run.

    Carried on a ContextVar so concurrent pattern runs on the same
    PatternService singleton don't corrupt each other's step counts.
    """
    __slots__ = ("workflow_id", "step_count", "success")

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.step_count = 0
        self.success = True


_current_tracker: ContextVar[Optional[_WorkflowTracker]] = ContextVar(
    "pattern_service_current_tracker", default=None
)


def _tracked(pattern: str):
    """Decorator — wrap a pattern_example method in a reliability workflow.

    Records one workflow row per invocation with the true LLM step count,
    isolated per async task via ContextVar.
    """
    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, *args, **kwargs):
            async with self._track_workflow(pattern):
                return await fn(self, *args, **kwargs)
        return wrapper
    return decorator


def _parse_json_response(text: str) -> Any:
    """Extract and parse JSON from an agent's text response.

    Handles responses that wrap JSON in markdown code fences or include
    surrounding prose.
    """
    if not text:
        return {}

    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code fence
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first [ or { and parse from there
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        start = text.find(start_char)
        if start >= 0:
            end = text.rfind(end_char)
            if end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

    return {}


class PatternService:
    """Service for demonstrating agentic design patterns."""

    def __init__(self, container):
        """Resolve all deps from the ServiceContainer — no caller boilerplate.

        container must already have ws_manager and reliability_service set
        (done in main.py lifespan).
        """
        self.monitoring_service = LLMMonitoringService()
        self.reliability_metrics = container.reliability_service.metrics
        self.ws_callback: WSCallback = container.ws_manager.broadcast_patterns

    @asynccontextmanager
    async def _track_workflow(self, pattern: str):
        """Record a pattern run as one reliability workflow.

        Tracker is bound to the current async task via ContextVar so
        concurrent pattern runs on the singleton don't contaminate each
        other's step counts.
        """
        workflow_id = f"patterns-{pattern}-{uuid.uuid4().hex[:8]}"
        tracker = _WorkflowTracker(workflow_id)
        token = _current_tracker.set(tracker)
        try:
            yield workflow_id
        except BaseException:
            tracker.success = False
            raise
        finally:
            _current_tracker.reset(token)
            try:
                await self.reliability_metrics.record_workflow(
                    workflow_id=workflow_id,
                    steps=tracker.step_count,
                    retries=0,
                    success=tracker.success,
                )
            except Exception as e:
                logger.error(f"record_workflow failed for {workflow_id}: {e}")

    async def _emit(self, pattern: str, event: str, **data: Any) -> None:
        """Broadcast a pattern lifecycle event over the WebSocket."""
        try:
            await self.ws_callback({
                "type": "pattern_event",
                "pattern": pattern,
                "event": event,
                "timestamp": datetime.now(UTC).isoformat(),
                **data,
            })
        except Exception as e:
            logger.error(f"ws_callback failed for pattern={pattern} event={event}: {e}")

    async def _monitored_llm_call(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        step_name: str = "pattern",
    ) -> str:
        """Make an LLM call via LLMStep with rate limiting and duration tracking.

        Returns plain text response string.
        Raises HTTPException if rate limited.
        """
        from fastapi import HTTPException

        # Check rate limits
        rate_check = self.monitoring_service.check_rate_limits(max_tokens)
        if not rate_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {rate_check['reason']}",
                headers={"Retry-After": str(int(rate_check["retry_after"]))}
            )

        # Make LLM call via LLMStep and track time
        start_time = time.time()
        try:
            result = await llm_call(
                system_prompt=system_prompt,
                user_message=user_message,
                step_name=step_name,
            )
        except Exception:
            await self.reliability_metrics.record_step(agent=step_name, success=False)
            raise
        duration = time.time() - start_time

        # Track usage
        self.monitoring_service.track_usage(
            provider="llm_step",
            model="cli_agent",
            input_tokens=0,
            output_tokens=0,
            duration_seconds=duration
        )

        await self.reliability_metrics.record_step(agent=step_name, success=True)
        tracker = _current_tracker.get()
        if tracker is not None:
            tracker.step_count += 1
        return result.text or ""

    # ==================== REFLECTION PATTERN ====================

    @_tracked("reflection")
    async def reflection_example(
        self,
        initial_output: str,
        criteria: Dict[str, str],
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """Demonstrate reflection pattern with self-critique and iterative improvement."""
        await self._emit("reflection", "started", initial_output=initial_output, max_iterations=max_iterations)
        iterations = []
        current_output = initial_output

        for i in range(max_iterations):
            await self._emit("reflection", "iteration_start", iteration=i + 1, output=current_output)
            critique = await self._llm_generate_critique(current_output, criteria)
            quality_score = self._calculate_quality_score(critique, criteria)
            improvements = self._extract_improvements(critique)
            await self._emit(
                "reflection", "critiqued",
                iteration=i + 1,
                quality_score=quality_score,
                improvements=improvements,
                critique=critique,
            )

            iteration_data = {
                "iteration": i + 1,
                "output": current_output,
                "critique": critique,
                "quality_score": quality_score,
                "improvements_suggested": improvements,
                "timestamp": datetime.now(UTC).isoformat()
            }

            iterations.append(iteration_data)

            if quality_score >= 0.85:
                iteration_data["improved_output"] = current_output
                await self._emit("reflection", "converged", iteration=i + 1, quality_score=quality_score)
                break

            current_output = await self._llm_apply_improvements(current_output, improvements, criteria)
            await self._emit("reflection", "improved", iteration=i + 1, new_output=current_output)

        await self._emit("reflection", "completed", total_iterations=len(iterations))
        return {
            "pattern": "reflection",
            "initial_output": initial_output,
            "final_output": current_output,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "final_quality_score": iterations[-1]["quality_score"]
        }

    async def _llm_generate_critique(self, output: str, criteria: Dict[str, str]) -> str:
        """Generate self-critique using LLM."""
        criteria_text = "\n".join([f"- {name}: {desc}" for name, desc in criteria.items()])
        return await self._monitored_llm_call(
            system_prompt=(
                "You are a critical evaluator analyzing text quality. "
                "Provide honest, constructive critique based on the given criteria. "
                "Focus on specific issues and be direct about weaknesses."
            ),
            user_message=(
                f"Evaluate this output against the criteria:\n\n"
                f"OUTPUT TO EVALUATE:\n{output}\n\n"
                f"CRITERIA:\n{criteria_text}\n\n"
                f"Provide a detailed critique addressing each criterion."
            ),
            temperature=0.3,
            step_name="reflection_critique",
        )

    async def _llm_apply_improvements(self, output: str, improvements: List[str], criteria: Dict[str, str]) -> str:
        """Apply improvements to output using LLM."""
        improvements_text = "\n".join([f"- {imp}" for imp in improvements])
        criteria_text = "\n".join([f"- {name}: {desc}" for name, desc in criteria.items()])
        result = await self._monitored_llm_call(
            system_prompt=(
                "You are an expert editor improving text quality. "
                "Apply the suggested improvements while maintaining the core message. "
                "Provide the improved version directly, without explanations."
            ),
            user_message=(
                f"CURRENT OUTPUT:\n{output}\n\n"
                f"IMPROVEMENTS TO APPLY:\n{improvements_text}\n\n"
                f"CRITERIA TO MEET:\n{criteria_text}"
            ),
            temperature=0.7,
            step_name="reflection_improve",
        )
        return result.strip()

    def _calculate_quality_score(self, critique: str, criteria: Dict) -> float:
        """Calculate quality score from critique."""
        negative_words = ["too brief", "unclear", "incomplete", "uncertainty", "missing",
                          "lacks", "weak", "poor", "insufficient", "vague"]
        positive_words = ["acceptable", "accurate", "complete", "clear", "good",
                          "strong", "excellent", "thorough", "well"]

        negative_count = sum(1 for word in negative_words if word in critique.lower())
        positive_count = sum(1 for word in positive_words if word in critique.lower())

        total_criteria = max(len(criteria), 1)
        score = (positive_count - negative_count) / total_criteria
        return max(0.0, min(1.0, 0.5 + score * 0.2))

    def _extract_improvements(self, critique: str) -> List[str]:
        """Extract improvement suggestions from critique."""
        improvements = []
        if "too brief" in critique.lower() or "lacks" in critique.lower():
            improvements.append("Add more detailed explanations")
        if "unclear" in critique.lower() or "vague" in critique.lower():
            improvements.append("Use simpler, clearer language")
        if "incomplete" in critique.lower() or "missing" in critique.lower():
            improvements.append("Cover all aspects of the topic")
        if "uncertainty" in critique.lower():
            improvements.append("Verify facts and remove hedging language")
        if not improvements:
            improvements.append("Refine and polish the content")
        return improvements

    # ==================== PLANNING PATTERN ====================

    @_tracked("planning")
    async def planning_example(
        self,
        goal: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Demonstrate planning pattern with goal decomposition."""
        await self._emit("planning", "started", goal=goal, constraints=constraints or {})
        await self._emit("planning", "decomposing", goal=goal)
        subgoals = await self._llm_decompose_goal(goal, constraints)
        await self._emit("planning", "decomposed", count=len(subgoals))

        steps = []
        for i, subgoal in enumerate(subgoals):
            step = {
                "step_number": i + 1,
                "subgoal": subgoal.get("description", subgoal.get("subgoal", f"Step {i+1}")),
                "reasoning": subgoal.get("reasoning", ""),
                "estimated_duration": subgoal.get("duration", subgoal.get("estimated_duration", 15)),
                "dependencies": subgoal.get("dependencies", []),
                "success_criteria": subgoal.get("success_criteria", [])
            }
            steps.append(step)
            await self._emit("planning", "step", step=step)

        await self._emit("planning", "completed", total_steps=len(steps))
        return {
            "pattern": "planning",
            "goal": goal,
            "constraints": constraints or {},
            "total_steps": len(steps),
            "estimated_total_time": sum(s["estimated_duration"] for s in steps),
            "plan": steps,
            "created_at": datetime.now(UTC).isoformat()
        }

    async def _llm_decompose_goal(self, goal: str, constraints: Optional[Dict]) -> List[Dict]:
        """Decompose goal into actionable steps using LLM."""
        constraints_text = ""
        if constraints:
            constraints_text = "\n".join([f"- {k}: {v}" for k, v in constraints.items()])

        result = await self._monitored_llm_call(
            system_prompt=(
                "You are an expert planner who breaks down complex goals into actionable steps. "
                "Create a detailed, realistic plan with clear dependencies and success criteria."
            ),
            user_message=(
                f"Break down this goal into a step-by-step plan:\n\n"
                f"GOAL: {goal}\n\n"
                + (f"CONSTRAINTS:\n{constraints_text}\n\n" if constraints_text else "")
                + "Create a plan with 3-5 steps. For each step, provide:\n"
                "1. description: What needs to be done\n"
                "2. reasoning: Why this step is important\n"
                "3. duration: Estimated time in minutes\n"
                "4. dependencies: Which previous steps must complete first (use step numbers)\n"
                "5. success_criteria: How to know this step is complete (list of 2-3 criteria)\n\n"
                "Return valid JSON array."
            ),
            temperature=0.5,
            step_name="planning_decompose",
        )

        parsed = _parse_json_response(result)
        if not parsed:
            logger.warning("Planning LLM returned unparseable response: %r", result[:500] if result else result)

        if isinstance(parsed, dict):
            for key in ("steps", "plan"):
                if key in parsed:
                    return parsed[key]
            # LLM may use an unexpected key — grab the first list value
            for v in parsed.values():
                if isinstance(v, list):
                    return v
            return []
        elif isinstance(parsed, list):
            return parsed
        return []

    # ==================== TOOL USE PATTERN ====================

    @_tracked("tool_use")
    async def tool_use_example(
        self,
        task: str,
        available_tools: List[str]
    ) -> Dict[str, Any]:
        """Demonstrate tool use pattern with dynamic tool selection."""
        await self._emit("tool_use", "started", task=task, available_tools=available_tools)
        await self._emit("tool_use", "analyzing", task=task)
        tool_analysis = await self._llm_analyze_and_select_tools(task, available_tools)
        await self._emit(
            "tool_use", "selected",
            selected_tools=tool_analysis.get("selected_tools", []),
            execution_plan=tool_analysis.get("execution_plan", []),
        )
        await self._emit("tool_use", "completed")

        return {
            "pattern": "tool_use",
            "task": task,
            "available_tools": available_tools,
            "analysis": tool_analysis["analysis"],
            "selected_tools": tool_analysis["selected_tools"],
            "execution_plan": tool_analysis["execution_plan"],
            "reasoning": tool_analysis["reasoning"]
        }

    async def _llm_analyze_and_select_tools(
        self,
        task: str,
        available_tools: List[str]
    ) -> Dict[str, Any]:
        """Analyze task and select appropriate tools using LLM."""
        tools_list = ", ".join(available_tools)

        result = await self._monitored_llm_call(
            system_prompt="You are an expert task analyzer selecting the right tools for a job.",
            user_message=(
                f"TASK: {task}\n\n"
                f"AVAILABLE TOOLS: {tools_list}\n\n"
                f"Analyze the task and select the most appropriate tools. Return valid JSON:\n"
                f'{{"analysis": {{"task_type": "...", "required_capabilities": [...], "complexity": "low/medium/high"}}, '
                f'"selected_tools": [{{"tool": "...", "reasoning": "...", "priority": 1}}], '
                f'"execution_plan": [{{"step": 1, "tool": "...", "action": "...", "input": "...", "output": "..."}}], '
                f'"reasoning": "overall strategy"}}'
            ),
            temperature=0.5,
            step_name="tool_use_analyze",
        )

        parsed = _parse_json_response(result)
        if not isinstance(parsed, dict):
            parsed = {}

        return {
            "analysis": parsed.get("analysis", {}),
            "selected_tools": parsed.get("selected_tools", []),
            "execution_plan": parsed.get("execution_plan", []),
            "reasoning": parsed.get("reasoning", "")
        }

    # ==================== AGENTIC RAG PATTERN ====================

    @_tracked("agentic_rag")
    async def agentic_rag_example(
        self,
        initial_query: str,
        max_refinements: int = 3
    ) -> Dict[str, Any]:
        """Demonstrate agentic RAG with query refinement."""
        await self._emit("agentic_rag", "started", initial_query=initial_query, max_refinements=max_refinements)
        iterations = []
        current_query = initial_query

        for i in range(max_refinements):
            await self._emit("agentic_rag", "iteration_start", iteration=i + 1, query=current_query)
            documents = self._retrieve_documents(current_query)
            await self._emit("agentic_rag", "retrieved", iteration=i + 1, count=len(documents))

            evaluation = await self._llm_evaluate_documents(current_query, documents)
            await self._emit(
                "agentic_rag", "evaluated",
                iteration=i + 1,
                average_relevance=evaluation["average_relevance"],
                reasoning=evaluation["reasoning"],
            )

            iteration_data = {
                "iteration": i + 1,
                "query": current_query,
                "documents_retrieved": len(documents),
                "average_relevance": evaluation["average_relevance"],
                "documents": evaluation["document_scores"],
                "evaluation_reasoning": evaluation["reasoning"]
            }

            if evaluation["average_relevance"] >= 0.75:
                iterations.append(iteration_data)
                await self._emit("agentic_rag", "converged", iteration=i + 1, relevance=evaluation["average_relevance"])
                break

            refined_query = await self._llm_refine_query(
                current_query, documents, evaluation
            )
            iteration_data["refined_query"] = refined_query
            iteration_data["refinement_reasoning"] = evaluation.get("refinement_suggestion", "")

            iterations.append(iteration_data)
            current_query = refined_query
            await self._emit("agentic_rag", "refined", iteration=i + 1, new_query=refined_query)

        await self._emit("agentic_rag", "completed", total_iterations=len(iterations))
        return {
            "pattern": "agentic_rag",
            "initial_query": initial_query,
            "final_query": current_query,
            "total_iterations": len(iterations),
            "iterations": iterations,
            "final_relevance": iterations[-1]["average_relevance"] if iterations else 0
        }

    async def _llm_evaluate_documents(
        self,
        query: str,
        documents: List[Dict]
    ) -> Dict[str, Any]:
        """Use LLM to evaluate document relevance."""
        docs_text = "\n\n".join([
            f"DOCUMENT {i+1}:\nTitle: {doc['title']}\nContent: {doc['content']}"
            for i, doc in enumerate(documents)
        ])

        result = await self._monitored_llm_call(
            system_prompt="You are an expert at evaluating document relevance for search queries.",
            user_message=(
                f"QUERY: {query}\n\n"
                f"RETRIEVED DOCUMENTS:\n{docs_text}\n\n"
                f"Evaluate each document's relevance to the query. Return valid JSON:\n"
                f'{{"document_scores": [{{"document_number": 1, "title": "...", "relevance_score": 0.0, "reasoning": "..."}}], '
                f'"average_relevance": 0.0, "reasoning": "overall assessment", '
                f'"refinement_suggestion": "how to improve query if needed"}}'
            ),
            temperature=0.3,
            step_name="rag_evaluate",
        )

        parsed = _parse_json_response(result)
        return {
            "document_scores": parsed.get("document_scores", []),
            "average_relevance": parsed.get("average_relevance", 0.5),
            "reasoning": parsed.get("reasoning", ""),
            "refinement_suggestion": parsed.get("refinement_suggestion", "")
        }

    async def _llm_refine_query(
        self,
        original_query: str,
        documents: List[Dict],
        evaluation: Dict[str, Any]
    ) -> str:
        """Use LLM to refine search query based on results."""
        result = await self._monitored_llm_call(
            system_prompt="You are an expert at refining search queries to improve results.",
            user_message=(
                f"ORIGINAL QUERY: {original_query}\n\n"
                f"EVALUATION: {evaluation.get('reasoning', 'Results not satisfactory')}\n\n"
                f"REFINEMENT SUGGESTION: {evaluation.get('refinement_suggestion', 'Make query more specific')}\n\n"
                f"Create an improved search query. Return only the refined query text, no explanation."
            ),
            temperature=0.5,
            step_name="rag_refine",
        )
        return result.strip()

    def _retrieve_documents(self, query: str) -> List[Dict]:
        """Simulate document retrieval (placeholder for real RAG integration)."""
        words = query.split()
        return [
            {
                "title": f"Document about {words[0] if words else 'topic'}",
                "content": f"This document discusses {query}. It provides detailed information about the subject matter."
            },
            {
                "title": f"Research on {words[-1] if len(words) > 1 else 'subject'}",
                "content": f"A comprehensive study examining {query} from multiple perspectives."
            },
            {
                "title": "Related Topic Overview",
                "content": f"While not directly about {query}, this document covers related concepts."
            }
        ][:3]

    # ==================== METACOGNITION PATTERN ====================

    @_tracked("metacognition")
    async def metacognition_example(
        self,
        execution_trace: List[Dict],
        performance_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Demonstrate metacognition with self-monitoring."""
        await self._emit(
            "metacognition", "started",
            trace_length=len(execution_trace),
            metrics=performance_metrics,
        )
        await self._emit("metacognition", "analyzing")
        analysis = await self._llm_analyze_performance(execution_trace, performance_metrics)
        await self._emit(
            "metacognition", "analyzed",
            assessment=analysis.get("assessment", {}),
            issues=analysis.get("issues", []),
            adjustments=analysis.get("adjustments", []),
        )
        await self._emit("metacognition", "completed")

        return {
            "pattern": "metacognition",
            "performance_assessment": analysis["assessment"],
            "patterns_detected": analysis["patterns"],
            "issues_identified": analysis["issues"],
            "strategy_adjustments": analysis["adjustments"],
            "confidence_level": analysis.get("confidence", 0.7),
            "timestamp": datetime.now(UTC).isoformat()
        }

    async def _llm_analyze_performance(
        self,
        execution_trace: List[Dict],
        performance_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Use LLM to analyze performance and suggest improvements."""
        trace_text = "\n".join([
            f"Step {i+1}: {step}" for i, step in enumerate(execution_trace)
        ])
        metrics_text = "\n".join([
            f"- {metric}: {value:.2f}" for metric, value in performance_metrics.items()
        ])

        result = await self._monitored_llm_call(
            system_prompt="You are an AI agent analyzing your own performance to improve future execution.",
            user_message=(
                f"EXECUTION TRACE:\n{trace_text}\n\n"
                f"PERFORMANCE METRICS:\n{metrics_text}\n\n"
                f"Perform metacognitive analysis and return valid JSON:\n"
                f'{{"assessment": {{"overall_score": 0.0, "summary": "...", "strengths": [...], "weaknesses": [...]}}, '
                f'"patterns": ["..."], '
                f'"issues": [{{"issue": "...", "severity": "low/medium/high", "impact": "..."}}], '
                f'"adjustments": ["..."], '
                f'"confidence": 0.0}}'
            ),
            temperature=0.5,
            step_name="metacognition_analyze",
        )

        parsed = _parse_json_response(result)
        return {
            "assessment": parsed.get("assessment", {}),
            "patterns": parsed.get("patterns", []),
            "issues": parsed.get("issues", []),
            "adjustments": parsed.get("adjustments", []),
            "confidence": parsed.get("confidence", 0.7)
        }
