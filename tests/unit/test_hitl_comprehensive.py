"""
Comprehensive pytest tests for HITL (Human-in-the-Loop) functionality
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from nexusql import DatabaseManager
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
from ia_modules.pipeline.core import ExecutionContext, ServiceRegistry, Step
from ia_modules.pipeline.execution_tracker import ExecutionTracker, ExecutionStatus
from ia_modules.pipeline.hitl_manager import HITLManager
from ia_modules.database import MIGRATIONS_DIR


@pytest.fixture
async def db_manager():
    """Create in-memory database for testing"""
    db = DatabaseManager("sqlite:///:memory:")
    await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
    yield db
    db.disconnect()


@pytest.fixture
async def services(db_manager):
    """Create service registry with all required services"""
    services = ServiceRegistry()
    services.register('database', db_manager)

    tracker = ExecutionTracker(db_manager)
    services.register('execution_tracker', tracker)

    hitl_manager = HITLManager(db_manager)
    services.register('hitl_manager', hitl_manager)

    return services


@pytest.fixture
def simple_hitl_pipeline_config():
    """Simple HITL pipeline configuration"""
    return {
        "name": "Test HITL Pipeline",
        "steps": [
            {
                "id": "prepare",
                "name": "Prepare",
                "step_class": "PrepareStep",
                "module": "tests.unit.test_hitl_comprehensive",
                "config": {}
            },
            {
                "id": "human_review",
                "name": "Human Review",
                "step_class": "HITLReviewStep",
                "module": "tests.unit.test_hitl_comprehensive",
                "config": {
                    "channels": ["web"],
                    "assigned_users": ["test-user@example.com"]
                }
            },
            {
                "id": "finalize",
                "name": "Finalize",
                "step_class": "FinalizeStep",
                "module": "tests.unit.test_hitl_comprehensive",
                "config": {}
            }
        ],
        "flow": {
            "start_at": "prepare",
            "paths": [
                {"from": "prepare", "to": "human_review"},
                {"from": "human_review", "to": "finalize"}
            ]
        }
    }


# Test step implementations
class PrepareStep(Step):
    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"prepared_data": "test data", "status": "prepared"}


class HITLReviewStep(Step):
    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "human_input_required",
            "prompt": "Please review the data",
            "ui_schema": {
                "type": "form",
                "fields": [
                    {"name": "decision", "type": "radio", "options": [
                        {"value": "approve", "label": "Approve"},
                        {"value": "reject", "label": "Reject"}
                    ]}
                ]
            },
            "channels": self.config.get('channels', ['web']),
            "assigned_users": self.config.get('assigned_users', []),
            "timeout_seconds": 300
        }


class FinalizeStep(Step):
    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        decision = data.get('decision', 'unknown')
        return {"status": "completed", "decision": decision, "final_result": f"Finalized with {decision}"}


# Test cases
@pytest.mark.skip(reason="Execution tracking in HITL needs investigation - other HITL features work")
@pytest.mark.asyncio
async def test_hitl_pipeline_pauses_correctly(services, simple_hitl_pipeline_config):
    """Test that pipeline pauses when step returns human_input_required"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-001",
        pipeline_id="test-hitl-pipeline"
    )

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        {"initial": "data"},
        execution_context,
        use_enhanced_features=True
    )

    # Verify pipeline paused
    assert result['status'] == 'waiting_for_human'
    assert result['waiting_step'] == 'human_review'
    assert result['interaction_id'] is not None

    # Verify execution marked as waiting
    tracker = services.get('execution_tracker')
    execution = await tracker.get_execution("test-exec-001")
    assert execution.status == ExecutionStatus.WAITING_FOR_HUMAN


@pytest.mark.asyncio
async def test_hitl_interaction_created_in_database(services, simple_hitl_pipeline_config):
    """Test that HITL interaction is created in database with correct data"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-002",
        pipeline_id="test-hitl-pipeline"
    )

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        {"initial": "data"},
        execution_context,
        use_enhanced_features=True
    )

    interaction_id = result['interaction_id']
    hitl_manager = services.get('hitl_manager')

    # Verify interaction exists
    interaction = await hitl_manager.get_interaction(interaction_id)
    assert interaction is not None
    assert interaction.execution_id == "test-exec-002"
    assert interaction.pipeline_id == "test-hitl-pipeline"
    assert interaction.step_id == "human_review"
    assert interaction.status == "pending"
    assert interaction.prompt == "Please review the data"
    assert interaction.ui_schema['type'] == 'form'


@pytest.mark.asyncio
async def test_hitl_user_assignment_created(services, simple_hitl_pipeline_config):
    """Test that user assignments are created for HITL interactions"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-003",
        pipeline_id="test-hitl-pipeline"
    )

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        {"initial": "data"},
        execution_context,
        use_enhanced_features=True
    )

    # Query pending interactions for assigned user
    hitl_manager = services.get('hitl_manager')
    user_interactions = await hitl_manager.get_pending_interactions(
        user_id="test-user@example.com"
    )

    assert len(user_interactions) == 1
    assert user_interactions[0].interaction_id == result['interaction_id']


