"""
Advanced Routing System for Phase 3 Implementation

Implements agent-based conditions, function-based conditions, and parallel execution
for complex pipeline routing and flow control.
"""

import asyncio
import importlib
import inspect
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from .core import TemplateParameterResolver


@dataclass
class RoutingContext:
    """Context for routing decisions"""
    pipeline_data: Dict[str, Any]
    step_results: Dict[str, Any]
    current_step_id: str
    execution_id: str
    metadata: Optional[Dict[str, Any]] = None


class ConditionEvaluator(ABC):
    """Abstract base class for condition evaluators"""

    @abstractmethod
    async def evaluate(self, context: RoutingContext) -> bool:
        """Evaluate the condition and return True/False"""
        pass


class AgentConditionEvaluator(ConditionEvaluator):
    """AI Agent-based condition evaluator"""

    def __init__(self,
                 model: str,
                 prompt_template: str,
                 context_fields: Optional[List[str]] = None,
                 expected_outputs: Optional[List[str]] = None,
                 confidence_threshold: float = 0.7,
                 max_retries: int = 2):
        self.model = model
        self.prompt_template = prompt_template
        self.context_fields = context_fields or []
        self.expected_outputs = expected_outputs or ["yes", "no", "true", "false"]
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

    async def evaluate(self, context: RoutingContext) -> bool:
        """Evaluate condition using AI agent"""
        try:
            # Build context for agent
            agent_context = self._build_agent_context(context)

            # Format prompt with context
            prompt = self._format_prompt(agent_context)

            # Call AI model (this would integrate with actual AI services)
            response = await self._call_ai_model(prompt)

            # Parse response
            return self._parse_agent_response(response)

        except Exception as e:
            raise RuntimeError(f"Agent condition evaluation failed: {str(e)}")

    def _build_agent_context(self, context: RoutingContext) -> Dict[str, Any]:
        """Build context data for AI agent"""
        agent_context = {
            "current_step": context.current_step_id,
            "execution_id": context.execution_id,
            "timestamp": datetime.now().isoformat()
        }

        # Include specified context fields
        for field in self.context_fields:
            if field in context.pipeline_data:
                agent_context[field] = context.pipeline_data[field]
            elif field in context.step_results:
                agent_context[field] = context.step_results[field]

        # Include all step results if no specific fields requested
        if not self.context_fields:
            agent_context["step_results"] = context.step_results
            agent_context["pipeline_data"] = context.pipeline_data

        return agent_context

    def _format_prompt(self, agent_context: Dict[str, Any]) -> str:
        """Format prompt template with context"""
        return TemplateParameterResolver.resolve_string_template(
            self.prompt_template,
            {"context": agent_context}
        )

    async def _call_ai_model(self, prompt: str) -> Dict[str, Any]:
        """Call AI model - placeholder for actual implementation"""
        # This would integrate with OpenAI, Anthropic, or other AI services
        # For now, return a mock response
        await asyncio.sleep(0.1)  # Simulate API call

        # Mock response based on prompt content
        if "error" in prompt.lower() or "fail" in prompt.lower():
            return {
                "response": "no",
                "confidence": 0.9,
                "reasoning": "Detected error or failure condition"
            }
        else:
            return {
                "response": "yes",
                "confidence": 0.8,
                "reasoning": "Conditions appear favorable"
            }

    def _parse_agent_response(self, response: Dict[str, Any]) -> bool:
        """Parse agent response to boolean"""
        agent_response = response.get("response", "").lower()
        confidence = response.get("confidence", 0.0)

        # Check confidence threshold
        if confidence < self.confidence_threshold:
            raise ValueError(f"Agent confidence {confidence} below threshold {self.confidence_threshold}")

        # Parse response
        if agent_response in ["yes", "true", "1", "proceed", "continue"]:
            return True
        elif agent_response in ["no", "false", "0", "stop", "halt"]:
            return False
        else:
            raise ValueError(f"Unexpected agent response: {agent_response}")


