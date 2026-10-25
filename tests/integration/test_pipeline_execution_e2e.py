"""
End-to-end pipeline execution tests using ia_modules library directly.

Tests the full execution flow: GraphPipelineRunner with real steps,
ExecutionTracker with database persistence, and step-level tracking.
"""

import pytest
import asyncio
import json
import uuid
from pathlib import Path

from nexusql import DatabaseManager
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.execution_tracker import ExecutionTracker
from ia_modules.pipeline.core import ExecutionContext, Step
from ia_modules.database import MIGRATIONS_DIR


# ---------------------------------------------------------------------------
# Test step classes
# ---------------------------------------------------------------------------

class AddPrefixStep(Step):
    """Adds a prefix to text"""
    async def run(self, data: dict) -> dict:
        text = data.get("text", "")
        prefix = self.config.get("prefix", "PROCESSED")
        await asyncio.sleep(0.1)
        return {"text": f"{prefix}_{text}"}


class UppercaseStep(Step):
    """Uppercases text"""
    async def run(self, data: dict) -> dict:
        text = data.get("text", "")
        await asyncio.sleep(0.1)
        return {"text": text.upper()}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipelines_dir():
    return Path(__file__).parent.parent / "pipelines"


@pytest.fixture
async def db_manager(tmp_path):
    """Temporary SQLite database with schema applied"""
    db_path = tmp_path / "test_e2e.db"
    db = DatabaseManager(f"sqlite:///{db_path}")
    await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
    yield db
    await db.close()


@pytest.fixture
def services(db_manager):
    """ServiceRegistry with execution tracker"""
    registry = ServiceRegistry()
    tracker = ExecutionTracker(db_manager)
    registry.register("execution_tracker", tracker)
    return registry


@pytest.fixture
def runner(services):
    return GraphPipelineRunner(services)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pipeline_config(name, steps, connections=None):
    """Build a pipeline config dict from step definitions."""
    flow_paths = []
    if connections:
        for conn in connections:
            flow_paths.append({
                "from_step": conn["from"],
                "to_step": conn["to"],
                "condition": {"type": "always"}
            })

    return {
        "name": name,
        "version": "1.0.0",
        "steps": steps,
        "flow": {
            "start_at": steps[0]["id"],
            "paths": flow_paths
        }
    }