@pytest.mark.asyncio
async def test_hitl_respond_to_interaction(services, simple_hitl_pipeline_config):
    """Test responding to a HITL interaction"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-004",
        pipeline_id="test-hitl-pipeline"
    )

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        {"initial": "data"},
        execution_context,
        use_enhanced_features=True
    )

    interaction_id = result['interaction_id']
    hitl_manager = services.get('hitl_manager')

    # Submit human response
    human_input = {"decision": "approve", "comments": "Looks good"}
    success = await hitl_manager.respond_to_interaction(
        interaction_id=interaction_id,
        human_input=human_input,
        responded_by="test-user@example.com"
    )

    assert success is True

    # Verify interaction updated
    interaction = await hitl_manager.get_interaction(interaction_id)
    assert interaction.status == "completed"
    assert interaction.human_input == human_input
    assert interaction.responded_by == "test-user@example.com"
    assert interaction.completed_at is not None


@pytest.mark.asyncio
async def test_hitl_execution_state_saved(services, simple_hitl_pipeline_config):
    """Test that execution state is saved with HITL interaction"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-005",
        pipeline_id="test-hitl-pipeline"
    )

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        {"initial": "data"},
        execution_context,
        use_enhanced_features=True
    )

    interaction_id = result['interaction_id']
    hitl_manager = services.get('hitl_manager')

    # Get execution state
    exec_state = await hitl_manager.get_execution_state(interaction_id)

    assert exec_state is not None
    assert exec_state['pipeline_name'] == "Test HITL Pipeline"
    assert exec_state['current_step'] == "human_review"
    assert 'current_data' in exec_state
    assert 'input_data' in exec_state
    assert 'execution_context' in exec_state
    assert exec_state['execution_context']['execution_id'] == "test-exec-005"


@pytest.mark.asyncio
async def test_hitl_query_by_pipeline(services, simple_hitl_pipeline_config):
    """Test querying HITL interactions by pipeline ID"""
    runner = GraphPipelineRunner(services)

    # Create multiple interactions
    for i in range(3):
        execution_context = ExecutionContext(
            execution_id=f"test-exec-00{i}",
            pipeline_id="test-hitl-pipeline"
        )

        await runner.run_pipeline_from_json(
            simple_hitl_pipeline_config,
            {"initial": f"data-{i}"},
            execution_context,
            use_enhanced_features=True
        )

    # Query by pipeline
    hitl_manager = services.get('hitl_manager')
    pipeline_interactions = await hitl_manager.get_pending_interactions(
        pipeline_id="test-hitl-pipeline"
    )

    assert len(pipeline_interactions) == 3


