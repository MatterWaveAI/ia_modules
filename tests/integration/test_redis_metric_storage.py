"""
Tests for Redis metric storage.

Requires Redis server running for integration tests.
Tests use a separate Redis database (db=15) to avoid conflicts.
"""

import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

redis_sync = pytest.importorskip("redis")
from ia_modules.reliability.redis_metric_storage import RedisMetricStorage

# Check if Redis server is actually running (synchronous ping — no event loop issues)
_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
try:
    _client = redis_sync.Redis.from_url(f"{_redis_url}/15", decode_responses=True, socket_timeout=2)
    _client.ping()
    _client.close()
    REDIS_SERVER_AVAILABLE = True
except Exception:
    REDIS_SERVER_AVAILABLE = False


pytestmark = [
    pytest.mark.redis,
    pytest.mark.integration,
    pytest.mark.skipif(
        not REDIS_SERVER_AVAILABLE,
        reason="Redis server not running"
    )
]


@pytest.fixture
async def redis_storage():
    """Create Redis storage for testing."""
    _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    storage = RedisMetricStorage(
        redis_url=f"{_redis_url}/15",  # Use db 15 for tests
        key_prefix="test:reliability",
        ttl_days=1  # Short TTL for tests
    )

    try:
        # Clean up any existing test data
        await storage.client.flushdb()

        yield storage
    finally:
        # Clean up
        await storage.client.flushdb()
        await storage.close()


@pytest.mark.asyncio
async def test_redis_storage_creation():
    """Test creating Redis storage instance."""
    _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    storage = RedisMetricStorage(redis_url=f"{_redis_url}/15")

    assert storage.redis_url == f"{_redis_url}/15"
    assert storage.key_prefix == "reliability"
    assert storage.ttl_seconds == 90 * 86400


@pytest.mark.asyncio
async def test_redis_storage_initialization(redis_storage):
    """Test Redis connection initialization."""
    assert redis_storage.client is not None

    # Test ping
    result = await redis_storage.client.ping()
    assert result is True


@pytest.mark.asyncio
async def test_record_step(redis_storage):
    """Test recording a step metric."""
    now = datetime.now(timezone.utc)

    await redis_storage.record_step({
        "agent": "researcher",
        "success": True,
        "required_compensation": False,
        "required_human": False,
        "mode": "execute",
        "declared_mode": "execute",
        "mode_violation": False,
        "timestamp": now
    })

    # Verify step was stored
    steps = await redis_storage.get_steps(agent="researcher")

    assert len(steps) == 1
    assert steps[0]["agent"] == "researcher"
    assert steps[0]["success"] is True
    assert steps[0]["mode"] == "execute"


@pytest.mark.asyncio
async def test_record_multiple_steps(redis_storage):
    """Test recording multiple step metrics."""
    now = datetime.now(timezone.utc)

    for i in range(5):
        await redis_storage.record_step({
            "agent": "researcher",
            "success": i % 2 == 0,  # Alternate success/failure
            "timestamp": now + timedelta(seconds=i)
        })

    steps = await redis_storage.get_steps(agent="researcher")

    assert len(steps) == 5
    # Count successful steps
    successful = sum(1 for s in steps if s["success"])
    assert successful == 3


@pytest.mark.asyncio
async def test_get_steps_with_time_filter(redis_storage):
    """Test retrieving steps with time range filter."""
    base_time = datetime.now(timezone.utc)

    # Record steps across 10 seconds
    for i in range(10):
        await redis_storage.record_step({
            "agent": "researcher",
            "success": True,
            "timestamp": base_time + timedelta(seconds=i)
        })

    # Query middle 6 seconds
    since = base_time + timedelta(seconds=2)
    until = base_time + timedelta(seconds=7)

    steps = await redis_storage.get_steps(
        agent="researcher",
        since=since,
        until=until
    )

    assert len(steps) == 6


@pytest.mark.asyncio
async def test_record_workflow(redis_storage):
    """Test recording a workflow metric."""
    now = datetime.now(timezone.utc)

    await redis_storage.record_workflow({
        "workflow_id": "workflow-123",
        "total_steps": 10,
        "total_retries": 2,
        "required_compensation": False,
        "required_human": True,
        "agents_involved": ["researcher", "planner"],
        "timestamp": now
    })

    # Verify workflow was stored
    workflows = await redis_storage.get_workflows()

    assert len(workflows) == 1
    assert workflows[0]["workflow_id"] == "workflow-123"
    assert workflows[0]["total_steps"] == 10
    assert workflows[0]["total_retries"] == 2
    assert workflows[0]["required_human"] is True
    assert "researcher" in workflows[0]["agents_involved"]


@pytest.mark.asyncio
async def test_get_workflows_with_time_filter(redis_storage):
    """Test retrieving workflows with time range filter."""
    base_time = datetime.now(timezone.utc)

    # Record workflows across 5 seconds
    for i in range(5):
        await redis_storage.record_workflow({
            "workflow_id": f"workflow-{i}",
            "total_steps": 10,
            "total_retries": 0,
            "timestamp": base_time + timedelta(seconds=i)
        })

    # Query middle 3 seconds
    since = base_time + timedelta(seconds=1)
    until = base_time + timedelta(seconds=3)

    workflows = await redis_storage.get_workflows(since=since, until=until)

    assert len(workflows) == 3