def all_steps_completed(result):
    """Check that every step in the result completed successfully."""
    steps = result.get("steps", [])
    return all(s.get("status") == "completed" for s in steps)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPipelineExecutionE2E:
    """End-to-end pipeline execution with real database tracking"""

    async def test_single_step_execution(self, runner):
        """Execute a single-step pipeline and verify output"""
        config = make_pipeline_config(
            "Single Step Test",
            steps=[{
                "id": "step1",
                "name": "Uppercase",
                "step_class": "UppercaseStep",
                "module": "tests.integration.test_pipeline_execution_e2e",
                "config": {}
            }]
        )

        ctx = ExecutionContext(
            execution_id=str(uuid.uuid4()),
            pipeline_id="test-single-step"
        )

        result = await runner.run_pipeline_from_json(
            config,
            {"text": "hello"},
            execution_context=ctx
        )

        assert "output" in result
        assert all_steps_completed(result)

    async def test_multi_step_pipeline(self, runner):
        """Execute a multi-step pipeline with connections"""
        config = make_pipeline_config(
            "Multi Step Test",
            steps=[
                {
                    "id": "prefix",
                    "name": "Add Prefix",
                    "step_class": "AddPrefixStep",
                    "module": "tests.integration.test_pipeline_execution_e2e",
                    "config": {"prefix": "DATA"}
                },
                {
                    "id": "upper",
                    "name": "Uppercase",
                    "step_class": "UppercaseStep",
                    "module": "tests.integration.test_pipeline_execution_e2e",
                    "config": {}
                }
            ],
            connections=[{"from": "prefix", "to": "upper"}]
        )

        ctx = ExecutionContext(
            execution_id=str(uuid.uuid4()),
            pipeline_id="test-multi-step"
        )

        result = await runner.run_pipeline_from_json(
            config,
            {"text": "hello"},
            execution_context=ctx
        )

        assert all_steps_completed(result)
        assert len(result["steps"]) == 2

    async def test_step_executions_tracked_in_database(self, runner, db_manager):
        """Verify step execution records are persisted to the database.

        Note: GraphPipelineRunner tracks step-level executions.
        Pipeline-level execution records are created by the showcase
        app's PipelineService (not tested here).
        """
        exec_id = str(uuid.uuid4())
        config = make_pipeline_config(
            "Tracked Pipeline",
            steps=[{
                "id": "step1",
                "name": "Uppercase",
                "step_class": "UppercaseStep",
                "module": "tests.integration.test_pipeline_execution_e2e",
                "config": {}
            }]
        )

        ctx = ExecutionContext(
            execution_id=exec_id,
            pipeline_id="test-tracked"
        )

        await runner.run_pipeline_from_json(
            config,
            {"text": "track me"},
            execution_context=ctx
        )

        # Verify step execution records
        step_rows = db_manager.execute(
            "SELECT * FROM step_executions WHERE execution_id = :id",
            {"id": exec_id}
        )
        assert len(step_rows) >= 1
        assert step_rows[0]["status"] == "completed"
        assert step_rows[0]["step_name"] == "step1"

    async def test_parallel_executions_tracked_separately(self, runner, db_manager):
        """Two concurrent executions get independent step tracking"""
        config = make_pipeline_config(
            "Parallel Test",
            steps=[{
                "id": "step1",
                "name": "Uppercase",
                "step_class": "UppercaseStep",
                "module": "tests.integration.test_pipeline_execution_e2e",
                "config": {}
            }]
        )

        exec_id_1 = str(uuid.uuid4())
        exec_id_2 = str(uuid.uuid4())

        ctx1 = ExecutionContext(execution_id=exec_id_1, pipeline_id="test-parallel")
        ctx2 = ExecutionContext(execution_id=exec_id_2, pipeline_id="test-parallel")

        await asyncio.gather(
            runner.run_pipeline_from_json(config, {"text": "one"}, execution_context=ctx1),
            runner.run_pipeline_from_json(config, {"text": "two"}, execution_context=ctx2),
        )

        steps_1 = db_manager.execute(
            "SELECT * FROM step_executions WHERE execution_id = :id",
            {"id": exec_id_1}
        )
        steps_2 = db_manager.execute(
            "SELECT * FROM step_executions WHERE execution_id = :id",
            {"id": exec_id_2}
        )

        assert len(steps_1) >= 1
        assert len(steps_2) >= 1
        assert steps_1[0]["execution_id"] != steps_2[0]["execution_id"]

    async def test_failed_step_raises_error(self, runner):
        """A pipeline with a bad module import raises an error"""
        config = make_pipeline_config(
            "Failing Pipeline",
            steps=[{
                "id": "bad_step",
                "name": "Bad Step",
                "step_class": "NonExistent",
                "module": "does.not.exist",
                "config": {}
            }]
        )

        ctx = ExecutionContext(
            execution_id=str(uuid.uuid4()),
            pipeline_id="test-fail"
        )

        with pytest.raises((ImportError, Exception)):
            await runner.run_pipeline_from_json(
                config,
                {"text": "will fail"},
                execution_context=ctx
            )

    async def test_real_simple_pipeline_from_json(self, runner, pipelines_dir):
        """Execute the actual simple_pipeline from tests/pipelines/"""
        pipeline_path = pipelines_dir / "simple_pipeline" / "pipeline.json"
        if not pipeline_path.exists():
            pytest.skip("simple_pipeline not found")

        with open(pipeline_path) as f:
            config = json.load(f)

        ctx = ExecutionContext(
            execution_id=str(uuid.uuid4()),
            pipeline_id="simple-pipeline"
        )

        result = await runner.run_pipeline_from_json(
            config,
            {"topic": "testing"},
            execution_context=ctx
        )

        assert all_steps_completed(result)
        assert len(result["steps"]) == 3