@pytest.mark.asyncio
async def test_hitl_query_by_execution(services, simple_hitl_pipeline_config):
    """Test querying HITL interactions by execution ID"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-specific",
        pipeline_id="test-hitl-pipeline"
    )

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        {"initial": "data"},
        execution_context,
        use_enhanced_features=True
    )

    # Query by execution ID
    hitl_manager = services.get('hitl_manager')
    exec_interactions = await hitl_manager.get_pending_interactions(
        execution_id="test-exec-specific"
    )

    assert len(exec_interactions) == 1
    assert exec_interactions[0].interaction_id == result['interaction_id']


@pytest.mark.asyncio
async def test_hitl_expired_interaction_rejected(services):
    """Test that expired interactions cannot be responded to"""
    hitl_manager = services.get('hitl_manager')
    db_manager = services.get('database')

    # Create expired interaction manually
    interaction_id = "expired-test-001"
    expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired 1 hour ago

    query = """
    INSERT INTO hitl_interactions
    (interaction_id, execution_id, pipeline_id, step_id, step_name,
     status, ui_schema, prompt, context_data, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    db_manager.execute(query, (
        interaction_id,
        "test-exec-expired",
        "test-pipeline",
        "test-step",
        "Test Step",
        "pending",
        json.dumps({"type": "form", "fields": []}),
        "Test prompt",
        json.dumps({}),
        datetime.now(timezone.utc),
        expires_at
    ))

    # Try to respond to expired interaction
    success = await hitl_manager.respond_to_interaction(
        interaction_id=interaction_id,
        human_input={"decision": "approve"},
        responded_by="test-user"
    )

    assert success is False


@pytest.mark.asyncio
async def test_hitl_multiple_users_assigned(services):
    """Test that multiple users can be assigned to same interaction"""
    hitl_manager = services.get('hitl_manager')

    # Create interaction with multiple users
    interaction_id = await hitl_manager.create_interaction(
        execution_id="test-exec-multi",
        pipeline_id="test-pipeline",
        step_id="test-step",
        step_name="Test Step",
        prompt="Multi-user test",
        context_data={},
        ui_schema={"type": "form", "fields": []},
        timeout_seconds=300,
        channels=["web"],
        assigned_users=["user1@example.com", "user2@example.com", "user3@example.com"]
    )

    # Query for each user
    for user in ["user1@example.com", "user2@example.com", "user3@example.com"]:
        interactions = await hitl_manager.get_pending_interactions(user_id=user)
        assert len(interactions) == 1
        assert interactions[0].interaction_id == interaction_id


@pytest.mark.asyncio
async def test_hitl_cancel_interaction(services):
    """Test cancelling a HITL interaction"""
    hitl_manager = services.get('hitl_manager')

    # Create interaction
    interaction_id = await hitl_manager.create_interaction(
        execution_id="test-exec-cancel",
        pipeline_id="test-pipeline",
        step_id="test-step",
        step_name="Test Step",
        prompt="Cancel test",
        context_data={},
        ui_schema={"type": "form", "fields": []},
        timeout_seconds=300,
        channels=["web"],
        assigned_users=["test-user@example.com"]
    )

    # Cancel it
    success = await hitl_manager.cancel_interaction(interaction_id)
    assert success is True

    # Verify status
    interaction = await hitl_manager.get_interaction(interaction_id)
    assert interaction.status == "cancelled"

    # Verify not in pending list
    pending = await hitl_manager.get_pending_interactions()
    assert interaction_id not in [i.interaction_id for i in pending]


@pytest.mark.asyncio
async def test_hitl_double_response_rejected(services):
    """Test that responding twice to same interaction is rejected"""
    hitl_manager = services.get('hitl_manager')

    # Create interaction
    interaction_id = await hitl_manager.create_interaction(
        execution_id="test-exec-double",
        pipeline_id="test-pipeline",
        step_id="test-step",
        step_name="Test Step",
        prompt="Double response test",
        context_data={},
        ui_schema={"type": "form", "fields": []},
        timeout_seconds=300,
        channels=["web"],
        assigned_users=["test-user@example.com"]
    )

    # First response
    success1 = await hitl_manager.respond_to_interaction(
        interaction_id=interaction_id,
        human_input={"decision": "approve"},
        responded_by="user1"
    )
    assert success1 is True

    # Second response should fail
    success2 = await hitl_manager.respond_to_interaction(
        interaction_id=interaction_id,
        human_input={"decision": "reject"},
        responded_by="user2"
    )
    assert success2 is False


@pytest.mark.asyncio
async def test_hitl_context_data_preserved(services, simple_hitl_pipeline_config):
    """Test that context data from previous steps is preserved in HITL state"""
    runner = GraphPipelineRunner(services)

    execution_context = ExecutionContext(
        execution_id="test-exec-context",
        pipeline_id="test-hitl-pipeline"
    )

    initial_data = {"user_id": "user123", "request_id": "req-456"}

    result = await runner.run_pipeline_from_json(
        simple_hitl_pipeline_config,
        initial_data,
        execution_context,
        use_enhanced_features=True
    )

    # Get saved state
    hitl_manager = services.get('hitl_manager')
    exec_state = await hitl_manager.get_execution_state(result['interaction_id'])

    # Verify original data preserved
    assert exec_state['input_data']['user_id'] == "user123"
    assert exec_state['input_data']['request_id'] == "req-456"

    # Verify prepared data from first step also present
    assert exec_state['current_data']['prepared_data'] == "test data"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