class FunctionConditionEvaluator(ConditionEvaluator):
    """Function-based condition evaluator"""

    def __init__(self,
                 function_name: str,
                 module_path: str,
                 parameters: Dict[str, Any] = None,
                 timeout_seconds: int = 30):
        self.function_name = function_name
        self.module_path = module_path
        self.parameters = parameters or {}
        self.timeout_seconds = timeout_seconds
        self._function = None

    async def evaluate(self, context: RoutingContext) -> bool:
        """Evaluate condition using custom function"""
        try:
            if self._function is None:
                self._function = self._load_function()

            # Prepare function arguments
            args = self._prepare_arguments(context)

            # Execute function with timeout
            result = await self._execute_with_timeout(self._function, args)

            # Ensure boolean result
            return bool(result)

        except Exception as e:
            raise RuntimeError(f"Function condition evaluation failed: {str(e)}")

    def _load_function(self) -> Callable:
        """Load and validate the condition function"""
        try:
            module = importlib.import_module(self.module_path)
            function = getattr(module, self.function_name)

            # Validate function signature
            sig = inspect.signature(function)
            expected_params = ["context", "parameters"]

            if not all(param in sig.parameters for param in expected_params):
                raise ValueError(f"Function must accept parameters: {expected_params}")

            return function

        except ImportError as e:
            raise ImportError(f"Cannot import module {self.module_path}: {str(e)}")
        except AttributeError:
            raise AttributeError(f"Function {self.function_name} not found in {self.module_path}")

    def _prepare_arguments(self, context: RoutingContext) -> Dict[str, Any]:
        """Prepare arguments for function call"""
        return {
            "context": context,
            "parameters": self.parameters
        }

    async def _execute_with_timeout(self, function: Callable, args: Dict[str, Any]) -> Any:
        """Execute function with timeout"""
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                future = loop.run_in_executor(executor, lambda: function(**args))
                result = await asyncio.wait_for(future, timeout=self.timeout_seconds)
                return result
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function execution timed out after {self.timeout_seconds}s")


