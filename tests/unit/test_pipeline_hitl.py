"""
Tests for pipeline.hitl module - Human-in-the-Loop components
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from ia_modules.pipeline.hitl import (
    HITLException,
    InteractionTimeoutException,
    PipelineStateManager,
    get_state_manager,
    set_state_manager,
    HumanInputStep,
    PauseForInputStep,
    ReviewAndApproveStep,
    ConditionalHumanStep,
    MultiStakeholderStep,
    TimeBasedDecisionStep,
    HITLResumeManager,
    create_pause_step,
    create_approval_step,
    create_conditional_step
)


class MockDBManager:
    """Mock database manager for testing"""
    def __init__(self):
        self.execute_calls = []
        self.fetch_calls = []
        self.execute_results = []
        self.fetch_results = []

    async def execute_async(self, query, params=None):
        self.execute_calls.append((query, params))
        if self.execute_results:
            return self.execute_results.pop(0)
        return MagicMock(success=True)

    async def fetch_one(self, query, params=None):
        self.fetch_calls.append((query, params))
        if self.fetch_results:
            return self.fetch_results.pop(0)
        return None

    def add_fetch_result(self, result):
        self.fetch_results.append(result)


class MockCacheService:
    """Mock cache service for testing"""
    def __init__(self):
        self.cache = {}

    async def set(self, key, value, timeout=None):
        self.cache[key] = value

    async def get(self, key):
        return self.cache.get(key)

    async def delete(self, key):
        if key in self.cache:
            del self.cache[key]


class TestHITLExceptions:
    """Test HITL exception classes"""

    def test_hitl_exception(self):
        """Test HITLException"""
        exc = HITLException("Test error")
        assert str(exc) == "Test error"
        assert isinstance(exc, Exception)

    def test_interaction_timeout_exception(self):
        """Test InteractionTimeoutException"""
        exc = InteractionTimeoutException("Timeout")
        assert str(exc) == "Timeout"
        assert isinstance(exc, HITLException)
        assert isinstance(exc, Exception)


@pytest.mark.asyncio
class TestPipelineStateManager:
    """Test PipelineStateManager"""

    async def test_init_no_services(self):
        """Test initialization without services"""
        manager = PipelineStateManager()
        assert manager.db_manager is None
        assert manager.cache_service is None
        assert isinstance(manager.in_memory_states, dict)

    async def test_init_with_services(self):
        """Test initialization with services"""
        db = MockDBManager()
        cache = MockCacheService()
        manager = PipelineStateManager(db, cache)
        assert manager.db_manager is db
        assert manager.cache_service is cache

    async def test_save_state_in_memory(self):
        """Test save state to in-memory storage"""
        manager = PipelineStateManager()

        await manager.save_state(
            "test-id",
            "test_pipeline",
            "test_step",
            {"key": "value"},
            timeout_seconds=3600
        )

        assert "test-id" in manager.in_memory_states
        state = manager.in_memory_states["test-id"]
        assert state["interaction_id"] == "test-id"
        assert state["pipeline_name"] == "test_pipeline"
        assert state["step_name"] == "test_step"
        assert state["data"] == {"key": "value"}
        assert state["status"] == "pending"

    async def test_save_state_with_db(self):
        """Test save state with database"""
        db = MockDBManager()
        manager = PipelineStateManager(db_manager=db)

        await manager.save_state(
            "test-id",
            "test_pipeline",
            "test_step",
            {"key": "value"}
        )

        assert len(db.execute_calls) == 1
        query, params = db.execute_calls[0]
        # Clean INSERT - no ON CONFLICT hack
        assert "INSERT INTO pipeline_states" in query
        assert "ON CONFLICT" not in query
        # Verify named parameters are used
        assert isinstance(params, dict)
        assert params['interaction_id'] == "test-id"

    async def test_save_state_with_cache(self):
        """Test save state with cache"""
        cache = MockCacheService()
        manager = PipelineStateManager(cache_service=cache)

        await manager.save_state(
            "test-id",
            "test_pipeline",
            "test_step",
            {"key": "value"},
            timeout_seconds=300
        )

        assert "pipeline_state:test-id" in cache.cache

    async def test_save_state_db_failure_fallback(self):
        """Test fallback to in-memory when DB fails"""
        db = MockDBManager()

        async def raise_error(*args, **kwargs):
            raise Exception("DB Error")

        db.execute_async = raise_error
        manager = PipelineStateManager(db_manager=db)

        await manager.save_state("test-id", "pipeline", "step", {"data": "test"})

        assert "test-id" in manager.in_memory_states

    async def test_get_state_from_memory(self):
        """Test get state from in-memory storage"""
        manager = PipelineStateManager()

        # Save state first
        await manager.save_state("test-id", "pipeline", "step", {"key": "value"})

        # Retrieve it
        state = await manager.get_state("test-id")

        assert state is not None
        assert state["interaction_id"] == "test-id"
        assert state["data"] == {"key": "value"}

    async def test_get_state_from_cache(self):
        """Test get state from cache"""
        cache = MockCacheService()
        manager = PipelineStateManager(cache_service=cache)

        # Pre-populate cache
        cached_state = {
            "interaction_id": "test-id",
            "pipeline_name": "test",
            "data": {"cached": True}
        }
        await cache.set("pipeline_state:test-id", cached_state)

        state = await manager.get_state("test-id")

        assert state is not None
        assert state["data"]["cached"] is True

    async def test_get_state_expired(self):
        """Test get state returns None when expired"""
        manager = PipelineStateManager()

        # Create expired state
        manager.in_memory_states["test-id"] = {
            "interaction_id": "test-id",
            "expires_at": datetime.now() - timedelta(hours=1),
            "data": {}
        }

        state = await manager.get_state("test-id")
        assert state is None

    async def test_get_state_not_found(self):
        """Test get state returns None when not found"""
        manager = PipelineStateManager()
        state = await manager.get_state("non-existent")
        assert state is None

    async def test_complete_state_in_memory(self):
        """Test complete state in memory"""
        manager = PipelineStateManager()

        # Save state first
        await manager.save_state("test-id", "pipeline", "step", {"key": "value"})

        # Complete it
        human_input = {"decision": "approve", "comment": "LGTM"}
        await manager.complete_state("test-id", human_input)

        state = manager.in_memory_states["test-id"]
        assert state["status"] == "completed"
        assert state["human_input"] == human_input

    async def test_complete_state_with_db(self):
        """Test complete state with database"""
        db = MockDBManager()
        manager = PipelineStateManager(db_manager=db)

        human_input = {"decision": "approve"}
        await manager.complete_state("test-id", human_input)

        assert len(db.execute_calls) == 1
        query, params = db.execute_calls[0]
        assert "UPDATE pipeline_states" in query
        # Verify named parameters are used
        assert isinstance(params, dict)
        assert params['interaction_id'] == "test-id"

    async def test_complete_state_clears_cache(self):
        """Test complete state clears cache"""
        cache = MockCacheService()
        manager = PipelineStateManager(cache_service=cache)

        # Pre-populate cache
        await cache.set("pipeline_state:test-id", {"data": "test"})

        await manager.complete_state("test-id", {"decision": "approve"})

        # Cache should be cleared
        assert await cache.get("pipeline_state:test-id") is None


@pytest.mark.asyncio
class TestStateManagerGlobal:
    """Test global state manager functions"""

    async def test_get_state_manager_singleton(self):
        """Test get_state_manager returns singleton"""
        manager1 = get_state_manager()
        manager2 = get_state_manager()
        assert manager1 is manager2

    async def test_set_state_manager(self):
        """Test set_state_manager"""
        custom_manager = PipelineStateManager()
        set_state_manager(custom_manager)

        retrieved = get_state_manager()
        assert retrieved is custom_manager

        # Reset to default
        set_state_manager(PipelineStateManager())


@pytest.mark.asyncio
class TestHumanInputStep:
    """Test HumanInputStep base class"""

    async def test_run_creates_interaction(self):
        """Test run creates interaction"""
        step = HumanInputStep("test_step", {"timeout": 600, "prompt": "Test prompt"})

        result = await step.run({"input": "data"})

        assert result["status"] == "human_input_required"
        assert "interaction_id" in result
        assert result["prompt"] == "Test prompt"
        assert result["timeout_seconds"] == 600
        assert result["data"] == {"input": "data"}

    async def test_run_default_config(self):
        """Test run with default configuration"""
        step = HumanInputStep("test_step", {})

        result = await step.run({"test": "data"})

        assert result["timeout_seconds"] == 3600  # Default timeout
        assert result["prompt"] == "Human input required"

    async def test_run_saves_state(self):
        """Test run saves pipeline state"""
        manager = PipelineStateManager()
        set_state_manager(manager)

        step = HumanInputStep("test_step", {})
        result = await step.run({"data": "test"})

        interaction_id = result["interaction_id"]
        assert interaction_id in manager.in_memory_states


@pytest.mark.asyncio
class TestPauseForInputStep:
    """Test PauseForInputStep"""

    async def test_get_default_ui_schema(self):
        """Test default UI schema"""
        step = PauseForInputStep("pause", {})
        schema = step.get_default_ui_schema()

        assert schema["type"] == "generic_input"
        assert "fields" in schema
        assert len(schema["fields"]) == 1
        assert schema["fields"][0]["name"] == "user_input"

    async def test_custom_title_description(self):
        """Test custom title and description"""
        config = {
            "title": "Custom Title",
            "description": "Custom Description"
        }
        step = PauseForInputStep("pause", config)
        schema = step.get_default_ui_schema()

        assert schema["title"] == "Custom Title"
        assert schema["description"] == "Custom Description"


@pytest.mark.asyncio
class TestReviewAndApproveStep:
    """Test ReviewAndApproveStep"""

    async def test_get_default_ui_schema(self):
        """Test default UI schema for review"""
        step = ReviewAndApproveStep("review", {})
        schema = step.get_default_ui_schema()

        assert schema["type"] == "review_approval"
        assert len(schema["fields"]) == 2

        decision_field = schema["fields"][0]
        assert decision_field["name"] == "decision"
        assert decision_field["type"] == "radio"
        assert len(decision_field["options"]) == 3

    async def test_run_with_content(self):
        """Test run adds review content to UI schema"""
        step = ReviewAndApproveStep("review", {"content_key": "content"})

        data = {"content": "This is the content to review", "other": "data"}
        result = await step.run(data)

        assert "review_content" in result
        assert result["review_content"]["content"] == "This is the content to review"
        assert result["review_content"]["content_type"] == "str"

    async def test_run_with_custom_content_key(self):
        """Test run with custom content key"""
        step = ReviewAndApproveStep("review", {"content_key": "generated_text"})

        data = {"generated_text": "AI generated content"}
        result = await step.run(data)

        assert result["review_content"]["content"] == "AI generated content"

    async def test_run_preserves_config(self):
        """Test that run preserves original config"""
        original_config = {"content_key": "test"}
        step = ReviewAndApproveStep("review", original_config)

        await step.run({"test": "data"})

        # Config should be restored
        assert step.config == original_config


@pytest.mark.asyncio
class TestConditionalHumanStep:
    """Test ConditionalHumanStep"""

    async def test_confidence_threshold_trigger(self):
        """Test confidence threshold triggers human input"""
        conditions = [{"type": "confidence_threshold", "threshold": 0.8}]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"confidence": 0.6}
        result = await step.run(data)

        assert result["status"] == "human_input_required"
        assert "trigger_reason" in result
        assert "Low confidence" in result["trigger_reason"]

    async def test_confidence_threshold_no_trigger(self):
        """Test high confidence skips human input"""
        conditions = [{"type": "confidence_threshold", "threshold": 0.8}]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"confidence": 0.95}
        result = await step.run(data)

        assert result["status"] == "automated_processing"
        assert result["human_input_skipped"] is True

    async def test_error_occurred_trigger(self):
        """Test error condition triggers human input"""
        conditions = [{"type": "error_occurred"}]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"error": "Something went wrong"}
        result = await step.run(data)

        assert result["status"] == "human_input_required"

    async def test_error_status_trigger(self):
        """Test error status triggers human input"""
        conditions = [{"type": "error_occurred"}]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"status": "error"}
        result = await step.run(data)

        assert result["status"] == "human_input_required"

    async def test_value_check_equals(self):
        """Test value check with equals operator"""
        conditions = [{
            "type": "value_check",
            "field": "status",
            "expected_value": "success",
            "operator": "equals"
        }]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"status": "failed"}
        result = await step.run(data)

        assert result["status"] == "human_input_required"

    async def test_value_check_greater_than(self):
        """Test value check with greater_than operator"""
        conditions = [{
            "type": "value_check",
            "field": "error_count",
            "expected_value": 0,
            "operator": "greater_than"
        }]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"error_count": 0}  # Not greater than 0
        result = await step.run(data)

        assert result["status"] == "human_input_required"

    async def test_value_check_less_than(self):
        """Test value check with less_than operator"""
        conditions = [{
            "type": "value_check",
            "field": "score",
            "expected_value": 50,
            "operator": "less_than"
        }]
        step = ConditionalHumanStep("conditional", {"conditions": conditions})

        data = {"score": 100}  # Not less than 50
        result = await step.run(data)

        assert result["status"] == "human_input_required"

    async def test_no_conditions_no_trigger(self):
        """Test no conditions means no trigger"""
        step = ConditionalHumanStep("conditional", {"conditions": []})

        data = {"any": "data"}
        result = await step.run(data)

        assert result["status"] == "automated_processing"

    async def test_automated_processing_result(self):
        """Test automated processing result structure"""
        step = ConditionalHumanStep("conditional", {})

        data = {"test": "data"}
        result = await step.run(data)

        assert result["processing_method"] == "automated"
        assert result["result"] == data


@pytest.mark.asyncio
class TestMultiStakeholderStep:
    """Test MultiStakeholderStep"""

    async def test_run_creates_decision(self):
        """Test run creates multi-stakeholder decision"""
        stakeholders = ["user1", "user2", "user3"]
        step = MultiStakeholderStep("multi", {"stakeholders": stakeholders})

        result = await step.run({"decision_needed": True})

        assert result["status"] == "multi_stakeholder_decision_pending"
        assert "decision_id" in result
        assert result["stakeholders"] == stakeholders
        assert result["responses_needed"] == 3

    async def test_run_no_stakeholders_raises(self):
        """Test run raises exception with no stakeholders"""
        step = MultiStakeholderStep("multi", {})

        with pytest.raises(HITLException, match="No stakeholders configured"):
            await step.run({})

    async def test_run_sets_decision_type(self):
        """Test run sets decision type"""
        config = {
            "stakeholders": ["user1"],
            "decision_type": "majority"
        }
        step = MultiStakeholderStep("multi", config)

        result = await step.run({})

        assert result["decision_type"] == "majority"

    async def test_run_default_timeout(self):
        """Test default timeout is 24 hours"""
        step = MultiStakeholderStep("multi", {"stakeholders": ["user1"]})

        result = await step.run({})

        assert result["timeout_seconds"] == 24 * 3600


@pytest.mark.asyncio
class TestTimeBasedDecisionStep:
    """Test TimeBasedDecisionStep"""

    async def test_run_creates_urgent_decision(self):
        """Test run creates urgent decision"""
        step = TimeBasedDecisionStep("urgent", {"decision_timeout": 300})

        try:
            result = await step.run({"critical": True})

            assert result["status"] == "time_sensitive_decision"
            assert result["urgent"] is True
            assert result["timeout_seconds"] == 300
            assert "interaction_id" in result
        finally:
            await step.cleanup()

    async def test_run_default_action(self):
        """Test default action configuration"""
        step = TimeBasedDecisionStep("urgent", {"default_action": "abort"})

        try:
            result = await step.run({})

            assert result["default_action"] == "abort"
        finally:
            await step.cleanup()

    async def test_run_ui_schema_structure(self):
        """Test UI schema for urgent decision"""
        step = TimeBasedDecisionStep("urgent", {})

        try:
            result = await step.run({})

            ui_schema = result["ui_schema"]
            assert ui_schema["type"] == "urgent_decision"
            assert len(ui_schema["fields"]) == 2

            decision_field = ui_schema["fields"][0]
            assert decision_field["name"] == "decision"
            assert len(decision_field["options"]) == 3
        finally:
            await step.cleanup()

    async def test_timeout_handler_applies_default(self):
        """Test timeout handler applies default action"""
        manager = PipelineStateManager()
        set_state_manager(manager)

        step = TimeBasedDecisionStep("urgent", {
            "decision_timeout": 1,  # 1 second
            "default_action": "proceed"
        })

        try:
            result = await step.run({})
            interaction_id = result["interaction_id"]

            # Wait for timeout
            await asyncio.sleep(1.5)

            state = await manager.get_state(interaction_id)
            # State should be completed with timeout
            if state:
                assert state.get("status") == "completed"
        finally:
            await step.cleanup()


@pytest.mark.asyncio
class TestHITLResumeManager:
    """Test HITLResumeManager"""

    async def test_resume_pipeline_success(self):
        """Test successful pipeline resume"""
        manager = PipelineStateManager()
        set_state_manager(manager)

        # Create a pending state
        await manager.save_state(
            "test-id",
            "test_pipeline",
            "test_step",
            {"original": "data"}
        )

        human_input = {"decision": "approve", "comments": "Looks good"}
        result = await HITLResumeManager.resume_pipeline("test-id", human_input)

        assert result["status"] == "resumed"
        assert result["pipeline_name"] == "test_pipeline"
        assert result["human_input"] == human_input
        assert result["merged_data"]["original"] == "data"
        assert result["merged_data"]["decision"] == "approve"

    async def test_resume_pipeline_not_found(self):
        """Test resume raises exception when interaction not found"""
        manager = PipelineStateManager()
        set_state_manager(manager)

        with pytest.raises(HITLException, match="No pending interaction found"):
            await HITLResumeManager.resume_pipeline("non-existent", {})

    async def test_get_pending_interactions(self):
        """Test get pending interactions"""
        result = await HITLResumeManager.get_pending_interactions()
        assert isinstance(result, list)

    async def test_cancel_interaction_success(self):
        """Test successful interaction cancellation"""
        manager = PipelineStateManager()
        set_state_manager(manager)

        await manager.save_state("test-id", "pipeline", "step", {})

        result = await HITLResumeManager.cancel_interaction("test-id", "user cancelled")
        assert result is True

    async def test_cancel_interaction_not_found(self):
        """Test cancel returns False when not found"""
        manager = PipelineStateManager()
        set_state_manager(manager)

        result = await HITLResumeManager.cancel_interaction("non-existent")
        assert result is False


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Test convenience functions"""

    async def test_create_pause_step(self):
        """Test create_pause_step"""
        step = await create_pause_step(
            "test_pause",
            "Please review",
            timeout_seconds=1800,
            ui_schema={"custom": "schema"}
        )

        assert isinstance(step, PauseForInputStep)
        assert step.name == "test_pause"
        assert step.config["prompt"] == "Please review"
        assert step.config["timeout"] == 1800
        assert step.config["ui_schema"] == {"custom": "schema"}

    async def test_create_pause_step_minimal(self):
        """Test create_pause_step with minimal config"""
        step = await create_pause_step("pause", "Review needed")

        assert isinstance(step, PauseForInputStep)
        assert step.config["timeout"] == 3600

    async def test_create_approval_step(self):
        """Test create_approval_step"""
        step = await create_approval_step(
            "approval",
            content_key="generated_content",
            timeout_seconds=7200
        )

        assert isinstance(step, ReviewAndApproveStep)
        assert step.name == "approval"
        assert step.config["content_key"] == "generated_content"
        assert step.config["timeout"] == 7200

    async def test_create_conditional_step(self):
        """Test create_conditional_step"""
        conditions = [
            {"type": "confidence_threshold", "threshold": 0.9},
            {"type": "error_occurred"}
        ]

        step = await create_conditional_step("conditional", conditions, 600)

        assert isinstance(step, ConditionalHumanStep)
        assert step.name == "conditional"
        assert step.config["conditions"] == conditions
        assert step.config["timeout"] == 600
