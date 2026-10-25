"""
Unit Tests for MultiAgentService

Tests workflow creation, execution, hooks, persistence, and error handling.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path

from services.multi_agent_service import MultiAgentService


@pytest.fixture
async def service():
    """Create a temporary MultiAgentService instance"""
    temp_dir = tempfile.mkdtemp()
    service = MultiAgentService(storage_dir=temp_dir)
    yield service
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_create_simple_workflow(service):
    """Test creating a simple sequential workflow"""
    agents = [
        {"id": "agent1", "role": "planner", "description": "Plans the task"},
        {"id": "agent2", "role": "executor", "description": "Executes the task"}
    ]
    edges = [
        {"from": "agent1", "to": "agent2"}
    ]
    
    result = await service.create_workflow(
        workflow_id="test_workflow_1",
        agents=agents,
        edges=edges
    )
    
    assert result["workflow_id"] == "test_workflow_1"
    assert result["num_agents"] == 2
    assert result["num_edges"] == 1
    assert "test_workflow_1" in service.active_workflows


@pytest.mark.asyncio
async def test_create_workflow_with_feedback_loop(service):
    """Test creating a workflow with feedback loops"""
    agents = [
        {"id": "coder", "role": "coder", "description": "Writes code"},
        {"id": "critic", "role": "critic", "description": "Reviews code"}
    ]
    edges = [
        {"from": "coder", "to": "critic"}
    ]
    feedback_loops = [
        {"from": "coder", "to": "critic", "max_iterations": 3}
    ]
    
    result = await service.create_workflow(
        workflow_id="feedback_workflow",
        agents=agents,
        edges=edges,
        feedback_loops=feedback_loops
    )
    
    assert result["workflow_id"] == "feedback_workflow"
    assert result["num_agents"] == 2


@pytest.mark.asyncio
async def test_execute_workflow(service):
    """Test executing a workflow and tracking communications"""
    agents = [
        {"id": "agent1", "role": "planner", "description": "Plans"},
        {"id": "agent2", "role": "researcher", "description": "Researches"}
    ]
    edges = [
        {"from": "agent1", "to": "agent2"}
    ]
    
    await service.create_workflow(
        workflow_id="exec_test",
        agents=agents,
        edges=edges
    )
    
    result = await service.execute_workflow(
        workflow_id="exec_test",
        start_agent="agent1",
        initial_data={"task": "test task"}
    )
    
    assert "execution_id" in result
    assert result["workflow_id"] == "exec_test"
    assert len(result["communication_log"]) > 0
    assert "agent1" in result["execution_path"]
    assert "agent2" in result["execution_path"]


@pytest.mark.asyncio
async def test_workflow_communication_tracking(service):
    """Test that agent communications are properly tracked"""
    agents = [
        {"id": "agent1", "role": "planner", "description": "Plans"},
        {"id": "agent2", "role": "executor", "description": "Executes"}
    ]
    edges = [
        {"from": "agent1", "to": "agent2"}
    ]
    
    await service.create_workflow(
        workflow_id="comm_test",
        agents=agents,
        edges=edges
    )
    
    result = await service.execute_workflow(
        workflow_id="comm_test",
        start_agent="agent1",
        initial_data={"data": "test"}
    )
    
    comm_log = result["communication_log"]
    
    # Check for agent activation events
    activations = [log for log in comm_log if log["type"] == "agent_activated"]
    assert len(activations) == 2
    
    # Check for agent completion events
    completions = [log for log in comm_log if log["type"] == "agent_completed"]
    assert len(completions) == 2
    
    # Check timestamps exist
    for log in comm_log:
        assert "timestamp" in log


@pytest.mark.asyncio
async def test_agent_stats_tracking(service):
    """Test that agent statistics are properly tracked"""
    agents = [
        {"id": "agent1", "role": "worker", "description": "Worker"}
    ]
    edges = []
    
    await service.create_workflow(
        workflow_id="stats_test",
        agents=agents,
        edges=edges
    )
    
    result = await service.execute_workflow(
        workflow_id="stats_test",
        start_agent="agent1",
        initial_data={"data": "test"}
    )
    
    assert "agent_stats" in result
    assert "agent1" in result["agent_stats"]
    
    stats = result["agent_stats"]["agent1"]
    assert stats["executions"] == 1
    assert "total_duration" in stats
    assert len(stats["iterations"]) == 1


@pytest.mark.asyncio
async def test_get_workflow_state(service):
    """Test retrieving workflow state"""
    agents = [
        {"id": "agent1", "role": "planner", "description": "Plans"}
    ]
    edges = []
    
    await service.create_workflow(
        workflow_id="state_test",
        agents=agents,
        edges=edges
    )
    
    state = await service.get_workflow_state("state_test")
    
    assert state["workflow_id"] == "state_test"
    assert state["status"] == "created"
    assert "state" in state


@pytest.mark.asyncio
async def test_get_agent_communications(service):
    """Test retrieving agent communications for a workflow"""
    agents = [
        {"id": "agent1", "role": "worker", "description": "Worker"}
    ]
    edges = []
    
    await service.create_workflow(
        workflow_id="comm_retrieve_test",
        agents=agents,
        edges=edges
    )
    
    await service.execute_workflow(
        workflow_id="comm_retrieve_test",
        start_agent="agent1",
        initial_data={}
    )
    
    communications = await service.get_agent_communications("comm_retrieve_test")
    
    assert len(communications) > 0
    assert any(log["type"] == "agent_activated" for log in communications)
    assert any(log["type"] == "agent_completed" for log in communications)


@pytest.mark.asyncio
async def test_list_workflows(service):
    """Test listing all workflows"""
    await service.create_workflow(
        workflow_id="wf1",
        agents=[{"id": "a1", "role": "worker", "description": "W"}],
        edges=[]
    )
    
    await service.create_workflow(
        workflow_id="wf2",
        agents=[{"id": "a2", "role": "worker", "description": "W"}],
        edges=[]
    )
    
    workflows = service.list_workflows()
    
    assert len(workflows) == 2
    assert any(wf["workflow_id"] == "wf1" for wf in workflows)
    assert any(wf["workflow_id"] == "wf2" for wf in workflows)


@pytest.mark.asyncio
async def test_execution_history(service):
    """Test execution history tracking"""
    agents = [
        {"id": "agent1", "role": "worker", "description": "Worker"}
    ]
    edges = []
    
    await service.create_workflow(
        workflow_id="history_test",
        agents=agents,
        edges=edges
    )
    
    # Execute twice
    await service.execute_workflow("history_test", "agent1", {})
    await service.execute_workflow("history_test", "agent1", {})
    
    history = service.get_execution_history()
    
    assert len(history) == 2
    assert all("execution_id" in exec for exec in history)


@pytest.mark.asyncio
async def test_save_workflow(service):
    """Test saving workflow to persistent storage"""
    agents = [
        {"id": "agent1", "role": "planner", "description": "Plans"},
        {"id": "agent2", "role": "executor", "description": "Executes"}
    ]
    edges = [
        {"from": "agent1", "to": "agent2"}
    ]
    
    await service.create_workflow(
        workflow_id="save_test",
        agents=agents,
        edges=edges
    )
    
    result = await service.save_workflow(
        workflow_id="save_test",
        name="Test Workflow",
        description="A test workflow"
    )
    
    assert result["workflow_id"] == "save_test"
    assert result["name"] == "Test Workflow"
    assert "file_path" in result
    
    # Check file exists
    file_path = Path(result["file_path"])
    assert file_path.exists()
    
    # Verify content
    with open(file_path) as f:
        data = json.load(f)
    
    assert data["workflow_id"] == "save_test"
    assert data["name"] == "Test Workflow"
    assert len(data["agents"]) == 2


@pytest.mark.asyncio
async def test_load_workflow(service):
    """Test loading workflow from persistent storage"""
    agents = [
        {"id": "agent1", "role": "planner", "description": "Plans"}
    ]
    edges = []
    
    # Create and save
    await service.create_workflow(
        workflow_id="load_test",
        agents=agents,
        edges=edges
    )
    
    await service.save_workflow(
        workflow_id="load_test",
        name="Load Test",
        description="Test loading"
    )
    
    # Clear active workflows
    service.active_workflows.clear()
    
    # Load
    result = await service.load_workflow("load_test")
    
    assert result["workflow_id"] == "load_test"
    assert result["name"] == "Load Test"
    assert "load_test" in service.active_workflows


@pytest.mark.asyncio
async def test_list_saved_workflows(service):
    """Test listing saved workflows"""
    # Create and save multiple workflows
    for i in range(3):
        await service.create_workflow(
            workflow_id=f"wf_{i}",
            agents=[{"id": "a1", "role": "worker", "description": "W"}],
            edges=[]
        )
        await service.save_workflow(
            workflow_id=f"wf_{i}",
            name=f"Workflow {i}",
            description=f"Description {i}"
        )
    
    saved = await service.list_saved_workflows()
    
    assert len(saved) == 3
    assert all("workflow_id" in wf for wf in saved)
    assert all("name" in wf for wf in saved)


@pytest.mark.asyncio
async def test_delete_saved_workflow(service):
    """Test deleting saved workflow"""
    await service.create_workflow(
        workflow_id="delete_test",
        agents=[{"id": "a1", "role": "worker", "description": "W"}],
        edges=[]
    )
    
    await service.save_workflow(
        workflow_id="delete_test",
        name="Delete Test",
        description=""
    )
    
    result = await service.delete_saved_workflow("delete_test")
    
    assert result["workflow_id"] == "delete_test"
    assert "deleted_at" in result
    
    # Verify file doesn't exist
    file_path = service.storage_dir / "delete_test.json"
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_websocket_callback(service):
    """Test WebSocket callback is invoked during execution"""
    events = []
    
    async def mock_callback(workflow_id, event_type, data):
        events.append({
            "workflow_id": workflow_id,
            "event_type": event_type,
            "data": data
        })
    
    service.set_websocket_callback(mock_callback)
    
    agents = [
        {"id": "agent1", "role": "worker", "description": "Worker"}
    ]
    edges = []
    
    await service.create_workflow(
        workflow_id="ws_test",
        agents=agents,
        edges=edges
    )
    
    await service.execute_workflow(
        workflow_id="ws_test",
        start_agent="agent1",
        initial_data={}
    )
    
    # Check events were emitted
    assert len(events) > 0
    assert any(e["event_type"] == "agent_start" for e in events)
    assert any(e["event_type"] == "agent_complete" for e in events)


@pytest.mark.asyncio
async def test_workflow_not_found_error(service):
    """Test error handling for non-existent workflow"""
    with pytest.raises(ValueError, match="not found"):
        await service.execute_workflow(
            workflow_id="nonexistent",
            start_agent="agent1",
            initial_data={}
        )


@pytest.mark.asyncio
async def test_conditional_routing(service):
    """Test workflow with conditional edges"""
    agents = [
        {"id": "router", "role": "router", "description": "Routes"},
        {"id": "path_a", "role": "worker_a", "description": "Path A"},
        {"id": "path_b", "role": "worker_b", "description": "Path B"}
    ]
    edges = [
        {"from": "router", "to": "path_a", "condition": "needs_analysis"},
        {"from": "router", "to": "path_b", "condition": "needs_generation"}
    ]
    
    result = await service.create_workflow(
        workflow_id="conditional_test",
        agents=agents,
        edges=edges
    )
    
    assert result["workflow_id"] == "conditional_test"
    assert result["num_agents"] == 3


@pytest.mark.asyncio
async def test_workflow_status_updates(service):
    """Test that workflow status is updated during execution"""
    agents = [
        {"id": "agent1", "role": "worker", "description": "Worker"}
    ]
    edges = []
    
    await service.create_workflow(
        workflow_id="status_test",
        agents=agents,
        edges=edges
    )
    
    # Initial status
    workflow = service.active_workflows["status_test"]
    assert workflow["status"] == "created"
    
    # Execute
    await service.execute_workflow(
        workflow_id="status_test",
        start_agent="agent1",
        initial_data={}
    )
    
    # Status after execution
    assert workflow["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