class ExpressionConditionEvaluator(ConditionEvaluator):
    """Expression-based condition evaluator"""

    def __init__(self, source: str, operator: str, value: Any):
        self.source = source
        self.operator = operator
        self.value = value

    async def evaluate(self, context: RoutingContext) -> bool:
        """Evaluate simple expression condition"""
        try:
            # Extract value from context
            actual_value = self._extract_value(context)

            # Perform comparison
            return self._compare_values(actual_value, self.operator, self.value)

        except (ValueError, KeyError):
            # Re-raise these exceptions without wrapping (for testing)
            raise
        except Exception as e:
            raise RuntimeError(f"Expression condition evaluation failed: {str(e)}")

    def _extract_value(self, context: RoutingContext) -> Any:
        """Extract value from context using path notation"""
        path_parts = self.source.split('.')

        # Start with step results or pipeline data
        if path_parts[0] == "step_results":
            data = context.step_results
            path_parts = path_parts[1:]
        elif path_parts[0] == "pipeline_data":
            data = context.pipeline_data
            path_parts = path_parts[1:]
        else:
            # Try step results first, then pipeline data
            if self.source in context.step_results:
                return context.step_results[self.source]
            elif self.source in context.pipeline_data:
                return context.pipeline_data[self.source]
            else:
                raise KeyError(f"Path {self.source} not found in context")

        # Navigate nested path
        for part in path_parts:
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                raise KeyError(f"Path {self.source} not found in context")

        return data

    def _compare_values(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare values using specified operator"""
        operators = {
            "==": lambda a, e: a == e,
            "!=": lambda a, e: a != e,
            ">": lambda a, e: a > e,
            ">=": lambda a, e: a >= e,
            "<": lambda a, e: a < e,
            "<=": lambda a, e: a <= e,
            "in": lambda a, e: a in e,
            "not_in": lambda a, e: a not in e,
            "contains": lambda a, e: e in a,
            "startswith": lambda a, e: str(a).startswith(str(e)),
            "endswith": lambda a, e: str(a).endswith(str(e)),
            "regex": lambda a, e: bool(__import__('re').match(e, str(a)))
        }

        if operator not in operators:
            raise ValueError(f"Unsupported operator: {operator}")

        return operators[operator](actual, expected)


class AdvancedRouter:
    """Advanced routing system for Phase 3"""

    def __init__(self):
        self.evaluators = {
            "expression": ExpressionConditionEvaluator,
            "agent": AgentConditionEvaluator,
            "function": FunctionConditionEvaluator
        }

    async def evaluate_condition(self,
                                condition_type: str,
                                condition_config: Dict[str, Any],
                                context: RoutingContext) -> bool:
        """Evaluate a routing condition"""
        if condition_type == "always":
            return True

        if condition_type not in self.evaluators:
            raise ValueError(f"Unknown condition type: {condition_type}")

        # Create evaluator based on type
        if condition_type == "expression":
            evaluator = ExpressionConditionEvaluator(
                source=condition_config["source"],
                operator=condition_config["operator"],
                value=condition_config["value"]
            )
        elif condition_type == "agent":
            evaluator: Any = AgentConditionEvaluator(**condition_config)
        elif condition_type == "function":
            evaluator: Any = FunctionConditionEvaluator(**condition_config)

        return await evaluator.evaluate(context)

    async def find_next_steps(self,
                             current_step: str,
                             flow_paths: List[Dict[str, Any]],
                             context: RoutingContext) -> List[str]:
        """Find next steps based on condition evaluation"""
        next_steps = []

        for path in flow_paths:
            if path["from"] != current_step:
                continue

            condition = path.get("condition", {})
            condition_type = condition.get("type", "always")
            condition_config = condition.get("config", {})

            try:
                should_take_path = await self.evaluate_condition(
                    condition_type, condition_config, context
                )

                if should_take_path:
                    next_steps.append(path["to"])

            except Exception as e:
                # Log error but continue evaluation
                print(f"Error evaluating condition for path {path}: {str(e)}")
                continue

        return next_steps


class ParallelExecutor:
    """Parallel execution manager for independent paths"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.active_tasks = {}

    async def execute_parallel_steps(self,
                                   steps: List[str],
                                   step_executor: Callable,
                                   context: RoutingContext) -> Dict[str, Any]:
        """Execute multiple steps in parallel"""
        if len(steps) <= 1:
            # No parallelization needed
            if steps:
                return await step_executor(steps[0], context)
            return {}

        # Create tasks for parallel execution
        tasks = {}
        for step_id in steps:
            task = asyncio.create_task(
                self._execute_step_with_context(step_executor, step_id, context)
            )
            tasks[step_id] = task
            self.active_tasks[step_id] = task

        # Wait for all tasks to complete
        results = {}
        for step_id, task in tasks.items():
            try:
                result = await task
                results[step_id] = result
            except Exception as e:
                results[step_id] = {"error": str(e), "status": "failed"}
            finally:
                self.active_tasks.pop(step_id, None)

        return results

    async def _execute_step_with_context(self,
                                       step_executor: Callable,
                                       step_id: str,
                                       context: RoutingContext) -> Any:
        """Execute a single step with error handling"""
        try:
            return await step_executor(step_id, context)
        except Exception as e:
            raise RuntimeError(f"Step {step_id} execution failed: {str(e)}")

    def cancel_all_tasks(self):
        """Cancel all active parallel tasks"""
        for task in self.active_tasks.values():
            if not task.done():
                task.cancel()
        self.active_tasks.clear()

    def get_active_step_count(self) -> int:
        """Get number of currently active parallel steps"""
        return len([task for task in self.active_tasks.values() if not task.done()])
