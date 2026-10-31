"""
Tests for the ia-runner entrypoint (ia_modules/runner).

Covers the runner contract end to end without external services:
- pipeline loading: YAML and JSON bundle files, usage errors
- exit codes: 0 success, 1 pipeline failure, 2 usage error
- resume-from-checkpoint over SQLCheckpointer with a local SQLite file:
  a failed first attempt leaves a checkpoint; the retried run with the
  same IA_RUN_ID resumes (first attempt's marker survives) instead of
  rerunning.

The PostgreSQL flavor of the same story lives in
tests/integration/test_runner_postgres.py.
"""

import json
import textwrap

import pytest

from ia_modules.runner import (
    EXIT_FAILED,
    EXIT_OK,
    EXIT_USAGE,
    RunnerUsageError,
    build_db_url_from_env,
    create_parser,
    load_pipeline_config,
    runner_main,
)

# The steps module written into each test's working directory. Same content
# (and same module name) everywhere: EchoStep stamps a marker, VerifyStep
# gives the flow a second hop to resume across — the same shape the Docker
# smoke pipeline uses. SMOKE_FAIL_STEP names the step that should raise,
# so the first attempt can die AFTER echo has checkpointed.
STEPS_SOURCE = textwrap.dedent('''
    """Test steps for the ia-runner entrypoint tests."""
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

PIPELINE_DICT = {
    "name": "runner_test",
    "version": "1.0.0",
    "description": "Two-step smoke pipeline for entrypoint tests",
    "execution": {
        "engine": "ia_modules",
        "timeout": 60,
        "max_retries": 1,
    },
    "steps": [
        {
            "id": "echo",
            "name": "Echo Marker",
            "module": "runner_test_steps",
            "step_class": "EchoStep",
            "config": {"description": "Stamp SMOKE_MARKER into the data"},
        },
        {
            "id": "verify",
            "name": "Verify Passthrough",
            "module": "runner_test_steps",
            "step_class": "VerifyStep",
            "config": {"description": "Second hop"},
        },
    ],
    "flow": {
        "start_at": "echo",
        "paths": [
            {"from": "echo", "to": "verify", "condition": {"type": "always"}},
            {"from": "verify", "to": "end_with_success", "condition": {"type": "always"}},
        ],
    },
    "error_handling": {"on_step_failure": "stop"},
}


def write_pipeline_bundle(work_dir, pipeline_dict=None, fmt="yaml"):
    """Write the steps module and pipeline file; returns the pipeline path."""
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "runner_test_steps.py").write_text(STEPS_SOURCE, encoding="utf-8")
    config = pipeline_dict if pipeline_dict is not None else PIPELINE_DICT

    if fmt == "yaml":
        import yaml
        path = work_dir / "runner_test.yaml"
        path.write_text(yaml.dump(config), encoding="utf-8")
    else:
        path = work_dir / "runner_test.json"
        path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture
def no_runner_env(monkeypatch):
    """A clean env: no storage, no run id, no smoke switches leaking in."""
    for key in (
        "IA_RUN_ID",
        "IA_MODULES_DB_URL",
        "IA_MODULES_DB_HOST",
        "IA_MODULES_DB_PORT",
        "IA_MODULES_DB_USER",
        "IA_MODULES_DB_PASSWORD",
        "IA_MODULES_DB_NAME",
        "SMOKE_FAIL_STEP",
        "SMOKE_MARKER",
    ):
        monkeypatch.delenv(key, raising=False)


class TestArgumentParsing:
    """Test command-line argument parsing"""

    def test_parser_prog(self):
        """Test parser is created with the runner's prog name"""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == 'ia-runner'

    def test_missing_pipeline_arg_exits_usage(self, no_runner_env, capsys):
        """Test invoking with no --pipeline is a usage error, not a crash"""
        assert runner_main([]) == EXIT_USAGE
        assert "--pipeline" in capsys.readouterr().err

    def test_full_invocation_parsing(self):
        """Test all flags parse into the expected attributes"""
        args = create_parser().parse_args([
            '--pipeline', 'chat_pipeline.yaml',
            '--input', 'input.json',
            '--working-dir', '/work',
            '--output', '/out/result.json',
        ])
        assert args.pipeline == 'chat_pipeline.yaml'
        assert args.input == 'input.json'
        assert args.working_dir == '/work'
        assert args.output == '/out/result.json'
        assert args.version is False

    def test_version_flag(self):
        """Test --version parses"""
        assert create_parser().parse_args(['--version']).version is True


class TestPipelineLoading:
    """Test load_pipeline_config across the bundle schema"""

    def test_yaml_bundle_loads(self, tmp_path):
        """Test a chat_pipeline-style YAML file loads into a dict"""
        path = write_pipeline_bundle(tmp_path, fmt="yaml")
        config = load_pipeline_config(str(path))
        assert config["name"] == "runner_test"
        assert config["execution"]["engine"] == "ia_modules"
        assert config["flow"]["start_at"] == "echo"
        assert config["error_handling"] == {"on_step_failure": "stop"}

    def test_json_bundle_loads(self, tmp_path):
        """Test the same schema loads from JSON"""
        path = write_pipeline_bundle(tmp_path, fmt="json")
        config = load_pipeline_config(str(path))
        assert config["steps"][0]["step_class"] == "EchoStep"

    def test_missing_file(self, tmp_path):
        """Test a nonexistent pipeline file is a usage error"""
        with pytest.raises(RunnerUsageError, match="not found"):
            load_pipeline_config(str(tmp_path / "nope.yaml"))

    def test_unparsable_yaml(self, tmp_path):
        """Test broken YAML is a usage error"""
        path = tmp_path / "broken.yaml"
        path.write_text("steps: [unclosed", encoding="utf-8")
        with pytest.raises(RunnerUsageError, match="Cannot parse"):
            load_pipeline_config(str(path))

    def test_unsupported_extension(self, tmp_path):
        """Test a non-YAML/JSON file is a usage error"""
        path = tmp_path / "pipeline.toml"
        path.write_text("name = 'x'", encoding="utf-8")
        with pytest.raises(RunnerUsageError, match="Unsupported"):
            load_pipeline_config(str(path))

    def test_missing_required_fields(self, tmp_path):
        """Test a mapping without name/steps/flow is a usage error"""
        path = tmp_path / "thin.yaml"
        path.write_text("description: no steps here\n", encoding="utf-8")
        with pytest.raises(RunnerUsageError, match="missing required field"):
            load_pipeline_config(str(path))

    def test_missing_start_at(self, tmp_path):
        """Test a flow without start_at is a usage error"""
        path = tmp_path / "flowless.yaml"
        path.write_text(
            "name: x\nsteps: []\nflow:\n  paths: []\n", encoding="utf-8"
        )
        with pytest.raises(RunnerUsageError, match="start_at"):
            load_pipeline_config(str(path))


class TestDbUrlFromEnv:
    """Test IA_MODULES_DB_* env handling"""

    def test_url_wins(self, monkeypatch):
        """Test IA_MODULES_DB_URL is used as-is"""
        monkeypatch.setenv("IA_MODULES_DB_URL", "postgresql://u:p@db:5432/x")
        monkeypatch.setenv("IA_MODULES_DB_HOST", "ignored")
        assert build_db_url_from_env() == "postgresql://u:p@db:5432/x"

    def test_parts_build_url(self, monkeypatch):
        """Test host/port/user/password/name assemble into a URL"""
        monkeypatch.delenv("IA_MODULES_DB_URL", raising=False)
        monkeypatch.setenv("IA_MODULES_DB_HOST", "db.internal")
        monkeypatch.setenv("IA_MODULES_DB_PORT", "6543")
        monkeypatch.setenv("IA_MODULES_DB_USER", "runner")
        monkeypatch.setenv("IA_MODULES_DB_PASSWORD", "secret")
        monkeypatch.setenv("IA_MODULES_DB_NAME", "ia_modules")
        assert build_db_url_from_env() == \
            "postgresql://runner:secret@db.internal:6543/ia_modules"

    def test_parts_without_password(self, monkeypatch):
        """Test the password section is omitted when empty"""
        monkeypatch.delenv("IA_MODULES_DB_URL", raising=False)
        monkeypatch.setenv("IA_MODULES_DB_NAME", "ia_modules")
        monkeypatch.delenv("IA_MODULES_DB_HOST", raising=False)
        assert build_db_url_from_env() == \
            "postgresql://postgres@localhost:5432/ia_modules"

    def test_no_config_returns_none(self, monkeypatch):
        """Test no storage env at all means no storage"""
        for key in (
            "IA_MODULES_DB_URL", "IA_MODULES_DB_HOST", "IA_MODULES_DB_NAME"
        ):
            monkeypatch.delenv(key, raising=False)
        assert build_db_url_from_env() is None


class TestExitCodes:
    """Test the exit code contract against real (tiny) pipelines"""

    def test_version_exits_zero(self, no_runner_env, capsys):
        """Test --version prints the version and exits 0"""
        assert runner_main(['--version']) == EXIT_OK
        assert capsys.readouterr().out.strip()

    def test_missing_pipeline_file_exits_usage(self, no_runner_env, tmp_path):
        """Test a missing --pipeline file is exit code 2"""
        code = runner_main([
            '--pipeline', str(tmp_path / "missing.yaml"),
        ])
        assert code == EXIT_USAGE

    def test_successful_run_exits_zero(self, no_runner_env, tmp_path):
        """Test a green pipeline exits 0 and writes the result JSON"""
        path = write_pipeline_bundle(tmp_path)
        output = tmp_path / "out" / "result.json"

        code = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
            '--output', str(output),
        ])

        assert code == EXIT_OK
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["output"]["echo_marker"] == "unset"
        assert result["output"]["verify_done"] is True

    def test_json_pipeline_exits_zero(self, no_runner_env, tmp_path):
        """Test the same pipeline from JSON also exits 0"""
        path = write_pipeline_bundle(tmp_path, fmt="json")
        assert runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ]) == EXIT_OK

    def test_step_failure_exits_failed(self, no_runner_env, monkeypatch, tmp_path):
        """Test a step that raises makes the run exit 1"""
        monkeypatch.setenv("SMOKE_FAIL_STEP", "verify")
        path = write_pipeline_bundle(tmp_path)

        code = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ])

        assert code == EXIT_FAILED

    def test_run_without_storage_warns_but_succeeds(
        self, no_runner_env, monkeypatch, tmp_path, caplog
    ):
        """Test no IA_MODULES_DB_* still runs the pipeline, with a warning"""
        path = write_pipeline_bundle(tmp_path)
        with caplog.at_level("WARNING", logger="ia_modules.runner"):
            code = runner_main([
                '--pipeline', str(path),
                '--working-dir', str(tmp_path),
            ])
        assert code == EXIT_OK
        assert any("NOT" in r.message and "checkpoint" in r.message
                   for r in caplog.records)

    def test_actor_defaults_to_the_service_identity(
        self, no_runner_env, tmp_path, caplog
    ):
        """No IA_RUN_ACTOR: the run names its service identity, not a person"""
        path = write_pipeline_bundle(tmp_path)
        with caplog.at_level("INFO", logger="ia_modules.runner"):
            code = runner_main([
                '--pipeline', str(path),
                '--working-dir', str(tmp_path),
            ])
        assert code == EXIT_OK
        assert any("svc:ia-runner" in r.message and "actor" in r.message
                   for r in caplog.records)

    def test_actor_env_names_the_triggering_user(
        self, no_runner_env, monkeypatch, tmp_path, caplog
    ):
        """IA_RUN_ACTOR carries the console session's subject claim through"""
        monkeypatch.setenv("IA_RUN_ACTOR", "usr_dave")
        path = write_pipeline_bundle(tmp_path)
        with caplog.at_level("INFO", logger="ia_modules.runner"):
            code = runner_main([
                '--pipeline', str(path),
                '--working-dir', str(tmp_path),
            ])
        assert code == EXIT_OK
        assert any("usr_dave" in r.message and "actor" in r.message
                   for r in caplog.records)


class TestResumeFromCheckpoint:
    """Test checkpoint-resume on retry over SQLCheckpointer + SQLite file"""

    @pytest.fixture
    def sqlite_db_url(self, tmp_path, monkeypatch):
        """A file-backed SQLite database URL in IA_MODULES_DB_URL"""
        url = f"sqlite:///{tmp_path / 'runner_state.db'}"
        monkeypatch.setenv("IA_MODULES_DB_URL", url)
        return url

    def _count_checkpoints(self, db_url: str, thread_id: str) -> int:
        from nexusql import DatabaseManager

        db = DatabaseManager(db_url)
        db.connect()
        try:
            rows = db.fetch_all(
                "SELECT checkpoint_id FROM pipeline_checkpoints "
                "WHERE thread_id = :thread_id",
                {"thread_id": thread_id},
            )
            return len(rows)
        finally:
            db.disconnect()

    def test_retry_resumes_instead_of_rerunning(
        self, no_runner_env, monkeypatch, tmp_path, sqlite_db_url
    ):
        """Fail after the first checkpoint, retry with the same run id.

        The retried run must pick up the first attempt's marker from the
        checkpoint — if it says run-b, echo reran and resume is broken.
        """
        monkeypatch.setenv("IA_RUN_ID", "resume-unit-1")
        path = write_pipeline_bundle(tmp_path)
        output = tmp_path / "out" / "attempt2.json"

        # Attempt 1: echo stamps run-a and checkpoints, verify fails
        monkeypatch.setenv("SMOKE_FAIL_STEP", "verify")
        monkeypatch.setenv("SMOKE_MARKER", "run-a")
        failed = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ])
        assert failed == EXIT_FAILED
        assert self._count_checkpoints(sqlite_db_url, "resume-unit-1") == 1

        # Attempt 2: same run id, different marker, no injected failure
        monkeypatch.delenv("SMOKE_FAIL_STEP")
        monkeypatch.setenv("SMOKE_MARKER", "run-b")
        resumed = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
            '--output', str(output),
        ])
        assert resumed == EXIT_OK

        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["output"]["echo_marker"] == "run-a"
        assert result["output"]["verify_done"] is True

        # echo's checkpoint from attempt 1 + verify's from the resumed run
        assert self._count_checkpoints(sqlite_db_url, "resume-unit-1") == 2

    def test_fresh_run_id_starts_over(
        self, no_runner_env, monkeypatch, tmp_path, sqlite_db_url
    ):
        """A different run id does not see the previous run's checkpoint"""
        monkeypatch.setenv("IA_RUN_ID", "resume-unit-2")
        monkeypatch.setenv("SMOKE_MARKER", "run-a")
        path = write_pipeline_bundle(tmp_path)
        output = tmp_path / "out" / "fresh.json"

        # Attempt 1 fails, leaving a checkpoint under resume-unit-2
        monkeypatch.setenv("SMOKE_FAIL_STEP", "verify")
        assert runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ]) == EXIT_FAILED

        # A new run id runs from the top, not from the old checkpoint
        monkeypatch.delenv("SMOKE_FAIL_STEP")
        monkeypatch.setenv("IA_RUN_ID", "resume-unit-3")
        assert runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
            '--output', str(output),
        ]) == EXIT_OK

        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["output"]["echo_marker"] == "run-a"
        assert self._count_checkpoints(sqlite_db_url, "resume-unit-3") == 2

    def test_completed_run_id_is_idempotent(
        self, no_runner_env, monkeypatch, tmp_path, sqlite_db_url
    ):
        """Retrying an already-completed run id exits 0 without new steps"""
        monkeypatch.setenv("IA_RUN_ID", "resume-unit-4")
        monkeypatch.setenv("SMOKE_MARKER", "run-a")
        path = write_pipeline_bundle(tmp_path)
        output = tmp_path / "out" / "first.json"

        assert runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
            '--output', str(output),
        ]) == EXIT_OK
        assert self._count_checkpoints(sqlite_db_url, "resume-unit-4") == 2

        # Retry of the completed run: resumes, sees the pipeline complete
        monkeypatch.setenv("SMOKE_MARKER", "run-b")
        retry = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ])
        assert retry == EXIT_OK
        assert self._count_checkpoints(sqlite_db_url, "resume-unit-4") == 2

    def test_bad_storage_config_exits_failed(
        self, no_runner_env, monkeypatch, tmp_path
    ):
        """A storage URL that cannot initialize fails the run (exit 1)"""
        monkeypatch.setenv("IA_MODULES_DB_URL", "postgresql://no:such@127.0.0.1:1/none")
        path = write_pipeline_bundle(tmp_path)

        code = runner_main([
            '--pipeline', str(path),
            '--working-dir', str(tmp_path),
        ])

        assert code == EXIT_FAILED
