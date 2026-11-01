"""
Tests for the ia-runner entrypoint against a real PostgreSQL.

The same fail-then-retry story as tests/unit/test_runner_entrypoint.py
(see its STEPS_SOURCE for the pipeline shape), but with the checkpoints
landing in actual Postgres via nexusql — the storage the runner image
uses in the cluster (platform rule: real Postgres, never SQLite).

Requires a PostgreSQL server. Follows the repo's pattern for
DB-backed tests (cf. test_redis_metric_storage.py): the server is
probed once at import, and the whole module skips when it is not
reachable. Point TEST_POSTGRESQL_URL at the server; tests/
docker-compose.test.yml brings one up on port 15432.
"""

import json
import os
import textwrap

import pytest

pytest.importorskip("psycopg2")

from ia_modules.runner import EXIT_FAILED, EXIT_OK, runner_main

_TEST_DB_URL = os.environ.get(
    "TEST_POSTGRESQL_URL",
    "postgresql://testuser:testpass@localhost:15432/ia_modules_test",
)


def _postgres_available() -> bool:
    """Probe the server once, synchronously — no event loop issues."""
    import psycopg2

    try:
        conn = psycopg2.connect(_TEST_DB_URL, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


POSTGRES_AVAILABLE = _postgres_available()

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.integration,
    pytest.mark.skipif(
        not POSTGRES_AVAILABLE,
        reason="PostgreSQL server not running (set TEST_POSTGRESQL_URL)"
    ),
]

# Same steps as the unit suite: echo stamps a marker, verify is the second
# hop the resume lands on. SMOKE_FAIL_STEP names the step that should raise,
# so the first attempt can die AFTER echo has checkpointed.
STEPS_SOURCE = textwrap.dedent('''
    """Test steps for the ia-runner PostgreSQL tests."""
    import os
    from typing import Any, Dict

    from ia_modules.pipeline.core import Step


    def _fail_if_injected(step):
        """Raise when SMOKE_FAIL_STEP names this step (kill switch)."""
        if os.environ.get("SMOKE_FAIL_STEP") == step.name:
            raise RuntimeError(f"injected test failure (SMOKE_FAIL_STEP={step.name})")


    class EchoStep(Step):
        """Stamp SMOKE_MARKER into the data."""

        async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
            _fail_if_injected(self)
            result = dict(data)
            result["echo_marker"] = os.environ.get("SMOKE_MARKER", "unset")
            return result


    class VerifyStep(Step):
        """Pass-through step: gives the flow a second hop to resume across."""

        async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
            _fail_if_injected(self)
            result = dict(data)
            result["verify_done"] = True
            return result
''')

PIPELINE_YAML = """\
name: runner_pg_test
version: "1.0.0"
description: Two-step pipeline for the ia-runner PostgreSQL resume test

execution:
  engine: ia_modules
  timeout: 60
  max_retries: 1

steps:
  - id: echo
    name: Echo Marker
    module: runner_pg_steps
    step_class: EchoStep
    config:
      description: Stamp SMOKE_MARKER into the data

  - id: verify
    name: Verify Passthrough
    module: runner_pg_steps
    step_class: VerifyStep
    config:
      description: Second hop

flow:
  start_at: echo

  paths:
    - from: echo
      to: verify
      condition:
        type: always

    - from: verify
      to: end_with_success
      condition:
        type: always

error_handling:
  on_step_failure: stop
"""


def _write_bundle(work_dir):
    """Write the steps module and pipeline YAML; returns the pipeline path."""
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "runner_pg_steps.py").write_text(STEPS_SOURCE, encoding="utf-8")
    path = work_dir / "runner_pg_test.yaml"
    path.write_text(PIPELINE_YAML, encoding="utf-8")
    return path


def _checkpoint_rows(thread_id):
    """The checkpoint rows nexusql stored for a run, newest first."""
    from nexusql import DatabaseManager

    db = DatabaseManager(_TEST_DB_URL)
    db.connect()
    try:
        return db.execute(
            "SELECT checkpoint_id, step_name, step_index "
            "FROM pipeline_checkpoints WHERE thread_id = :thread_id "
            "ORDER BY timestamp DESC",
            {"thread_id": thread_id},
        )
    finally:
        db.disconnect()


def _delete_checkpoints(thread_id):
    """Clean up a run's checkpoints so the test database stays tidy."""
    from nexusql import DatabaseManager

    db = DatabaseManager(_TEST_DB_URL)
    db.connect()
    try:
        db.execute(
            "DELETE FROM pipeline_checkpoints WHERE thread_id = :thread_id",
            {"thread_id": thread_id},
        )
    finally:
        db.disconnect()


def test_retry_resumes_from_postgres(tmp_path, monkeypatch):
    """Fail after the first checkpoint; the retry must resume, not rerun."""
    import uuid

    run_id = f"runner-pg-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("IA_MODULES_DB_URL", _TEST_DB_URL)
    monkeypatch.setenv("IA_RUN_ID", run_id)

    path = _write_bundle(tmp_path)
    output = tmp_path / "out" / "attempt2.json"

    try:
        # Attempt 1: echo stamps run-a and checkpoints, verify fails
        monkeypatch.setenv("SMOKE_FAIL_STEP", "verify")
        monkeypatch.setenv("SMOKE_MARKER", "run-a")
        failed = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ])
        assert failed == EXIT_FAILED

        rows = _checkpoint_rows(run_id)
        assert len(rows) == 1
        assert rows[0]["step_name"] == "echo"

        # Attempt 2: same run id, different marker, no injected failure
        monkeypatch.delenv("SMOKE_FAIL_STEP")
        monkeypatch.setenv("SMOKE_MARKER", "run-b")
        resumed = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
            '--output', str(output),
        ])
        assert resumed == EXIT_OK

        # The first attempt's marker survives: echo was restored from the
        # checkpoint, not rerun. run-b here would mean resume is broken.
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["output"]["echo_marker"] == "run-a"
        assert result["output"]["verify_done"] is True

        rows = _checkpoint_rows(run_id)
        assert len(rows) == 2
        assert rows[0]["step_name"] == "verify"
        assert rows[1]["step_name"] == "echo"
    finally:
        _delete_checkpoints(run_id)


def test_storage_failure_exits_failed(tmp_path, monkeypatch):
    """A Postgres URL that cannot connect fails the run (exit 1)."""
    monkeypatch.setenv(
        "IA_MODULES_DB_URL", "postgresql://no:such@127.0.0.1:1/none"
    )
    monkeypatch.delenv("IA_RUN_ID", raising=False)

    path = _write_bundle(tmp_path)
    code = runner_main([
        '--pipeline', str(path),
        '--working-dir', str(tmp_path),
    ])
    assert code == EXIT_FAILED