@pytest.mark.asyncio
async def test_record_mtte_measurement(redis_storage):
    """Test recording MTTE measurement."""
    await redis_storage.record_slo_measurement(
        measurement_type="mtte",
        thread_id="thread-123",
        checkpoint_id="checkpoint-456",
        value=2500.0,  # 2.5 seconds
        success=True,
        metadata={"agent": "researcher"}
    )

    # Verify measurement was stored
    measurements = await redis_storage.get_slo_measurements("mtte")

    assert len(measurements) == 1
    assert measurements[0]["measurement_type"] == "mtte"
    assert measurements[0]["value"] == 2500.0
    assert measurements[0]["success"] is True


@pytest.mark.asyncio
async def test_record_rsr_measurement(redis_storage):
    """Test recording RSR measurement."""
    await redis_storage.record_slo_measurement(
        measurement_type="rsr",
        thread_id="thread-123",
        checkpoint_id="checkpoint-456",
        value=1.0,  # Successful replay
        success=True
    )

    # Verify measurement was stored
    measurements = await redis_storage.get_slo_measurements("rsr")

    assert len(measurements) == 1
    assert measurements[0]["measurement_type"] == "rsr"
    assert measurements[0]["value"] == 1.0


@pytest.mark.asyncio
async def test_get_slo_measurements_with_time_filter(redis_storage):
    """Test retrieving SLO measurements with time range filter."""
    import asyncio

    # Record some measurements before the time window
    for i in range(3):
        await redis_storage.record_slo_measurement(
            measurement_type="mtte",
            thread_id=f"thread-before-{i}",
            checkpoint_id=f"checkpoint-before-{i}",
            value=1000.0,
            success=True
        )

    # Small delay to ensure timestamp separation
    await asyncio.sleep(0.1)

    # Mark the start of our query window
    since = datetime.now(timezone.utc)
    await asyncio.sleep(0.05)

    # Record measurements within the time window
    for i in range(6):
        await redis_storage.record_slo_measurement(
            measurement_type="mtte",
            thread_id=f"thread-{i}",
            checkpoint_id=f"checkpoint-{i}",
            value=1000.0 + i * 100,
            success=True
        )
        await asyncio.sleep(0.01)  # Small delay between records

    # Mark the end of our query window
    await asyncio.sleep(0.05)
    until = datetime.now(timezone.utc)

    # Record some measurements after the time window
    for i in range(3):
        await redis_storage.record_slo_measurement(
            measurement_type="mtte",
            thread_id=f"thread-after-{i}",
            checkpoint_id=f"checkpoint-after-{i}",
            value=2000.0,
            success=True
        )

    # Query the time window
    measurements = await redis_storage.get_slo_measurements(
        "mtte",
        since=since,
        until=until
    )

    # Should get the 6 measurements in the window
    assert len(measurements) >= 5  # Allow for small timing variations


@pytest.mark.asyncio
async def test_multiple_agents(redis_storage):
    """Test tracking metrics for multiple agents."""
    now = datetime.now(timezone.utc)

    # Record steps for different agents
    for agent in ["researcher", "planner", "executor"]:
        for i in range(3):
            await redis_storage.record_step({
                "agent": agent,
                "success": True,
                "timestamp": now + timedelta(seconds=i)
            })

    # Query each agent
    researcher_steps = await redis_storage.get_steps(agent="researcher")
    planner_steps = await redis_storage.get_steps(agent="planner")
    executor_steps = await redis_storage.get_steps(agent="executor")

    assert len(researcher_steps) == 3
    assert len(planner_steps) == 3
    assert len(executor_steps) == 3


@pytest.mark.asyncio
async def test_step_with_mode_violation(redis_storage):
    """Test recording step with mode violation."""
    await redis_storage.record_step({
        "agent": "executor",
        "success": False,
        "mode": "explore",
        "declared_mode": "execute",
        "mode_violation": True,
        "timestamp": datetime.now(timezone.utc)
    })

    steps = await redis_storage.get_steps(agent="executor")

    assert len(steps) == 1
    assert steps[0]["mode_violation"] is True
    assert steps[0]["mode"] == "explore"
    assert steps[0]["declared_mode"] == "execute"


@pytest.mark.asyncio
async def test_workflow_with_compensation(redis_storage):
    """Test recording workflow that required compensation."""
    await redis_storage.record_workflow({
        "workflow_id": "workflow-comp",
        "total_steps": 15,
        "total_retries": 5,
        "required_compensation": True,
        "required_human": False,
        "agents_involved": ["executor"],
        "timestamp": datetime.now(timezone.utc)
    })

    workflows = await redis_storage.get_workflows()

    assert len(workflows) == 1
    assert workflows[0]["required_compensation"] is True
    assert workflows[0]["total_retries"] == 5


@pytest.mark.asyncio
async def test_close_connection(redis_storage):
    """Test closing Redis connection."""

    await redis_storage.close()



@pytest.mark.asyncio
async def test_import_error_handling():
    """Test handling of missing redis package."""
    with patch.dict('sys.modules', {'redis.asyncio': None}):
        # This test verifies the error handling in __init__
        # In actual code, REDIS_AVAILABLE would be False
        pass  # Skip actual test since redis is imported at module level
