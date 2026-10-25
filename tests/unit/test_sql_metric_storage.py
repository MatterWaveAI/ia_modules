"""
Unit tests for SQL metric storage.

Tests SQLMetricStorage with SQLite backend.
"""

import pytest
from datetime import datetime, timedelta, timezone
from ia_modules.reliability.sql_metric_storage import SQLMetricStorage
from nexusql import DatabaseManager, ConnectionConfig, DatabaseType
from ia_modules.database import MIGRATIONS_DIR


@pytest.mark.asyncio
class TestSQLMetricStorage:
    """Test SQLMetricStorage class."""

    @pytest.fixture
    async def db_manager(self):
        """Create DatabaseManager with SQLite in-memory."""
        config = ConnectionConfig(
            database_type=DatabaseType.SQLITE,
            database_url="sqlite://:memory:"
        )
        db = DatabaseManager(config)
        db.connect()
        # Initialize with migrations to create tables
        await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
        yield db
        await db.close()

    async def test_storage_creation(self, db_manager):
        """SQLMetricStorage can be created."""
        storage = SQLMetricStorage(db_manager)

        assert storage.db == db_manager

    async def test_initialize(self, db_manager):
        """Can initialize storage."""
        SQLMetricStorage(db_manager)

        


    async def test_record_step(self, db_manager):
        """Can record step metrics."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_step({
            "agent": "planner",
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        steps = await storage.get_steps()
        assert len(steps) == 1
        assert steps[0]["agent"] == "planner"

    async def test_record_workflow(self, db_manager):
        """Can record workflow metrics."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_workflow({
            "workflow_id": "wf-123",
            "steps": 5,
            "retries": 1,
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        workflows = await storage.get_workflows()
        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "wf-123"

    async def test_get_steps_by_agent(self, db_manager):
        """Can filter steps by agent."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_step({"agent": "agent1", "success": True})
        await storage.record_step({"agent": "agent2", "success": True})

        agent1_steps = await storage.get_steps(agent="agent1")
        assert len(agent1_steps) == 1
        assert agent1_steps[0]["agent"] == "agent1"

    async def test_get_steps_by_time(self, db_manager):
        """Can filter steps by time."""
        storage = SQLMetricStorage(db_manager)
        

        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        new_time = datetime.now(timezone.utc)

        await storage.record_step({"agent": "agent1", "success": True, "timestamp": old_time.isoformat()})
        await storage.record_step({"agent": "agent2", "success": True, "timestamp": new_time.isoformat()})

        since = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_steps = await storage.get_steps(since=since)

        assert len(recent_steps) == 1
        assert recent_steps[0]["agent"] == "agent2"

    async def test_record_slo_measurement_mtte(self, db_manager):
        """Can record MTTE measurements."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_slo_measurement(
            measurement_type="mtte",
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            duration_ms=1500,
            success=True
        )

        measurements = await storage.get_slo_measurements("mtte")
        assert len(measurements) == 1
        assert measurements[0]["duration_ms"] == 1500

    async def test_record_slo_measurement_rsr(self, db_manager):
        """Can record RSR measurements."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_slo_measurement(
            measurement_type="rsr",
            thread_id="thread-123",
            replay_mode="strict",
            success=True
        )

        measurements = await storage.get_slo_measurements("rsr")
        assert len(measurements) == 1
        assert measurements[0]["replay_mode"] == "strict"

    async def test_get_slo_measurements_by_time(self, db_manager):
        """Can filter SLO measurements by time."""
        storage = SQLMetricStorage(db_manager)
        

        # Record measurement
        await storage.record_slo_measurement(
            measurement_type="mtte",
            thread_id="thread-123",
            duration_ms=1000,
            success=True
        )

        # Get recent measurements
        since = datetime.now(timezone.utc) - timedelta(minutes=1)
        measurements = await storage.get_slo_measurements("mtte", since=since)

        assert len(measurements) == 1

    async def test_close(self, db_manager):
        """Can close storage connection."""
        storage = SQLMetricStorage(db_manager)

        await storage.close()


    async def test_step_with_mode_violation(self, db_manager):
        """Can record step with mode violation."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_step({
            "agent": "executor",
            "success": True,
            "mode": "explore",
            "declared_mode": "execute",
            "mode_violation": True
        })

        steps = await storage.get_steps()
        assert steps[0]["mode_violation"] is True

    async def test_workflow_with_human_intervention(self, db_manager):
        """Can record workflow requiring human intervention."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_workflow({
            "workflow_id": "wf-456",
            "steps": 3,
            "retries": 0,
            "success": True,
            "required_human": True
        })

        workflows = await storage.get_workflows()
        assert workflows[0]["required_human"] is True

    async def test_multiple_steps_ordering(self, db_manager):
        """Steps are returned in chronological order."""
        storage = SQLMetricStorage(db_manager)
        

        # Record in specific order
        time1 = datetime.now(timezone.utc)
        time2 = time1 + timedelta(seconds=1)
        time3 = time2 + timedelta(seconds=1)

        await storage.record_step({"agent": "agent1", "success": True, "timestamp": time1.isoformat()})
        await storage.record_step({"agent": "agent2", "success": True, "timestamp": time3.isoformat()})
        await storage.record_step({"agent": "agent3", "success": True, "timestamp": time2.isoformat()})

        steps = await storage.get_steps()

        # Should be in chronological order
        assert len(steps) == 3
        assert steps[0]["agent"] == "agent1"
        assert steps[1]["agent"] == "agent3"
        assert steps[2]["agent"] == "agent2"

    async def test_slo_measurement_with_error(self, db_manager):
        """Can record failed SLO measurement with error."""
        storage = SQLMetricStorage(db_manager)
        

        await storage.record_slo_measurement(
            measurement_type="rsr",
            thread_id="thread-123",
            replay_mode="strict",
            success=False,
            error="Tool not available"
        )

        measurements = await storage.get_slo_measurements("rsr")
        assert measurements[0]["success"] is False
        assert measurements[0]["error"] == "Tool not available"
