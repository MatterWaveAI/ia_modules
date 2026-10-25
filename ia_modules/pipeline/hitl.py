"""
Human-in-the-Loop (HITL) Pipeline Components

Production-ready implementations of various HITL patterns for IA Modules.
"""

import json
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from .core import Step


class HITLException(Exception):
    """Base exception for HITL operations"""
    pass


class InteractionTimeoutException(HITLException):
    """Raised when human interaction times out"""
    pass


class PipelineStateManager:
    """Manages pipeline state for HITL interactions"""

    def __init__(self, db_manager=None, cache_service=None):
        self.db_manager = db_manager
        self.cache_service = cache_service
        self.in_memory_states = {}  # Fallback for testing

    async def save_state(
        self,
        interaction_id: str,
        pipeline_name: str,
        step_name: str,
        data: Dict[str, Any],
        timeout_seconds: int = 3600
    ):
        """Save pipeline state for later resumption"""
        state_record = {
            "interaction_id": interaction_id,
            "pipeline_name": pipeline_name,
            "step_name": step_name,
            "data": data,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=timeout_seconds),
            "status": "pending"
        }

        if self.db_manager:
            try:
                await self.db_manager.execute_async("""
                    INSERT INTO pipeline_states
                    (interaction_id, pipeline_name, step_name, data, created_at, expires_at, status)
                    VALUES (:interaction_id, :pipeline_name, :step_name, :data, :created_at, :expires_at, :status)
                """, {
                    'interaction_id': interaction_id,
                    'pipeline_name': pipeline_name,
                    'step_name': step_name,
                    'data': json.dumps(data),
                    'created_at': state_record["created_at"],
                    'expires_at': state_record["expires_at"],
                    'status': "pending"
                })
            except Exception:
                # Fallback to in-memory
                self.in_memory_states[interaction_id] = state_record
        else:
            self.in_memory_states[interaction_id] = state_record

        # Cache for faster access
        if self.cache_service:
            try:
                await self.cache_service.set(
                    f"pipeline_state:{interaction_id}",
                    state_record,
                    timeout_seconds
                )
            except Exception:
                pass  # Cache failure is not critical

    async def get_state(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve pipeline state"""
        # Try cache first
        if self.cache_service:
            try:
                cached_state = await self.cache_service.get(f"pipeline_state:{interaction_id}")
                if cached_state:
                    return cached_state
            except Exception:
                pass

        # Try database
        if self.db_manager:
            try:
                result = await self.db_manager.fetch_one("""
                    SELECT * FROM pipeline_states
                    WHERE interaction_id = :interaction_id AND status = 'pending' AND expires_at > :now
                """, {
                    'interaction_id': interaction_id,
                    'now': datetime.now()
                })

                if result:
                    return {
                        "interaction_id": result["interaction_id"],
                        "pipeline_name": result["pipeline_name"],
                        "step_name": result["step_name"],
                        "data": json.loads(result["data"]),
                        "created_at": result["created_at"],
                        "expires_at": result["expires_at"],
                        "status": result["status"]
                    }
            except Exception:
                pass

        # Fallback to in-memory
        state = self.in_memory_states.get(interaction_id)
        if state and state["expires_at"] > datetime.now():
            return state

        return None

    async def complete_state(self, interaction_id: str, human_input: Dict[str, Any]):
        """Mark state as completed with human input"""
        if self.db_manager:
            try:
                await self.db_manager.execute_async("""
                    UPDATE pipeline_states
                    SET status = 'completed', completed_at = :completed_at, human_input = :human_input
                    WHERE interaction_id = :interaction_id
                """, {
                    'completed_at': datetime.now(),
                    'human_input': json.dumps(human_input),
                    'interaction_id': interaction_id
                })
            except Exception:
                pass

        # Update in-memory state
        if interaction_id in self.in_memory_states:
            self.in_memory_states[interaction_id]["status"] = "completed"
            self.in_memory_states[interaction_id]["human_input"] = human_input

        # Clear cache
        if self.cache_service:
            try:
                await self.cache_service.delete(f"pipeline_state:{interaction_id}")
            except Exception:
                pass


# Global state manager instance
_state_manager = None


def get_state_manager() -> PipelineStateManager:
    """Get global state manager instance"""
    global _state_manager
    if _state_manager is None:
        _state_manager = PipelineStateManager()
    return _state_manager


def set_state_manager(state_manager: PipelineStateManager):
    """Set global state manager instance"""
    global _state_manager
    _state_manager = state_manager


class HumanInputStep(Step):
    """Base class for steps requiring human interaction"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute human input step"""
        interaction_id = str(uuid.uuid4())

        # Get configuration
        timeout_seconds = self.config.get("timeout", 3600)  # 1 hour default
        ui_schema = self.config.get("ui_schema", {})
        prompt = self.config.get("prompt", "Human input required")

        # Save pipeline state
        state_manager = get_state_manager()
        await state_manager.save_state(
            interaction_id,
            getattr(self, 'pipeline_name', 'unknown'),
            self.name,
            data,
            timeout_seconds
        )

        # Return human input requirement
        return {
            "status": "human_input_required",
            "interaction_id": interaction_id,
            "ui_schema": ui_schema,
            "prompt": prompt,
            "timeout_seconds": timeout_seconds,
            "data": data,
            "step_name": self.name
        }


class PauseForInputStep(HumanInputStep):
    """Step that pauses pipeline and waits for human input"""

    def get_default_ui_schema(self) -> Dict[str, Any]:
        """Get default UI schema for generic input"""
        return {
            "type": "generic_input",
            "title": self.config.get("title", "Please provide input"),
            "description": self.config.get("description", ""),
            "fields": [
                {
                    "name": "user_input",
                    "type": "textarea",
                    "label": "Your input",
                    "required": True,
                    "placeholder": "Enter your response here..."
                }
            ]
        }


class ReviewAndApproveStep(HumanInputStep):
    """Step that requires human review and approval"""

    def get_default_ui_schema(self) -> Dict[str, Any]:
        """Get default UI schema for review and approval"""
        return {
            "type": "review_approval",
            "title": "Review and Approve",
            "fields": [
                {
                    "name": "decision",
                    "type": "radio",
                    "label": "Decision",
                    "options": [
                        {"value": "approve", "label": "Approve"},
                        {"value": "reject", "label": "Reject"},
                        {"value": "request_changes", "label": "Request Changes"}
                    ],
                    "required": True
                },
                {
                    "name": "comments",
                    "type": "textarea",
                    "label": "Comments",
                    "required": False,
                    "placeholder": "Add any comments or feedback..."
                }
            ]
        }

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute review step with content analysis"""
        # Extract content to review
        content_key = self.config.get("content_key", "content")
        content_to_review = data.get(content_key, data)

        # Add review context to UI schema
        ui_schema = self.config.get("ui_schema") or self.get_default_ui_schema()
        ui_schema["review_content"] = {
            "content": content_to_review,
            "content_type": type(content_to_review).__name__,
            "length": len(str(content_to_review))
        }

        # Update config with enhanced UI schema
        enhanced_config = {**self.config, "ui_schema": ui_schema}

        # Temporarily update config
        original_config = self.config
        self.config = enhanced_config

        try:
            result = await super().run(data)
            result["review_content"] = ui_schema["review_content"]
            return result
        finally:
            self.config = original_config


class ConditionalHumanStep(HumanInputStep):
    """Step that only requires human input under certain conditions"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute conditional human input"""
        # Check conditions
        if not self._should_require_human_input(data):
            # Proceed automatically
            return await self._automated_processing(data)

        # Require human input
        result = await super().run(data)
        result["trigger_reason"] = self._get_trigger_reason(data)
        return result

    def _should_require_human_input(self, data: Dict[str, Any]) -> bool:
        """Determine if human input is required"""
        conditions = self.config.get("conditions", [])

        for condition in conditions:
            condition_type = condition.get("type")

            if condition_type == "confidence_threshold":
                confidence = data.get("confidence", 1.0)
                threshold = condition.get("threshold", 0.8)
                if confidence < threshold:
                    return True

            elif condition_type == "error_occurred":
                if data.get("error") or data.get("status") == "error":
                    return True

            elif condition_type == "value_check":
                field = condition.get("field")
                expected_value = condition.get("expected_value")
                operator = condition.get("operator", "equals")

                actual_value = data.get(field)

                if operator == "equals" and actual_value != expected_value:
                    return True
                elif operator == "greater_than" and actual_value <= expected_value:
                    return True
                elif operator == "less_than" and actual_value >= expected_value:
                    return True

        return False

    def _get_trigger_reason(self, data: Dict[str, Any]) -> str:
        """Get reason why human input was triggered"""
        conditions = self.config.get("conditions", [])

        for condition in conditions:
            condition_type = condition.get("type")

            if condition_type == "confidence_threshold":
                confidence = data.get("confidence", 1.0)
                threshold = condition.get("threshold", 0.8)
                if confidence < threshold:
                    return f"Low confidence: {confidence} < {threshold}"

            elif condition_type == "error_occurred":
                if data.get("error"):
                    return f"Error occurred: {data.get('error')}"
                elif data.get("status") == "error":
                    return "Status indicates error"

            elif condition_type == "value_check":
                field = condition.get("field")
                expected_value = condition.get("expected_value")
                operator = condition.get("operator", "equals")
                actual_value = data.get(field)

                if operator == "equals" and actual_value != expected_value:
                    return f"Value check failed: {field} = {actual_value}, expected {expected_value}"

        return "Unknown trigger reason"

    async def _automated_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process automatically when human input not required"""
        return {
            "status": "automated_processing",
            "result": data,
            "processing_method": "automated",
            "human_input_skipped": True
        }


class MultiStakeholderStep(HumanInputStep):
    """Step that requires input from multiple stakeholders"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multi-stakeholder decision step"""
        stakeholders = self.config.get("stakeholders", [])
        decision_type = self.config.get("decision_type", "consensus")  # consensus, majority, any

        if not stakeholders:
            raise HITLException("No stakeholders configured for multi-stakeholder step")

        decision_id = str(uuid.uuid4())

        # Create interaction for tracking
        interaction_result = {
            "status": "multi_stakeholder_decision_pending",
            "decision_id": decision_id,
            "stakeholders": stakeholders,
            "decision_type": decision_type,
            "responses_needed": len(stakeholders),
            "timeout_seconds": self.config.get("timeout", 24 * 3600),  # 24 hours
            "data": data,
            "stakeholder_responses": {}
        }

        # In a full implementation, this would:
        # 1. Create individual interactions for each stakeholder
        # 2. Set up tracking for responses
        # 3. Implement decision resolution logic
        # 4. Handle timeouts and escalation

        return interaction_result


class TimeBasedDecisionStep(HumanInputStep):
    """Step with time-sensitive decision making"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize with task tracking"""
        super().__init__(name, config or {})
        self._timeout_tasks: list[Any] = []

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute time-based decision step"""
        decision_timeout = self.config.get("decision_timeout", 300)  # 5 minutes
        default_action = self.config.get("default_action", "proceed")

        interaction_id = str(uuid.uuid4())

        # Start timeout handler and keep reference
        task = asyncio.create_task(
            self._handle_timeout(interaction_id, default_action, decision_timeout)
        )
        self._timeout_tasks.append(task)

        # Save state with shorter timeout
        state_manager = get_state_manager()
        await state_manager.save_state(
            interaction_id,
            getattr(self, 'pipeline_name', 'unknown'),
            self.name,
            data,
            decision_timeout
        )

        return {
            "status": "time_sensitive_decision",
            "interaction_id": interaction_id,
            "timeout_seconds": decision_timeout,
            "default_action": default_action,
            "urgent": True,
            "ui_schema": {
                "type": "urgent_decision",
                "title": f"⚠️ Urgent Decision Required ({decision_timeout//60} minutes)",
                "fields": [
                    {
                        "name": "decision",
                        "type": "radio",
                        "label": "Your decision",
                        "options": [
                            {"value": "proceed", "label": "✅ Proceed"},
                            {"value": "abort", "label": "❌ Abort"},
                            {"value": "modify", "label": "📝 Modify"}
                        ],
                        "required": True
                    },
                    {
                        "name": "urgency_acknowledged",
                        "type": "checkbox",
                        "label": f"I understand this decision expires in {decision_timeout//60} minutes",
                        "required": True
                    }
                ]
            },
            "data": data
        }

    async def _handle_timeout(self, interaction_id: str, default_action: str, timeout: int):
        """Handle decision timeout"""
        try:
            await asyncio.sleep(timeout)

            # Check if decision was made
            state_manager = get_state_manager()
            state = await state_manager.get_state(interaction_id)

            if state and state["status"] == "pending":
                # Apply default action
                await state_manager.complete_state(
                    interaction_id,
                    {
                        "decision": default_action,
                        "timeout_applied": True,
                        "timeout_at": datetime.now().isoformat()
                    }
                )
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass

    async def cleanup(self):
        """Cancel any pending timeout tasks"""
        for task in self._timeout_tasks:
            if not task.done():
                task.cancel()
        # Wait for all tasks to complete cancellation
        if self._timeout_tasks:
            await asyncio.gather(*self._timeout_tasks, return_exceptions=True)
        self._timeout_tasks.clear()


class HITLResumeManager:
    """Manager for resuming paused pipelines"""

    @staticmethod
    async def resume_pipeline(interaction_id: str, human_input: Dict[str, Any]):
        """Resume a paused pipeline with human input"""
        state_manager = get_state_manager()
        state = await state_manager.get_state(interaction_id)

        if not state:
            raise HITLException(f"No pending interaction found for ID: {interaction_id}")

        # Mark state as completed
        await state_manager.complete_state(interaction_id, human_input)

        # Merge human input with original data
        merged_data = {**state["data"], **human_input}
        merged_data["human_input"] = human_input
        merged_data["interaction_completed"] = True
        merged_data["interaction_id"] = interaction_id

        return {
            "status": "resumed",
            "pipeline_name": state["pipeline_name"],
            "step_name": state["step_name"],
            "merged_data": merged_data,
            "human_input": human_input
        }

    @staticmethod
    async def get_pending_interactions(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all pending interactions, optionally filtered by user"""
        # This would integrate with a proper user assignment system
        # For now, return a basic structure
        return []

    @staticmethod
    async def cancel_interaction(interaction_id: str, reason: str = "cancelled"):
        """Cancel a pending interaction"""
        state_manager = get_state_manager()
        state = await state_manager.get_state(interaction_id)

        if state:
            await state_manager.complete_state(
                interaction_id,
                {"cancelled": True, "cancel_reason": reason}
            )
            return True

        return False


# Convenience functions for common HITL patterns
async def create_pause_step(
    name: str,
    prompt: str,
    timeout_seconds: int = 3600,
    ui_schema: Optional[Dict[str, Any]] = None
) -> PauseForInputStep:
    """Create a pause step with common configuration"""
    config = {
        "prompt": prompt,
        "timeout": timeout_seconds
    }

    if ui_schema:
        config["ui_schema"] = ui_schema

    return PauseForInputStep(name, config)


async def create_approval_step(
    name: str,
    content_key: str = "content",
    timeout_seconds: int = 3600
) -> ReviewAndApproveStep:
    """Create an approval step with common configuration"""
    config = {
        "content_key": content_key,
        "timeout": timeout_seconds
    }

    return ReviewAndApproveStep(name, config)


async def create_conditional_step(
    name: str,
    conditions: List[Dict[str, Any]],
    timeout_seconds: int = 3600
) -> ConditionalHumanStep:
    """Create a conditional human input step"""
    config = {
        "conditions": conditions,
        "timeout": timeout_seconds
    }

    return ConditionalHumanStep(name, config)


# Example usage and testing functions
if __name__ == "__main__":
    # Example of how to use HITL steps
    async def example_usage():
        # Create a pause step
        pause_step = await create_pause_step(
            "user_review",
            "Please review the generated content",
            timeout_seconds=1800,  # 30 minutes
            ui_schema={
                "type": "content_review",
                "fields": [
                    {
                        "name": "feedback",
                        "type": "textarea",
                        "label": "Your feedback",
                        "required": True
                    },
                    {
                        "name": "approved",
                        "type": "checkbox",
                        "label": "Approve this content",
                        "required": False
                    }
                ]
            }
        )

        # Test data
        test_data = {
            "generated_content": "This is some AI-generated content that needs review.",
            "confidence": 0.85,
            "metadata": {"model": "gpt-4", "temperature": 0.7}
        }

        # Run the step
        result = await pause_step.run(test_data)
        print("Pause step result:", json.dumps(result, indent=2, default=str))

        # Create an approval step
        approval_step = await create_approval_step("content_approval", "generated_content")
        approval_result = await approval_step.run(test_data)
        print("Approval step result:", json.dumps(approval_result, indent=2, default=str))

        # Create a conditional step
        conditional_step = await create_conditional_step(
            "quality_check",
            conditions=[
                {
                    "type": "confidence_threshold",
                    "threshold": 0.9
                },
                {
                    "type": "value_check",
                    "field": "error_count",
                    "operator": "greater_than",
                    "expected_value": 0
                }
            ]
        )

        # Test with high confidence (should not require human input)
        high_confidence_data = {**test_data, "confidence": 0.95}
        conditional_result = await conditional_step.run(high_confidence_data)
        print("Conditional step (high confidence):", json.dumps(conditional_result, indent=2, default=str))

        # Test with low confidence (should require human input)
        low_confidence_data = {**test_data, "confidence": 0.75}
        conditional_result_low = await conditional_step.run(low_confidence_data)
        print("Conditional step (low confidence):", json.dumps(conditional_result_low, indent=2, default=str))

    # Run example
    asyncio.run(example_usage())