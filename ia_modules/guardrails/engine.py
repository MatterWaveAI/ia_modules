"""
GuardrailsEngine - Orchestration system for managing multiple guardrails.

Provides a unified interface for applying multiple rails in sequence or parallel.
"""
from typing import List, Dict, Any, Optional
from .base import BaseGuardrail
from .models import RailResult, RailAction, RailType, GuardrailsConfig
import asyncio


class GuardrailsEngine:
    """
    Orchestrates multiple guardrails for comprehensive safety.

    The engine manages rails across all types (input, output, dialog, retrieval, execution)
    and provides flexible execution strategies (sequential, parallel, fail-fast, etc.).
    """

    def __init__(self, config: Optional[GuardrailsConfig] = None):
        """
        Initialize guardrails engine.

        Args:
            config: Optional guardrails configuration
        """
        self.config = config or GuardrailsConfig()
        self.rails: Dict[RailType, List[BaseGuardrail]] = {
            RailType.INPUT: [],
            RailType.OUTPUT: [],
            RailType.DIALOG: [],
            RailType.RETRIEVAL: [],
            RailType.EXECUTION: []
        }

    def add_rail(self, rail: BaseGuardrail) -> None:
        """
        Add a guardrail to the engine.

        Args:
            rail: Guardrail instance to add
        """
        rail_type = rail.config.type
        self.rails[rail_type].append(rail)

    def add_rails(self, rails: List[BaseGuardrail]) -> None:
        """
        Add multiple guardrails to the engine.

        Args:
            rails: List of guardrail instances
        """
        for rail in rails:
            self.add_rail(rail)

    def get_rails(self, rail_type: RailType) -> List[BaseGuardrail]:
        """
        Get all rails of a specific type.

        Args:
            rail_type: Type of rails to retrieve

        Returns:
            List of guardrails of the specified type
        """
        return [rail for rail in self.rails[rail_type] if rail.config.enabled]

    async def execute_rails(
        self,
        rail_type: RailType,
        content: Any,
        context: Optional[Dict[str, Any]] = None,
        fail_fast: bool = True,
        parallel: bool = False
    ) -> Dict[str, Any]:
        """
        Execute all rails of a specific type.

        Args:
            rail_type: Type of rails to execute
            content: Content to check
            context: Additional context
            fail_fast: Stop on first BLOCK action
            parallel: Execute rails in parallel (faster but less control)

        Returns:
            Dictionary with execution results:
            {
                "action": overall_action,
                "content": final_content,
                "results": list_of_rail_results,
                "triggered_count": number_of_triggered_rails
            }
        """
        rails = self.get_rails(rail_type)

        if not rails:
            return {
                "action": RailAction.ALLOW,
                "content": content,
                "results": [],
                "triggered_count": 0
            }

        results: List[RailResult] = []
        current_content = content
        triggered_count = 0

        if parallel:
            # Execute all rails in parallel
            tasks = [rail.execute(current_content, context) for rail in rails]
            results = await asyncio.gather(*tasks)
        else:
            # Execute rails sequentially
            for rail in rails:
                result = await rail.execute(current_content, context)
                results.append(result)

                if result.triggered:
                    triggered_count += 1

                # Handle result action
                if result.action == RailAction.BLOCK:
                    if fail_fast:
                        return {
                            "action": RailAction.BLOCK,
                            "content": current_content,
                            "results": results,
                            "triggered_count": triggered_count,
                            "blocked_by": result.rail_id,
                            "reason": result.reason
                        }
                elif result.action == RailAction.MODIFY:
                    current_content = result.modified_content

        # Determine overall action
        overall_action = RailAction.ALLOW
        if any(r.action == RailAction.BLOCK for r in results):
            overall_action = RailAction.BLOCK
        elif any(r.action == RailAction.WARN for r in results):
            overall_action = RailAction.WARN
        elif any(r.action == RailAction.MODIFY for r in results):
            overall_action = RailAction.MODIFY

        return {
            "action": overall_action,
            "content": current_content,
            "results": results,
            "triggered_count": triggered_count
        }

    async def check_input(
        self,
        content: Any,
        context: Optional[Dict[str, Any]] = None,
        fail_fast: bool = True
    ) -> Dict[str, Any]:
        """
        Execute all input rails.

        Args:
            content: User input to check
            context: Additional context
            fail_fast: Stop on first BLOCK

        Returns:
            Execution results dictionary
        """
        return await self.execute_rails(
            RailType.INPUT,
            content,
            context,
            fail_fast=fail_fast
        )

    async def check_output(
        self,
        content: Any,
        context: Optional[Dict[str, Any]] = None,
        fail_fast: bool = False  # Usually want to apply all output modifications
    ) -> Dict[str, Any]:
        """
        Execute all output rails.

        Args:
            content: LLM output to check
            context: Additional context
            fail_fast: Stop on first BLOCK

        Returns:
            Execution results dictionary
        """
        return await self.execute_rails(
            RailType.OUTPUT,
            content,
            context,
            fail_fast=fail_fast
        )

    async def check_dialog(
        self,
        content: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute all dialog rails.

        Args:
            content: Current message
            context: Conversation context (should include conversation_history)

        Returns:
            Execution results dictionary
        """
        return await self.execute_rails(
            RailType.DIALOG,
            content,
            context,
            fail_fast=False  # Dialog rails usually just warn
        )

    async def check_retrieval(
        self,
        content: Any,
        context: Optional[Dict[str, Any]] = None,
        fail_fast: bool = False
    ) -> Dict[str, Any]:
        """
        Execute all retrieval rails.

        Args:
            content: Retrieved documents
            context: Retrieval context (should include metadata)
            fail_fast: Stop on first BLOCK

        Returns:
            Execution results dictionary
        """
        return await self.execute_rails(
            RailType.RETRIEVAL,
            content,
            context,
            fail_fast=fail_fast
        )

    async def check_execution(
        self,
        content: Any,
        context: Optional[Dict[str, Any]] = None,
        fail_fast: bool = True
    ) -> Dict[str, Any]:
        """
        Execute all execution rails.

        Args:
            content: Code or tool call to check
            context: Execution context (should include tool_name, parameters, etc.)
            fail_fast: Stop on first BLOCK

        Returns:
            Execution results dictionary
        """
        return await self.execute_rails(
            RailType.EXECUTION,
            content,
            context,
            fail_fast=fail_fast
        )

    async def process_llm_call(
        self,
        user_input: str,
        llm_callable,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        input_context: Optional[Dict[str, Any]] = None,
        output_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a complete LLM call with input and output rails.

        Args:
            user_input: User's input message
            llm_callable: Async callable that takes input and returns LLM response
            conversation_history: Optional conversation history for dialog rails
            input_context: Additional context for input rails
            output_context: Additional context for output rails

        Returns:
            Dictionary with:
            {
                "response": final_response,
                "input_result": input_rails_result,
                "output_result": output_rails_result,
                "dialog_result": dialog_rails_result (if history provided),
                "blocked": True/False,
                "warnings": list_of_warnings
            }
        """
        # Prepare contexts
        input_ctx = input_context or {}
        output_ctx = output_context or {}

        # Check dialog rails if history provided
        dialog_result = None
        if conversation_history is not None:
            dialog_ctx = {"conversation_history": conversation_history}
            dialog_result = await self.check_dialog(user_input, context=dialog_ctx)

        # Check input rails
        input_result = await self.check_input(user_input, context=input_ctx)

        if input_result["action"] == RailAction.BLOCK:
            return {
                "response": None,
                "input_result": input_result,
                "output_result": None,
                "dialog_result": dialog_result,
                "blocked": True,
                "reason": input_result.get("reason", "Input blocked by guardrails"),
                "warnings": self._extract_warnings([input_result, dialog_result])
            }

        # Get potentially modified input
        processed_input = input_result["content"]

        # Call LLM
        try:
            llm_response = await llm_callable(processed_input)
        except Exception as e:
            return {
                "response": None,
                "input_result": input_result,
                "output_result": None,
                "dialog_result": dialog_result,
                "blocked": True,
                "reason": f"LLM call failed: {str(e)}",
                "warnings": self._extract_warnings([input_result, dialog_result])
            }

        # Check output rails
        output_result = await self.check_output(llm_response, context=output_ctx)

        if output_result["action"] == RailAction.BLOCK:
            return {
                "response": None,
                "input_result": input_result,
                "output_result": output_result,
                "dialog_result": dialog_result,
                "blocked": True,
                "reason": output_result.get("reason", "Output blocked by guardrails"),
                "warnings": self._extract_warnings([input_result, output_result, dialog_result])
            }

        # Get final response (potentially modified by output rails)
        final_response = output_result["content"]

        return {
            "response": final_response,
            "input_result": input_result,
            "output_result": output_result,
            "dialog_result": dialog_result,
            "blocked": False,
            "warnings": self._extract_warnings([input_result, output_result, dialog_result])
        }

    def _extract_warnings(self, results: List[Optional[Dict[str, Any]]]) -> List[str]:
        """Extract warning messages from results."""
        warnings: List[str] = []
        for result in results:
            if result is None:
                continue
            for rail_result in result.get("results", []):
                if rail_result.action == RailAction.WARN and rail_result.reason is not None:
                    warnings.append(rail_result.reason)
        return warnings

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics for all rails.

        Returns:
            Dictionary with statistics per rail type and overall
        """
        stats = {
            "total_rails": sum(len(rails) for rails in self.rails.values()),
            "by_type": {}
        }

        for rail_type, rails in self.rails.items():
            type_stats = {
                "count": len(rails),
                "enabled": sum(1 for r in rails if r.config.enabled),
                "rails": [rail.get_stats() for rail in rails]
            }
            stats["by_type"][rail_type.value] = type_stats

        return stats

    def clear_rails(self, rail_type: Optional[RailType] = None) -> None:
        """
        Clear rails from the engine.

        Args:
            rail_type: If provided, only clear rails of this type.
                      If None, clear all rails.
        """
        if rail_type is None:
            for rt in RailType:
                self.rails[rt] = []
        else:
            self.rails[rail_type] = []
