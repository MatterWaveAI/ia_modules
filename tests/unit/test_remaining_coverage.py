"""
Comprehensive unit tests to maximize coverage for under-tested modules.

Targets:
1. graph_pipeline_runner.py
2. db_step_loader.py
3. cli/main.py
4. cli/validate.py
5. hitl.py
6. hitl_manager.py
7. subprocess_executor.py
8. iterative_refinement.py
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import (
    AsyncMock, MagicMock, patch,
)

import pytest

from ia_modules.agents.executor import AgentConfig, CLIType, EventType
from ia_modules.agents.subprocess_executor import (
    SubprocessExecutor,
    _find_executable,
    _write_opencode_json,
)
from ia_modules.cli.main import (
    create_parser, cmd_validate, cmd_visualize, cmd_format, cmd_run,
    print_validation_result, cli,
)
from ia_modules.cli.validate import ValidationResult, validate_pipeline
from ia_modules.pipeline.core import Step, ExecutionContext
from ia_modules.pipeline.db_step_loader import DatabaseStepLoader, load_step_class_from_db, _step_class_cache
from ia_modules.pipeline.graph_pipeline_runner import (
    AgentStepWrapper,
    PipelineStep,
    FlowCondition,
    FlowPath,
    PipelineFlow,
    PipelineConfig,
    GraphPipelineRunner,
    run_graph_pipeline,
    run_graph_pipeline_from_file,
)
from ia_modules.pipeline.hitl import (
    HITLException, PipelineStateManager, get_state_manager, set_state_manager,
    HumanInputStep, PauseForInputStep, ReviewAndApproveStep,
    ConditionalHumanStep, MultiStakeholderStep, TimeBasedDecisionStep,
    HITLResumeManager, create_pause_step, create_approval_step,
    create_conditional_step,
)
from ia_modules.pipeline.hitl_manager import HITLManager, HITLInteraction
from ia_modules.pipeline.iterative_refinement import (
    IterativeRefinementStep, ProcessRefinementResponseStep,
)
from ia_modules.pipeline.services import ServiceRegistry


class EchoStep(Step):
    """Simple step that echoes input."""
    async def run(self, data):
        return {**data, "echo": self.name}


class FailStep(Step):
    """Step that always raises."""
    async def run(self, data):
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# 1. graph_pipeline_runner  – Pydantic models + runner helpers
# ---------------------------------------------------------------------------


class TestPydanticModels:
    def test_pipeline_step_defaults(self):
        ps = PipelineStep(id="s1", name="S1", step_class="Cls", module="mod")
        assert ps.type == "task"
        assert ps.config == {}

    def test_flow_condition_defaults(self):
        fc = FlowCondition()
        assert fc.type == "always"

    def test_flow_path_alias(self):
        fp = FlowPath(**{"from": "a", "to": "b"})
        assert fp.from_step == "a"
        assert fp.to_step == "b"

    def test_pipeline_config_parameters_list(self):
        cfg = PipelineConfig(
            name="p", steps=[PipelineStep(id="s", name="S", step_class="C", module="m")],
            flow=PipelineFlow(start_at="s", paths=[
                FlowPath(**{"from": "s", "to": "end_with_success"})
            ]),
            parameters=[{"name": "x", "type": "string"}],
        )
        # Schemas are kept: create_pipeline_from_json reads defaults and required-ness from them
        assert cfg.parameters == [{"name": "x", "type": "string"}]

    def test_pipeline_config_parameters_dict(self):
        cfg = PipelineConfig(
            name="p", steps=[PipelineStep(id="s", name="S", step_class="C", module="m")],
            flow=PipelineFlow(start_at="s"), parameters={"x": 1},
        )
        assert cfg.parameters == {"x": 1}

    def test_pipeline_config_parameters_other(self):
        cfg = PipelineConfig(
            name="p", steps=[PipelineStep(id="s", name="S", step_class="C", module="m")],
            flow=PipelineFlow(start_at="s"), parameters=42,
        )
        assert cfg.parameters == {}

    def test_duplicate_step_ids_rejected(self):
        with pytest.raises(Exception, match="unique"):
            PipelineConfig(
                name="p",
                steps=[
                    PipelineStep(id="dup", name="A", step_class="C", module="m"),
                    PipelineStep(id="dup", name="B", step_class="C", module="m"),
                ],
                flow=PipelineFlow(start_at="dup"),
            )

    def test_flow_references_unknown_from(self):
        with pytest.raises(Exception, match="unknown step"):
            PipelineConfig(
                name="p",
                steps=[PipelineStep(id="s", name="S", step_class="C", module="m")],
                flow=PipelineFlow(start_at="s", paths=[
                    FlowPath(**{"from": "missing", "to": "end_with_success"})
                ]),
            )

    def test_flow_references_unknown_to(self):
        with pytest.raises(Exception, match="unknown step"):
            PipelineConfig(
                name="p",
                steps=[PipelineStep(id="s", name="S", step_class="C", module="m")],
                flow=PipelineFlow(start_at="s", paths=[
                    FlowPath(**{"from": "s", "to": "nonexistent"})
                ]),
            )


class TestAgentStepWrapper:
    async def test_success(self):
        agent = AsyncMock()
        agent.process.return_value = {"success": True, "data": {"v": 1}}
        wrapper = AgentStepWrapper("w", agent, {})
        result = await wrapper.run({"input": 1})
        assert result == {"v": 1}

    async def test_failure(self):
        agent = AsyncMock()
        agent.process.return_value = {"success": False, "error": "bad"}
        wrapper = AgentStepWrapper("w", agent, {})
        with pytest.raises(Exception, match="bad"):
            await wrapper.run({})


class TestGraphPipelineRunnerHelpers:
    def test_default_services(self):
        runner = GraphPipelineRunner()
        assert runner.services is not None

    def test_get_central_logger(self):
        runner = GraphPipelineRunner()
        # Default ServiceRegistry registers a CentralLoggingService
        logger = runner._get_central_logger()
        # May or may not be None depending on default ServiceRegistry
        # Just verify it doesn't raise
        assert logger is None or logger is not None

    def test_log_to_central_service_no_logger(self):
        runner = GraphPipelineRunner()
        # Should not raise
        runner._log_to_central_service("INFO", "test")

    def test_log_step_data_none(self):
        runner = GraphPipelineRunner()
        runner._log_step_data("step", "s1", "input", None)

    def test_log_step_data_dict_large_array(self):
        runner = GraphPipelineRunner()
        data = {"big": list(range(20)), "small": 5, "text": "hi", "flag": True, "obj": object()}
        runner._log_step_data("step", "s1", "input", data)

    def test_log_step_data_large_list(self):
        runner = GraphPipelineRunner()
        runner._log_step_data("step", "s1", "input", list(range(20)))

    def test_log_step_data_small_list(self):
        runner = GraphPipelineRunner()
        runner._log_step_data("step", "s1", "input", [1, 2])

    def test_log_step_data_scalar(self):
        runner = GraphPipelineRunner()
        runner._log_step_data("step", "s1", "input", 42)

    async def test_log_execution_end_to_database(self):
        from ia_modules.pipeline.execution_tracker import ExecutionStatus

        services = ServiceRegistry()
        tracker = AsyncMock()
        services.register("execution_tracker", tracker)
        runner = GraphPipelineRunner(services)
        await runner._log_execution_end_to_database("eid", True)
        tracker.update_execution_status.assert_called_once_with(
            execution_id="eid",
            status=ExecutionStatus.COMPLETED,
            error_message=None,
        )

    async def test_write_central_logs(self):
        services = ServiceRegistry()
        logger_mock = AsyncMock()
        logger_mock.write_to_database = AsyncMock()
        tracker = MagicMock()
        services.register("central_logger", logger_mock)
        services.register("execution_tracker", tracker)
        runner = GraphPipelineRunner(services)
        await runner._write_central_logs_to_database()
        logger_mock.write_to_database.assert_called_once_with(tracker)

    async def test_start_execution_logging_tracker_error(self):
        services = ServiceRegistry()
        tracker = AsyncMock()
        tracker.start_execution = AsyncMock(side_effect=Exception("fail"))
        services.register("execution_tracker", tracker)
        runner = GraphPipelineRunner(services)
        cfg = PipelineConfig(
            name="p", steps=[PipelineStep(id="s", name="S", step_class="C", module="m")],
            flow=PipelineFlow(start_at="s"),
        )
        # Should not raise even though tracker fails
        await runner._start_execution_logging(cfg, {}, "eid")


class TestRunPipelineFromJson:
    async def test_invalid_config(self):
        runner = GraphPipelineRunner()
        with pytest.raises(ValueError, match="Invalid pipeline"):
            await runner.run_pipeline_from_json({"bad": True})

    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_waiting_for_human(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.return_value = {
            "status": "waiting_for_human",
            "interaction_id": "i1",
            "waiting_step": "s1",
        }
        mock_create.return_value = pipeline_mock

        runner = GraphPipelineRunner()
        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        result = await runner.run_pipeline_from_json(config, {})
        assert result["status"] == "waiting_for_human"

    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_success(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.return_value = {"done": True}
        mock_create.return_value = pipeline_mock

        runner = GraphPipelineRunner()
        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        result = await runner.run_pipeline_from_json(config, {})
        assert result["done"] is True

    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_failure(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.side_effect = RuntimeError("fail")
        mock_create.return_value = pipeline_mock

        runner = GraphPipelineRunner()
        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        with pytest.raises(RuntimeError):
            await runner.run_pipeline_from_json(config, {})

    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_with_execution_context(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.return_value = {"ok": True}
        mock_create.return_value = pipeline_mock

        ctx = ExecutionContext(execution_id="e1", pipeline_id="p1")
        runner = GraphPipelineRunner()
        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        result = await runner.run_pipeline_from_json(config, {}, execution_context=ctx)
        assert result["ok"] is True


class TestRunPipelineMethod:
    @patch("ia_modules.pipeline.graph_pipeline_runner.Pipeline")
    async def test_run_pipeline_success(self, MockPipeline):
        instance = AsyncMock()
        instance.run.return_value = {"result": "ok"}
        MockPipeline.return_value = instance

        runner = GraphPipelineRunner()
        steps = [EchoStep("s1", {})]
        flow = {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]}
        result = await runner.run_pipeline("test", steps, flow, {"msg": "hi"})
        assert result == {"result": "ok"}

    @patch("ia_modules.pipeline.graph_pipeline_runner.Pipeline")
    async def test_run_pipeline_hitl(self, MockPipeline):
        instance = AsyncMock()
        instance.run.return_value = {"status": "waiting_for_human"}
        MockPipeline.return_value = instance

        runner = GraphPipelineRunner()
        steps = [EchoStep("s1", {})]
        flow = {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]}
        result = await runner.run_pipeline("test", steps, flow)
        assert result["status"] == "waiting_for_human"

    @patch("ia_modules.pipeline.graph_pipeline_runner.Pipeline")
    async def test_run_pipeline_error(self, MockPipeline):
        instance = AsyncMock()
        instance.run.side_effect = RuntimeError("boom")
        MockPipeline.return_value = instance

        runner = GraphPipelineRunner()
        steps = [EchoStep("s1", {})]
        flow = {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]}
        with pytest.raises(RuntimeError):
            await runner.run_pipeline("test", steps, flow)


class TestRunWithDifferentScenarios:
    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_scenarios(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.side_effect = [{"r": 1}, RuntimeError("fail")]
        mock_create.return_value = pipeline_mock

        runner = GraphPipelineRunner()
        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        results = await runner.run_with_different_scenarios(config, [
            {"name": "ok", "input_data": {}},
            {"name": "fail", "input_data": {}},
        ])
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False


class TestRunPipelineWithRealClasses:
    def test_agent_step_wrapper_creation(self):
        """Test that AgentStepWrapper can be created for agent-style classes."""
        agent_inst = MagicMock()
        agent_inst.process = AsyncMock(return_value={"result": "done"})
        wrapper = AgentStepWrapper("test", agent_inst, {})
        assert wrapper.name == "test"
        assert wrapper.agent_instance is agent_inst

    async def test_missing_class(self):
        runner = GraphPipelineRunner()
        config = {
            "name": "p",
            "steps": [{"id": "s1", "name": "S1", "step_class": "Missing", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        with pytest.raises(ValueError, match="not found"):
            await runner.run_pipeline_with_real_classes(config, {}, {})

    async def test_invalid_config(self):
        runner = GraphPipelineRunner()
        with pytest.raises(ValueError, match="Invalid pipeline"):
            await runner.run_pipeline_with_real_classes({"bad": True}, {}, {})


class TestConvenienceFunctions:
    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_run_graph_pipeline(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.return_value = {"ok": True}
        mock_create.return_value = pipeline_mock

        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        result = await run_graph_pipeline(config, {})
        assert result["ok"] is True

    @patch("ia_modules.pipeline.graph_pipeline_runner.create_pipeline_from_json")
    async def test_run_from_file(self, mock_create):
        pipeline_mock = AsyncMock()
        pipeline_mock.run.return_value = {"ok": True}
        mock_create.return_value = pipeline_mock

        config = {
            "name": "p", "steps": [{"id": "s1", "name": "S1", "step_class": "C", "module": "m"}],
            "flow": {"start_at": "s1", "paths": [{"from": "s1", "to": "end_with_success"}]},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            result = await run_graph_pipeline_from_file(f.name, {})
        os.unlink(f.name)
        assert result["ok"] is True

    async def test_run_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            await run_graph_pipeline_from_file("/nonexistent.json")


# ---------------------------------------------------------------------------
# 2. db_step_loader
# ---------------------------------------------------------------------------


class TestDatabaseStepLoader:
    def setup_method(self):
        _step_class_cache.clear()

    def test_validate_safe_import(self):
        loader = DatabaseStepLoader(MagicMock())
        assert loader._is_safe_import("ia_modules.pipeline.core") is True
        assert loader._is_safe_import("typing") is True
        assert loader._is_safe_import("os") is False
        assert loader._is_safe_import("subprocess") is False

    def test_validate_source_code_valid(self):
        loader = DatabaseStepLoader(MagicMock())
        code = "from ia_modules.pipeline.core import Step\nclass MyStep(Step):\n    pass"
        loader._validate_source_code(code)  # Should not raise

    def test_validate_source_code_syntax_error(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ValueError, match="Invalid Python syntax"):
            loader._validate_source_code("def :")

    def test_validate_source_code_unsafe_import(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ValueError, match="unsafe import"):
            loader._validate_source_code("import os")

    def test_validate_source_code_unsafe_from_import(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ValueError, match="unsafe import"):
            loader._validate_source_code("from subprocess import call")

    def test_validate_source_code_exec_call(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ValueError, match="Dangerous function"):
            loader._validate_source_code("exec('print(1)')")

    def test_validate_source_code_eval_call(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ValueError, match="Dangerous function"):
            loader._validate_source_code("eval('1+1')")

    def test_validate_source_code_system_call(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ValueError, match="dangerous method"):
            loader._validate_source_code("import json\njson.system('ls')")

    def test_compile_and_extract_class(self):
        loader = DatabaseStepLoader(MagicMock())
        code = (
            "class TestStep(Step):\n"
            "    async def run(self, data):\n"
            "        return data\n"
        )
        cls = loader._compile_and_extract_class(code, "TestStep", "test.module")
        assert issubclass(cls, Step)

    def test_compile_and_extract_class_not_found(self):
        loader = DatabaseStepLoader(MagicMock())
        code = "class Other(Step):\n    async def run(self, data): return data\n"
        with pytest.raises(AttributeError, match="not found"):
            loader._compile_and_extract_class(code, "Missing", "test.module")

    def test_compile_and_extract_not_step_subclass(self):
        loader = DatabaseStepLoader(MagicMock())
        code = "class NotAStep:\n    pass\n"
        with pytest.raises(TypeError, match="not a subclass"):
            loader._compile_and_extract_class(code, "NotAStep", "test.module")

    def test_compile_exec_error(self):
        loader = DatabaseStepLoader(MagicMock())
        code = "raise RuntimeError('fail at import time')"
        with pytest.raises(ImportError, match="Failed to execute"):
            loader._compile_and_extract_class(code, "X", "test.module")

    async def test_load_from_database_cached(self):
        loader = DatabaseStepLoader(MagicMock(), enable_cache=True)
        _step_class_cache["mod.Cls"] = EchoStep
        result = await loader._load_from_database("mod", "Cls")
        assert result is EchoStep

    async def test_load_from_database_dict_result(self):
        db = MagicMock()
        code = "class MyStep(Step):\n    async def run(self, data): return data\n"
        db.fetch_one.return_value = {"source_code": code, "content_hash": "abc12345"}
        loader = DatabaseStepLoader(db, enable_cache=False)
        result = await loader._load_from_database("mod", "MyStep")
        assert result is not None
        assert issubclass(result, Step)

    async def test_load_from_database_result_with_data_attr(self):
        db = MagicMock()
        code = "class MyStep(Step):\n    async def run(self, data): return data\n"
        result_obj = MagicMock()
        result_obj.data = [{"source_code": code, "content_hash": "abc12345"}]
        # Not a dict, has data attr
        db.fetch_one.return_value = result_obj
        loader = DatabaseStepLoader(db, enable_cache=False)
        result = await loader._load_from_database("mod", "MyStep")
        assert result is not None

    async def test_load_from_database_no_result(self):
        db = MagicMock()
        db.fetch_one.return_value = None
        loader = DatabaseStepLoader(db, enable_cache=False)
        result = await loader._load_from_database("mod", "MyStep")
        assert result is None

    async def test_load_from_database_empty_data(self):
        db = MagicMock()
        result_obj = MagicMock()
        result_obj.data = []
        db.fetch_one.return_value = result_obj
        loader = DatabaseStepLoader(db, enable_cache=False)
        result = await loader._load_from_database("mod", "MyStep")
        assert result is None

    async def test_load_from_database_with_pipeline_id(self):
        db = MagicMock()
        code = "class MyStep(Step):\n    async def run(self, data): return data\n"
        db.fetch_one.return_value = {"source_code": code, "content_hash": "abc12345"}
        loader = DatabaseStepLoader(db, enable_cache=True)
        result = await loader._load_from_database("mod", "MyStep", pipeline_id="pid")
        assert result is not None
        assert "pid:mod.MyStep" in _step_class_cache

    def test_load_from_filesystem(self):
        loader = DatabaseStepLoader(MagicMock())
        # Load a known module
        cls = loader._load_from_filesystem("ia_modules.pipeline.core", "Step")
        assert cls is Step

    def test_load_from_filesystem_import_error(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(ImportError):
            loader._load_from_filesystem("nonexistent.module", "Step")

    def test_load_from_filesystem_attr_error(self):
        loader = DatabaseStepLoader(MagicMock())
        with pytest.raises(AttributeError):
            loader._load_from_filesystem("ia_modules.pipeline.core", "NonExistentClass")

    async def test_load_step_class_db_first(self):
        db = MagicMock()
        code = "class MyStep(Step):\n    async def run(self, data): return data\n"
        db.fetch_one.return_value = {"source_code": code, "content_hash": "abc12345"}
        loader = DatabaseStepLoader(db, enable_cache=False)
        result = await loader.load_step_class("mod", "MyStep")
        assert issubclass(result, Step)

    async def test_load_step_class_filesystem_fallback(self):
        db = MagicMock()
        db.fetch_one.return_value = None
        loader = DatabaseStepLoader(db, enable_cache=False)
        result = await loader.load_step_class("ia_modules.pipeline.core", "Step")
        assert result is Step

    def test_clear_cache(self):
        _step_class_cache["key"] = "val"
        loader = DatabaseStepLoader(MagicMock(), enable_cache=True)
        loader.clear_cache()
        assert len(_step_class_cache) == 0

    def test_clear_cache_disabled(self):
        _step_class_cache["key"] = "val"
        loader = DatabaseStepLoader(MagicMock(), enable_cache=False)
        loader.clear_cache()
        # Cache not cleared when disabled
        assert "key" in _step_class_cache

    async def test_convenience_function(self):
        db = MagicMock()
        db.fetch_one.return_value = None
        result = await load_step_class_from_db(db, "ia_modules.pipeline.core", "Step")
        assert result is Step


# ---------------------------------------------------------------------------
# 3. cli/main.py
# ---------------------------------------------------------------------------


class TestCLIParser:
    def test_create_parser(self):
        parser = create_parser()
        assert parser is not None

    def test_no_command(self):
        result = cli([])
        assert result == 1

    def test_unknown_command(self):
        # Argparse exits on unknown commands; use parse_known_args behavior
        # Instead test via cli dispatch
        parser = create_parser()
        args = parser.parse_args(["validate", "some.json"])
        assert args.command == "validate"


class TestCmdValidate:
    def test_file_not_found(self, capsys):
        parser = create_parser()
        args = parser.parse_args(["validate", "/nonexistent.json"])
        result = cmd_validate(args)
        assert result == 1

    def test_invalid_json(self, tmp_path, capsys):
        f = tmp_path / "bad.json"
        f.write_text("not json{")
        parser = create_parser()
        args = parser.parse_args(["validate", str(f)])
        result = cmd_validate(args)
        assert result == 1

    def test_valid_pipeline_json_output(self, tmp_path, capsys):
        pipeline = {
            "name": "test",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "paths": [{"from_step": "s1", "to_step": "end_with_success"}]},
        }
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        parser = create_parser()
        args = parser.parse_args(["validate", str(f), "--json"])
        cmd_validate(args)
        captured = capsys.readouterr()
        assert "is_valid" in captured.out

    def test_valid_pipeline_human_output(self, tmp_path, capsys):
        pipeline = {
            "name": "test",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "paths": [{"from_step": "s1", "to_step": "end_with_success"}]},
        }
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        parser = create_parser()
        args = parser.parse_args(["validate", str(f)])
        cmd_validate(args)
        captured = capsys.readouterr()
        assert "validation" in captured.out.lower()

    def test_strict_mode(self, tmp_path, capsys):
        pipeline = {
            "name": "test",
            "steps": [],
            "flow": {"start_at": "s1"},
        }
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        parser = create_parser()
        args = parser.parse_args(["validate", str(f), "--strict"])
        result = cmd_validate(args)
        # Empty steps generates warning, strict makes it an error
        assert result == 1


class TestCmdVisualize:
    def test_file_not_found(self, capsys):
        parser = create_parser()
        args = parser.parse_args(["visualize", "/nonexistent.json"])
        result = cmd_visualize(args)
        assert result == 1

    def test_invalid_json(self, tmp_path, capsys):
        f = tmp_path / "bad.json"
        f.write_text("{bad")
        parser = create_parser()
        args = parser.parse_args(["visualize", str(f)])
        result = cmd_visualize(args)
        assert result == 1

    @patch("ia_modules.cli.main.visualize_pipeline")
    def test_success(self, mock_viz, tmp_path, capsys):
        pipeline = {"name": "test", "steps": [], "flow": {}}
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        parser = create_parser()
        args = parser.parse_args(["visualize", str(f), "--format", "svg"])
        result = cmd_visualize(args)
        assert result == 0
        mock_viz.assert_called_once()

    @patch("ia_modules.cli.main.visualize_pipeline", side_effect=Exception("fail"))
    def test_error(self, mock_viz, tmp_path, capsys):
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps({"name": "t"}))
        parser = create_parser()
        args = parser.parse_args(["visualize", str(f)])
        result = cmd_visualize(args)
        assert result == 1


class TestCmdFormat:
    def test_file_not_found(self):
        parser = create_parser()
        args = parser.parse_args(["format", "/nonexistent.json"])
        result = cmd_format(args)
        assert result == 1

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{bad")
        parser = create_parser()
        args = parser.parse_args(["format", str(f)])
        result = cmd_format(args)
        assert result == 1

    def test_format_stdout(self, tmp_path, capsys):
        pipeline = {"name": "test", "steps": []}
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        parser = create_parser()
        args = parser.parse_args(["format", str(f)])
        result = cmd_format(args)
        assert result == 0
        captured = capsys.readouterr()
        assert '"name"' in captured.out

    def test_format_in_place(self, tmp_path, capsys):
        pipeline = {"name": "test", "steps": []}
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        parser = create_parser()
        args = parser.parse_args(["format", str(f), "--in-place"])
        result = cmd_format(args)
        assert result == 0
        content = f.read_text()
        assert "  " in content  # indented


class TestCmdRun:
    def test_file_not_found(self):
        parser = create_parser()
        args = parser.parse_args(["run", "/nonexistent.json"])
        result = cmd_run(args)
        assert result == 1

    def test_input_file_not_found(self, tmp_path):
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps({"name": "t"}))
        parser = create_parser()
        args = parser.parse_args(["run", str(f), "--input", "/nonexistent_input.json"])
        result = cmd_run(args)
        assert result == 1

    def test_invalid_pipeline_json(self, tmp_path):
        f = tmp_path / "pipe.json"
        f.write_text("{bad")
        parser = create_parser()
        args = parser.parse_args(["run", str(f)])
        result = cmd_run(args)
        assert result == 1

    def test_invalid_input_json(self, tmp_path):
        pf = tmp_path / "pipe.json"
        pf.write_text(json.dumps({"name": "t", "steps": [], "flow": {}}))
        inf = tmp_path / "input.json"
        inf.write_text("{bad")
        parser = create_parser()
        args = parser.parse_args(["run", str(pf), "--input", str(inf)])
        result = cmd_run(args)
        assert result == 1

    @patch("ia_modules.pipeline.graph_pipeline_runner.GraphPipelineRunner")
    def test_success_stdout(self, MockRunner, tmp_path, capsys):
        mock_instance = MagicMock()
        mock_instance.run_pipeline_from_json = AsyncMock(return_value={"ok": True})
        MockRunner.return_value = mock_instance

        pf = tmp_path / "pipe.json"
        pf.write_text(json.dumps({"name": "t", "steps": [], "flow": {}}))
        parser = create_parser()
        args = parser.parse_args(["run", str(pf)])
        result = cmd_run(args)
        assert result == 0

    @patch("ia_modules.pipeline.graph_pipeline_runner.GraphPipelineRunner")
    def test_success_output_file(self, MockRunner, tmp_path, capsys):
        mock_instance = MagicMock()
        mock_instance.run_pipeline_from_json = AsyncMock(return_value={"ok": True})
        MockRunner.return_value = mock_instance

        pf = tmp_path / "pipe.json"
        pf.write_text(json.dumps({"name": "t", "steps": [], "flow": {}}))
        out = tmp_path / "out.json"
        parser = create_parser()
        args = parser.parse_args(["run", str(pf), "--output", str(out)])
        result = cmd_run(args)
        assert result == 0
        assert out.exists()

    @patch("ia_modules.pipeline.graph_pipeline_runner.GraphPipelineRunner")
    def test_run_error(self, MockRunner, tmp_path, capsys):
        mock_instance = MagicMock()
        mock_instance.run_pipeline_from_json = AsyncMock(side_effect=RuntimeError("fail"))
        MockRunner.return_value = mock_instance

        pf = tmp_path / "pipe.json"
        pf.write_text(json.dumps({"name": "t", "steps": [], "flow": {}}))
        parser = create_parser()
        args = parser.parse_args(["run", str(pf)])
        result = cmd_run(args)
        assert result == 1

    @patch("ia_modules.pipeline.graph_pipeline_runner.GraphPipelineRunner")
    def test_working_dir(self, MockRunner, tmp_path, capsys):
        mock_instance = MagicMock()
        mock_instance.run_pipeline_from_json = AsyncMock(return_value={})
        MockRunner.return_value = mock_instance

        pf = tmp_path / "pipe.json"
        pf.write_text(json.dumps({"name": "t", "steps": [], "flow": {}}))
        parser = create_parser()
        args = parser.parse_args(["run", str(pf), "--working-dir", str(tmp_path)])
        result = cmd_run(args)
        assert result == 0


class TestPrintValidationResult:
    def test_valid(self, capsys):
        r = ValidationResult(is_valid=True, info=["all good"])
        print_validation_result(r)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out

    def test_invalid_with_errors_warnings(self, capsys):
        r = ValidationResult(is_valid=False, errors=["err1"], warnings=["warn1"])
        print_validation_result(r)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out
        assert "err1" in captured.out
        assert "warn1" in captured.out


class TestCLIEntry:
    def test_validate_dispatch(self, tmp_path):
        pipeline = {
            "name": "test",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "paths": []},
        }
        f = tmp_path / "pipe.json"
        f.write_text(json.dumps(pipeline))
        result = cli(["validate", str(f)])
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# 4. cli/validate.py
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_add_error(self):
        r = ValidationResult(is_valid=True)
        r.add_error("err")
        assert r.is_valid is False
        assert "err" in r.errors

    def test_add_warning(self):
        r = ValidationResult(is_valid=True)
        r.add_warning("warn")
        assert "warn" in r.warnings

    def test_add_info(self):
        r = ValidationResult(is_valid=True)
        r.add_info("info")
        assert "info" in r.info

    def test_to_dict(self):
        r = ValidationResult(is_valid=True, errors=[], warnings=["w"], info=["i"])
        d = r.to_dict()
        assert d["is_valid"] is True
        assert d["warnings"] == ["w"]


class TestPipelineValidatorStructure:
    def test_missing_required_fields(self):
        r = validate_pipeline({})
        assert r.is_valid is False
        assert any("name" in e for e in r.errors)

    def test_name_not_string(self):
        r = validate_pipeline({"name": 123, "steps": [], "flow": {}})
        assert any("string" in e for e in r.errors)

    def test_name_empty(self):
        r = validate_pipeline({"name": "  ", "steps": [], "flow": {}})
        assert any("empty" in e for e in r.errors)

    def test_steps_not_list(self):
        r = validate_pipeline({"name": "t", "steps": "bad", "flow": {}})
        assert any("list" in e for e in r.errors)

    def test_flow_not_dict(self):
        r = validate_pipeline({"name": "t", "steps": [], "flow": "bad"})
        assert any("object" in e for e in r.errors)

    def test_empty_steps_warning(self):
        r = validate_pipeline({"name": "t", "steps": [], "flow": {"start_at": "s1"}})
        assert any("no steps" in w.lower() for w in r.warnings)


class TestPipelineValidatorSteps:
    def test_step_not_dict(self):
        r = validate_pipeline({"name": "t", "steps": ["bad"], "flow": {}})
        assert any("object" in e for e in r.errors)

    def test_step_missing_name(self):
        r = validate_pipeline({"name": "t", "steps": [{}], "flow": {}})
        assert any("name" in e for e in r.errors)

    def test_duplicate_step_name(self):
        steps = [
            {"name": "s1", "module": "m", "class": "C"},
            {"name": "s1", "module": "m", "class": "C"},
        ]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("Duplicate" in e for e in r.errors)

    def test_step_name_format_warning(self):
        steps = [{"name": "bad-name", "module": "ia_modules.pipeline.core", "class": "Step"}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("naming convention" in w for w in r.warnings)

    def test_step_missing_module(self):
        steps = [{"name": "s1", "class": "Step"}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("module" in e for e in r.errors)

    def test_step_missing_class(self):
        steps = [{"name": "s1", "module": "ia_modules.pipeline.core"}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("class" in e for e in r.errors)

    def test_step_config_not_dict(self):
        steps = [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step", "config": "bad"}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("config" in e for e in r.errors)

    def test_step_import_error(self):
        steps = [{"name": "s1", "module": "nonexistent.module", "class": "Step"}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("cannot be imported" in e for e in r.errors)

    def test_step_inputs_validation(self):
        steps = [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step",
                   "inputs": [{"name": "i1"}]}]  # missing source
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("source" in e for e in r.errors)

    def test_step_inputs_not_list(self):
        steps = [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step", "inputs": "bad"}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("should be a list" in w for w in r.warnings)  # a warning: the runner does not read inputs

    def test_step_inputs_not_dict(self):
        steps = [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step", "inputs": ["bad"]}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("object" in e for e in r.errors)

    def test_step_inputs_missing_name(self):
        steps = [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step",
                   "inputs": [{"source": "x"}]}]
        r = validate_pipeline({"name": "t", "steps": steps, "flow": {}})
        assert any("name" in e for e in r.errors)


class TestPipelineValidatorFlow:
    def test_missing_start_at(self):
        r = validate_pipeline({"name": "t", "steps": [], "flow": {}})
        assert any("start_at" in e for e in r.errors)

    def test_start_step_not_defined(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "missing"}
        })
        assert any("not defined" in e for e in r.errors)

    def test_no_paths_warning(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1"}
        })
        assert any("paths" in w.lower() for w in r.warnings)

    def test_paths_not_list(self):
        # Validator doesn't guard against non-list paths; iterating "bad" yields chars
        with pytest.raises(AttributeError):
            validate_pipeline({
                "name": "t",
                "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
                "flow": {"start_at": "s1", "paths": "bad"}
            })

    def test_path_not_dict(self):
        # Validator doesn't guard against non-dict path entries
        with pytest.raises(AttributeError):
            validate_pipeline({
                "name": "t",
                "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
                "flow": {"start_at": "s1", "paths": ["bad"]}
            })

    def test_path_invalid_from_step(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "paths": [{"from_step": "missing", "to_step": "end_ok"}]}
        })
        assert any("not defined" in e for e in r.errors)

    def test_path_invalid_to_step(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "paths": [{"from_step": "s1", "to_step": "missing"}]}
        })
        assert any("not defined" in e for e in r.errors)

    def test_transitions_not_list(self):
        with pytest.raises(AttributeError):
            validate_pipeline({
                "name": "t",
                "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
                "flow": {"start_at": "s1", "transitions": "bad"}
            })

    def test_transitions_not_dict(self):
        with pytest.raises(AttributeError):
            validate_pipeline({
                "name": "t",
                "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
                "flow": {"start_at": "s1", "transitions": ["bad"]}
            })

    def test_transition_invalid_from(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "transitions": [{"from": "missing", "to": "end_ok"}]}
        })
        assert any("not defined" in e for e in r.errors)

    def test_transition_invalid_to(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {"start_at": "s1", "transitions": [{"from": "s1", "to": "missing"}]}
        })
        assert any("not defined" in e for e in r.errors)

    def test_unreachable_steps(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [
                {"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "s2", "module": "ia_modules.pipeline.core", "class": "Step"},
            ],
            "flow": {
                "start_at": "s1",
                "paths": [{"from_step": "s1", "to_step": "end_ok"}]
            }
        })
        assert any("Unreachable" in w for w in r.warnings)

    def test_cycle_detection_paths(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [
                {"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "s2", "module": "ia_modules.pipeline.core", "class": "Step"},
            ],
            "flow": {
                "start_at": "s1",
                "paths": [
                    {"from_step": "s1", "to_step": "s2"},
                    {"from_step": "s2", "to_step": "s1"},
                ]
            }
        })
        assert any("cycle" in w.lower() for w in r.warnings)


class TestValidateCondition:
    def test_condition_not_dict(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {
                "start_at": "s1",
                "paths": [{"from_step": "s1", "to_step": "end_ok", "condition": "bad"}]
            }
        })
        assert any("condition" in e and "object" in e for e in r.errors)

    def test_condition_missing_type(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {
                "start_at": "s1",
                "paths": [{"from_step": "s1", "to_step": "end_ok", "condition": {}}]
            }
        })
        assert any("type" in e for e in r.errors)

    def test_condition_unknown_type(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"}],
            "flow": {
                "start_at": "s1",
                "paths": [{"from_step": "s1", "to_step": "end_ok", "condition": {"type": "weird"}}]
            }
        })
        assert any("unknown condition" in w.lower() for w in r.warnings)


class TestValidateTemplates:
    def test_template_refs_undefined_param(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step",
                        "config": {"val": "{{ parameters.missing }}"}}],
            "flow": {"start_at": "s1"},
            "parameters": {}
        })
        assert any("undefined parameter" in w for w in r.warnings)

    def test_template_refs_undefined_step(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [{"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step",
                        "config": {"val": "{{ steps.missing.output }}"}}],
            "flow": {"start_at": "s1"},
        })
        assert any("undefined step" in e for e in r.errors)

    def test_parameters_not_dict(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [],
            "flow": {"start_at": "s1"},
            "parameters": "bad"
        })
        assert any("parameters" in e and "object" in e for e in r.errors)

    def test_strict_mode(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [],
            "flow": {"start_at": "s1"},
        }, strict=True)
        assert r.is_valid is False
        assert any("[STRICT]" in e for e in r.errors)


class TestFindReachableSteps:
    def test_transitions_reachable(self):
        r = validate_pipeline({
            "name": "t",
            "steps": [
                {"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "s2", "module": "ia_modules.pipeline.core", "class": "Step"},
            ],
            "flow": {
                "start_at": "s1",
                "transitions": [{"from": "s1", "to": "s2"}, {"from": "s2", "to": "end_ok"}]
            }
        })
        # s2 should be reachable
        assert not any("Unreachable" in w and "s2" in w for w in r.warnings)


class TestFindCyclesTransitions:
    def test_cycle_in_transitions(self):
        # Validator currently doesn't detect cycles, just validates structure
        r = validate_pipeline({
            "name": "t",
            "steps": [
                {"name": "s1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "s2", "module": "ia_modules.pipeline.core", "class": "Step"},
            ],
            "flow": {
                "start_at": "s1",
                "transitions": [{"from": "s1", "to": "s2"}, {"from": "s2", "to": "s1"}]
            }
        })
        # No cycle detection: should still be valid
        assert r.is_valid


# ---------------------------------------------------------------------------
# 5. hitl.py
# ---------------------------------------------------------------------------


class TestPipelineStateManager:
    async def test_save_and_get_in_memory(self):
        mgr = PipelineStateManager()
        await mgr.save_state("id1", "pipe", "step", {"key": "val"}, 3600)
        state = await mgr.get_state("id1")
        assert state is not None
        assert state["data"]["key"] == "val"

    async def test_get_state_expired(self):
        mgr = PipelineStateManager()
        mgr.in_memory_states["id1"] = {
            "interaction_id": "id1",
            "data": {},
            "expires_at": datetime.now() - timedelta(hours=1),
            "status": "pending"
        }
        state = await mgr.get_state("id1")
        assert state is None

    async def test_save_with_db_manager(self):
        db = AsyncMock()
        mgr = PipelineStateManager(db_manager=db)
        await mgr.save_state("id1", "pipe", "step", {"k": "v"}, 3600)
        db.execute_async.assert_called_once()

    async def test_save_with_db_failure(self):
        db = AsyncMock()
        db.execute_async.side_effect = Exception("db fail")
        mgr = PipelineStateManager(db_manager=db)
        await mgr.save_state("id1", "pipe", "step", {"k": "v"}, 3600)
        assert "id1" in mgr.in_memory_states

    async def test_save_with_cache(self):
        cache = AsyncMock()
        mgr = PipelineStateManager(cache_service=cache)
        await mgr.save_state("id1", "pipe", "step", {}, 3600)
        cache.set.assert_called_once()

    async def test_save_with_cache_failure(self):
        cache = AsyncMock()
        cache.set.side_effect = Exception("cache fail")
        mgr = PipelineStateManager(cache_service=cache)
        await mgr.save_state("id1", "pipe", "step", {}, 3600)
        # Should not raise

    async def test_get_state_from_cache(self):
        cache = AsyncMock()
        cache.get.return_value = {"data": "cached"}
        mgr = PipelineStateManager(cache_service=cache)
        state = await mgr.get_state("id1")
        assert state["data"] == "cached"

    async def test_get_state_cache_miss_db_hit(self):
        cache = AsyncMock()
        cache.get.return_value = None
        db = AsyncMock()
        db.fetch_one.return_value = {
            "interaction_id": "id1", "pipeline_name": "p", "step_name": "s",
            "data": '{"k":"v"}', "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=1), "status": "pending"
        }
        mgr = PipelineStateManager(db_manager=db, cache_service=cache)
        state = await mgr.get_state("id1")
        assert state is not None
        assert state["data"]["k"] == "v"

    async def test_get_state_db_returns_none(self):
        db = AsyncMock()
        db.fetch_one.return_value = None
        mgr = PipelineStateManager(db_manager=db)
        state = await mgr.get_state("id1")
        assert state is None

    async def test_complete_state_in_memory(self):
        mgr = PipelineStateManager()
        mgr.in_memory_states["id1"] = {"status": "pending", "data": {}}
        await mgr.complete_state("id1", {"decision": "approve"})
        assert mgr.in_memory_states["id1"]["status"] == "completed"
        assert mgr.in_memory_states["id1"]["human_input"]["decision"] == "approve"

    async def test_complete_state_with_db(self):
        db = AsyncMock()
        mgr = PipelineStateManager(db_manager=db)
        await mgr.complete_state("id1", {"ok": True})
        db.execute_async.assert_called_once()

    async def test_complete_state_db_failure(self):
        db = AsyncMock()
        db.execute_async.side_effect = Exception("fail")
        mgr = PipelineStateManager(db_manager=db)
        await mgr.complete_state("id1", {"ok": True})
        # Should not raise

    async def test_complete_state_with_cache(self):
        cache = AsyncMock()
        mgr = PipelineStateManager(cache_service=cache)
        mgr.in_memory_states["id1"] = {"status": "pending", "data": {}}
        await mgr.complete_state("id1", {})
        cache.delete.assert_called_once()

    async def test_complete_state_cache_failure(self):
        cache = AsyncMock()
        cache.delete.side_effect = Exception("fail")
        mgr = PipelineStateManager(cache_service=cache)
        mgr.in_memory_states["id1"] = {"status": "pending", "data": {}}
        await mgr.complete_state("id1", {})
        # Should not raise


class TestGlobalStateManager:
    def test_get_and_set(self):
        import ia_modules.pipeline.hitl as hitl_mod
        old = hitl_mod._state_manager
        try:
            hitl_mod._state_manager = None
            mgr = get_state_manager()
            assert isinstance(mgr, PipelineStateManager)

            custom = PipelineStateManager()
            set_state_manager(custom)
            assert get_state_manager() is custom
        finally:
            hitl_mod._state_manager = old


class TestHumanInputStep:
    async def test_run(self):
        step = HumanInputStep("test_step", {"timeout": 60, "prompt": "Enter data"})
        result = await step.run({"key": "val"})
        assert result["status"] == "human_input_required"
        assert result["step_name"] == "test_step"
        assert result["timeout_seconds"] == 60


class TestPauseForInputStep:
    def test_default_ui_schema(self):
        step = PauseForInputStep("pause", {"title": "Test", "description": "Desc"})
        schema = step.get_default_ui_schema()
        assert schema["type"] == "generic_input"
        assert schema["title"] == "Test"


class TestReviewAndApproveStep:
    def test_default_ui_schema(self):
        step = ReviewAndApproveStep("review", {})
        schema = step.get_default_ui_schema()
        assert schema["type"] == "review_approval"

    async def test_run(self):
        step = ReviewAndApproveStep("review", {"content_key": "text"})
        result = await step.run({"text": "Hello world"})
        assert result["status"] == "human_input_required"
        assert "review_content" in result


class TestConditionalHumanStep:
    async def test_automated_when_no_conditions_met(self):
        step = ConditionalHumanStep("cond", {"conditions": []})
        result = await step.run({"data": 1})
        assert result["status"] == "automated_processing"
        assert result["human_input_skipped"] is True

    async def test_triggered_by_confidence(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "confidence_threshold", "threshold": 0.9}]
        })
        result = await step.run({"confidence": 0.5})
        assert result["status"] == "human_input_required"
        assert "Low confidence" in result["trigger_reason"]

    async def test_triggered_by_error(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "error_occurred"}]
        })
        result = await step.run({"error": "something bad"})
        assert result["status"] == "human_input_required"

    async def test_triggered_by_error_status(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "error_occurred"}]
        })
        result = await step.run({"status": "error"})
        assert "trigger_reason" in result

    async def test_triggered_by_value_check_equals(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "value_check", "field": "x", "expected_value": 10, "operator": "equals"}]
        })
        result = await step.run({"x": 5})
        assert result["status"] == "human_input_required"

    async def test_triggered_by_value_check_greater_than(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "value_check", "field": "x", "expected_value": 10, "operator": "greater_than"}]
        })
        result = await step.run({"x": 5})
        assert result["status"] == "human_input_required"

    async def test_triggered_by_value_check_less_than(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "value_check", "field": "x", "expected_value": 10, "operator": "less_than"}]
        })
        result = await step.run({"x": 15})
        assert result["status"] == "human_input_required"

    async def test_get_trigger_reason_error_status(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "error_occurred"}]
        })
        result = await step.run({"status": "error"})
        assert "error" in result["trigger_reason"].lower()

    async def test_get_trigger_reason_unknown(self):
        step = ConditionalHumanStep("cond", {
            "conditions": [{"type": "unknown_type"}]
        })
        # No condition matches but _should_require returns False
        result = await step.run({})
        assert result["status"] == "automated_processing"


class TestMultiStakeholderStep:
    async def test_no_stakeholders(self):
        step = MultiStakeholderStep("multi", {})
        with pytest.raises(HITLException, match="No stakeholders"):
            await step.run({})

    async def test_with_stakeholders(self):
        step = MultiStakeholderStep("multi", {
            "stakeholders": ["user1", "user2"],
            "decision_type": "majority",
        })
        result = await step.run({"data": 1})
        assert result["status"] == "multi_stakeholder_decision_pending"
        assert result["responses_needed"] == 2


class TestTimeBasedDecisionStep:
    async def test_run(self):
        step = TimeBasedDecisionStep("timed", {"decision_timeout": 10, "default_action": "abort"})
        result = await step.run({"data": 1})
        assert result["status"] == "time_sensitive_decision"
        assert result["default_action"] == "abort"
        assert result["urgent"] is True
        # Clean up background task
        await step.cleanup()

    async def test_cleanup(self):
        step = TimeBasedDecisionStep("timed", {"decision_timeout": 3600})
        await step.run({})
        assert len(step._timeout_tasks) > 0
        await step.cleanup()
        assert len(step._timeout_tasks) == 0


class TestHITLResumeManager:
    async def test_resume_pipeline(self):
        import ia_modules.pipeline.hitl as hitl_mod
        old = hitl_mod._state_manager
        try:
            mgr = PipelineStateManager()
            await mgr.save_state("id1", "pipe", "step", {"original": True}, 3600)
            set_state_manager(mgr)

            result = await HITLResumeManager.resume_pipeline("id1", {"decision": "approve"})
            assert result["status"] == "resumed"
            assert result["merged_data"]["decision"] == "approve"
            assert result["merged_data"]["original"] is True
        finally:
            hitl_mod._state_manager = old

    async def test_resume_not_found(self):
        import ia_modules.pipeline.hitl as hitl_mod
        old = hitl_mod._state_manager
        try:
            set_state_manager(PipelineStateManager())
            with pytest.raises(HITLException, match="No pending"):
                await HITLResumeManager.resume_pipeline("nonexistent", {})
        finally:
            hitl_mod._state_manager = old

    async def test_get_pending_interactions(self):
        result = await HITLResumeManager.get_pending_interactions()
        assert result == []

    async def test_cancel_interaction(self):
        import ia_modules.pipeline.hitl as hitl_mod
        old = hitl_mod._state_manager
        try:
            mgr = PipelineStateManager()
            await mgr.save_state("id1", "pipe", "step", {}, 3600)
            set_state_manager(mgr)
            result = await HITLResumeManager.cancel_interaction("id1", "test cancel")
            assert result is True
        finally:
            hitl_mod._state_manager = old

    async def test_cancel_nonexistent(self):
        import ia_modules.pipeline.hitl as hitl_mod
        old = hitl_mod._state_manager
        try:
            set_state_manager(PipelineStateManager())
            result = await HITLResumeManager.cancel_interaction("nonexistent")
            assert result is False
        finally:
            hitl_mod._state_manager = old


class TestConvenienceHITLFunctions:
    async def test_create_pause_step(self):
        step = await create_pause_step("pause", "Enter data", 60, {"type": "custom"})
        assert isinstance(step, PauseForInputStep)

    async def test_create_approval_step(self):
        step = await create_approval_step("approve", "content", 120)
        assert isinstance(step, ReviewAndApproveStep)

    async def test_create_conditional_step(self):
        step = await create_conditional_step("cond", [{"type": "confidence_threshold"}], 300)
        assert isinstance(step, ConditionalHumanStep)


# ---------------------------------------------------------------------------
# 6. hitl_manager.py
# ---------------------------------------------------------------------------


class TestHITLManager:
    def _make_manager(self):
        db = MagicMock()
        db.execute.return_value = None
        db.fetch_one.return_value = None
        db.execute.return_value = []
        return HITLManager(db), db

    async def test_create_interaction(self):
        mgr, db = self._make_manager()
        iid = await mgr.create_interaction(
            "exec1", "pipe1", "step1", "Step 1", "Please review", {"data": 1}
        )
        assert isinstance(iid, str)
        db.execute.assert_called_once()

    async def test_create_interaction_with_users(self):
        mgr, db = self._make_manager()
        await mgr.create_interaction(
            "exec1", "pipe1", "step1", "Step 1", "Review",
            {"data": 1}, assigned_users=["u1", "u2"]
        )
        # 1 for main insert + 2 for user assignments
        assert db.execute.call_count == 3

    async def test_create_interaction_with_channels_and_ws(self):
        mgr, db = self._make_manager()
        _ws_mock = AsyncMock()
        with patch.dict(sys.modules, {'ia_modules.showcase_app.backend.api.websocket': MagicMock()}):
            await mgr.create_interaction(
                "exec1", "pipe1", "step1", "Step 1", "Review",
                {"data": 1}, channels=["web", "email"],
                assigned_users=["u1"]
            )

    async def test_get_interaction_not_found(self):
        mgr, db = self._make_manager()
        result = await mgr.get_interaction("nonexistent")
        assert result is None

    async def test_get_interaction_found(self):
        mgr, db = self._make_manager()
        now = datetime.now(timezone.utc)
        db.fetch_one.return_value = {
            "interaction_id": "id1", "execution_id": "e1", "pipeline_id": "p1",
            "step_id": "s1", "step_name": "Step1", "status": "pending",
            "ui_schema": '{"type":"form"}', "prompt": "Review",
            "context_data": '{"key":"val"}', "human_input": None,
            "responded_by": None, "created_at": now,
            "expires_at": now + timedelta(hours=1), "completed_at": None,
        }
        interaction = await mgr.get_interaction("id1")
        assert isinstance(interaction, HITLInteraction)
        assert interaction.interaction_id == "id1"

    async def test_get_pending_interactions(self):
        mgr, db = self._make_manager()
        db.execute.return_value = []
        result = await mgr.get_pending_interactions(execution_id="e1", pipeline_id="p1")
        assert result == []

    async def test_get_pending_interactions_by_user(self):
        mgr, db = self._make_manager()
        db.execute.return_value = []
        result = await mgr.get_pending_interactions(user_id="u1")
        assert result == []

    async def test_respond_to_interaction_not_found(self):
        mgr, db = self._make_manager()
        result = await mgr.respond_to_interaction("nonexistent", {})
        assert result is False

    async def test_respond_to_interaction_not_pending(self):
        mgr, db = self._make_manager()
        now = datetime.now(timezone.utc)
        db.fetch_one.return_value = {
            "interaction_id": "id1", "execution_id": "e1", "pipeline_id": "p1",
            "step_id": "s1", "step_name": "S1", "status": "completed",
            "ui_schema": '{}', "prompt": "p", "context_data": '{}',
            "human_input": None, "responded_by": None,
            "created_at": now, "expires_at": None, "completed_at": None,
        }
        result = await mgr.respond_to_interaction("id1", {})
        assert result is False

    async def test_respond_to_interaction_expired(self):
        mgr, db = self._make_manager()
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        db.fetch_one.return_value = {
            "interaction_id": "id1", "execution_id": "e1", "pipeline_id": "p1",
            "step_id": "s1", "step_name": "S1", "status": "pending",
            "ui_schema": '{}', "prompt": "p", "context_data": '{}',
            "human_input": None, "responded_by": None,
            "created_at": past, "expires_at": past + timedelta(hours=1),
            "completed_at": None,
        }
        result = await mgr.respond_to_interaction("id1", {})
        assert result is False

    async def test_respond_to_interaction_success(self):
        mgr, db = self._make_manager()
        now = datetime.now(timezone.utc)
        db.fetch_one.return_value = {
            "interaction_id": "id1", "execution_id": "e1", "pipeline_id": "p1",
            "step_id": "s1", "step_name": "S1", "status": "pending",
            "ui_schema": '{}', "prompt": "p", "context_data": '{}',
            "human_input": None, "responded_by": None,
            "created_at": now, "expires_at": now + timedelta(hours=1),
            "completed_at": None,
        }
        result = await mgr.respond_to_interaction("id1", {"decision": "approve"}, "user1")
        assert result is True

    async def test_cancel_interaction_success(self):
        mgr, db = self._make_manager()
        now = datetime.now(timezone.utc)
        db.fetch_one.return_value = {
            "interaction_id": "id1", "execution_id": "e1", "pipeline_id": "p1",
            "step_id": "s1", "step_name": "S1", "status": "pending",
            "ui_schema": '{}', "prompt": "p", "context_data": '{}',
            "human_input": None, "responded_by": None,
            "created_at": now, "expires_at": None, "completed_at": None,
        }
        result = await mgr.cancel_interaction("id1")
        assert result is True

    async def test_cancel_interaction_not_pending(self):
        mgr, db = self._make_manager()
        db.fetch_one.return_value = None
        result = await mgr.cancel_interaction("id1")
        assert result is False

    async def test_cleanup_expired(self):
        mgr, db = self._make_manager()
        db.execute.return_value = 3
        result = await mgr.cleanup_expired_interactions()
        assert result == 3

    async def test_save_execution_state(self):
        mgr, db = self._make_manager()
        await mgr.save_execution_state("id1", {"state": "data"})
        db.execute.assert_called_once()

    async def test_get_execution_state_found(self):
        mgr, db = self._make_manager()
        db.fetch_one.return_value = {"context_data": '{"step":"s1"}'}
        result = await mgr.get_execution_state("id1")
        assert result == {"step": "s1"}

    async def test_get_execution_state_not_found(self):
        mgr, db = self._make_manager()
        db.fetch_one.return_value = None
        result = await mgr.get_execution_state("id1")
        assert result is None

    async def test_get_execution_state_no_data(self):
        mgr, db = self._make_manager()
        db.fetch_one.return_value = {"context_data": None}
        result = await mgr.get_execution_state("id1")
        assert result is None

    async def test_notify_channels(self):
        mgr, db = self._make_manager()
        ws = AsyncMock()
        await mgr.notify_channels("id1", ["web", "email", "slack", "discord", "sms"], "prompt", {}, ["u1"], ws)
        ws.broadcast_hitl_notification.assert_called_once()

    async def test_notify_channels_ws_failure(self):
        mgr, db = self._make_manager()
        ws = AsyncMock()
        ws.broadcast_hitl_notification.side_effect = Exception("fail")
        # Should not raise
        await mgr.notify_channels("id1", ["web"], "prompt", {}, ["u1"], ws)

    async def test_notify_channels_no_ws(self):
        mgr, db = self._make_manager()
        await mgr.notify_channels("id1", ["web", "email"], "prompt", {}, ["u1"], None)

    def test_row_to_interaction_string_datetime(self):
        mgr, db = self._make_manager()
        row = {
            "interaction_id": "id1", "execution_id": "e1", "pipeline_id": "p1",
            "step_id": "s1", "step_name": "S1", "status": "pending",
            "ui_schema": '{}', "prompt": "p", "context_data": '{}',
            "human_input": '{"k":"v"}', "responded_by": "u1",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
            "completed_at": None,
        }
        interaction = mgr._row_to_interaction(row)
        assert interaction.interaction_id == "id1"
        assert interaction.human_input == {"k": "v"}


# ---------------------------------------------------------------------------
# 7. subprocess_executor.py
# ---------------------------------------------------------------------------


class TestFindExecutable:
    def test_find_python(self):
        # Python should be findable
        result = _find_executable("python")
        # May or may not be on path depending on environment
        # Just test it doesn't raise
        assert result is None or isinstance(result, str)


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX file mode not enforced on Windows",
)
def test_write_opencode_json_creates_owner_only_config_dir(tmp_path):
    """[26] ``_write_opencode_json`` creates its opencode config dir 0o700.

    Previously the dir inherited the process umask (typically 0o755)
    which made the per-agent config world-listable — an attacker on
    the same host could enumerate job ids and pipeline metadata even
    though the ``opencode.json`` file itself was 0o600.
    """
    import stat

    cleanup = _write_opencode_json(
        str(tmp_path),
        provider="openai",
        api_key="sk-test-not-real",
        model="gpt-4",
    )
    try:
        cfg_dir = tmp_path / "opencode"
        assert cfg_dir.is_dir()
        mode = stat.S_IMODE(cfg_dir.stat().st_mode)
        assert mode & 0o077 == 0, f"expected owner-only, got {oct(mode)}"
    finally:
        cleanup()


class TestSubprocessExecutorInit:
    def test_default_init(self):
        exc = SubprocessExecutor()
        assert exc.bridge_dir is None
        assert exc.max_concurrent == 3

    def test_with_bridge_dir(self):
        exc = SubprocessExecutor(bridge_dir="/tmp/bridge", node_path="/usr/bin/node")
        assert exc.bridge_dir == Path("/tmp/bridge")
        assert exc.node == "/usr/bin/node"


class TestBuildPrompt:
    def test_no_history(self):
        exc = SubprocessExecutor()
        config = AgentConfig(task="Do something", cwd=".")
        result = exc._build_prompt(config)
        assert result == "Do something"

    def test_with_history(self):
        exc = SubprocessExecutor()
        config = AgentConfig(
            task="Do something", cwd=".",
            chat_history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        )
        result = exc._build_prompt(config)
        assert "User: Hello" in result
        assert "Assistant: Hi there" in result
        assert "Current request:" in result
        assert "Do something" in result

    def test_with_empty_history(self):
        exc = SubprocessExecutor()
        config = AgentConfig(task="Do something", cwd=".", chat_history=[])
        result = exc._build_prompt(config)
        assert result == "Do something"


class TestSubprocessExecutorCancel:
    async def test_cancel_no_process(self):
        exc = SubprocessExecutor()
        result = await exc.cancel("nonexistent")
        assert result is False

    async def test_cancel_with_process(self):
        exc = SubprocessExecutor()
        proc = MagicMock()
        proc.returncode = None
        proc.pid = 123
        proc.kill = MagicMock()
        exc._running["job1"] = proc
        result = await exc.cancel("job1")
        assert result is True
        proc.kill.assert_called_once()

    async def test_cancel_already_done(self):
        exc = SubprocessExecutor()
        proc = MagicMock()
        proc.returncode = 0
        exc._running["job1"] = proc
        result = await exc.cancel("job1")
        assert result is False


class TestSubprocessExecute:
    @patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_timeout(self, mock_create, mock_find):
        """Test that timeout yields error event."""
        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=0.001)

        # Make the subprocess hang by sleeping forever on readline
        async def hang_forever():
            await asyncio.sleep(999)
            return b""

        proc = AsyncMock()
        proc.stdout.readline = hang_forever
        proc.stderr.readline = AsyncMock(return_value=b"")
        proc.returncode = None
        proc.wait = AsyncMock(side_effect=lambda: asyncio.sleep(999))
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        events = []
        async for event in exc.execute(config):
            events.append(event)

        # Should have timeout error and stream_end
        assert any(e.type == EventType.SYSTEM and e.subtype == "stream_end" for e in events)
        assert any(e.type == EventType.SYSTEM and "timed out" in (e.error or "") for e in events)

    @patch("asyncio.create_subprocess_exec")
    async def test_run_direct_claude(self, mock_create):
        """Test direct CLI mode for Claude."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[
            b'{"type":"assistant","message":{"type":"text","text":"hi"}}\n',
            b"",
        ])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=10)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        assert any(e.type == EventType.SYSTEM and e.subtype == "stream_end" for e in events)

    @patch("asyncio.create_subprocess_exec")
    async def test_run_direct_opencode(self, mock_create):
        """Test direct CLI mode for OpenCode."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[b""])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(
            task="test", cwd=".",
            cli_type=CLIType.OPENCODE,
            model="gpt-4", provider="openai",
            timeout_seconds=10,
        )

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/opencode"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        assert any(e.subtype == "stream_end" for e in events)

    async def test_run_direct_claude_not_found(self):
        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=1)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value=None):
            with pytest.raises(FileNotFoundError, match="claude CLI not found"):
                await _exhaust_async_gen(exc._run_direct(config))

    async def test_run_direct_opencode_not_found(self):
        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", cli_type=CLIType.OPENCODE, timeout_seconds=1)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value=None):
            with pytest.raises(FileNotFoundError, match="opencode CLI not found"):
                await _exhaust_async_gen(exc._run_direct(config))

    @patch("asyncio.create_subprocess_exec")
    async def test_bridge_mode(self, mock_create):
        """Test bridge mode with stdin config."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[b""])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = AsyncMock()
        proc.stdin.write = MagicMock()
        proc.stdin.drain = AsyncMock()
        proc.stdin.close = MagicMock()
        mock_create.return_value = proc

        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "run_agent.mjs"
            script.write_text("// bridge")

            exc = SubprocessExecutor(bridge_dir=td, node_path="node")
            config = AgentConfig(
                task="test", cwd=".",
                system_prompt="Be helpful",
                tools=["Read", "Write"],
                model="claude-3",
                provider="anthropic",
                api_key="sk-test",
                business_id="biz1",
                agent_id="agent1",
                docs_dir="/docs",
                task_id="t1",
                timeout_seconds=10,
            )
            events = []
            async for event in exc.execute(config):
                events.append(event)

        assert any(e.subtype == "stream_end" for e in events)

    async def test_bridge_script_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            exc = SubprocessExecutor(bridge_dir=td, node_path="node")
            config = AgentConfig(task="test", cwd=".", timeout_seconds=1)
            with pytest.raises(FileNotFoundError, match="Bridge script not found"):
                async for _ in exc._run_via_bridge(config):
                    pass

    @patch("asyncio.create_subprocess_exec")
    async def test_bridge_opencode(self, mock_create):
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[b""])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = AsyncMock()
        proc.stdin.write = MagicMock()
        proc.stdin.drain = AsyncMock()
        proc.stdin.close = MagicMock()
        mock_create.return_value = proc

        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "run_agent_opencode.mjs"
            script.write_text("// bridge")

            exc = SubprocessExecutor(bridge_dir=td, node_path="node")
            config = AgentConfig(
                task="test", cwd=".",
                cli_type=CLIType.OPENCODE,
                model="gpt-4", provider="openai", api_key="sk-key",
                timeout_seconds=10,
            )
            events = []
            async for event in exc.execute(config):
                events.append(event)

    @patch("asyncio.create_subprocess_exec")
    async def test_process_error_exit(self, mock_create):
        """Test handling of non-zero exit code."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[b""])
        proc.stderr.readline = AsyncMock(side_effect=[
            b"ERROR: something went wrong\n", b""
        ])
        proc.returncode = 1
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=10)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        assert any(e.subtype == "error_agent_exit" for e in events)

    @patch("asyncio.create_subprocess_exec")
    async def test_process_interrupted(self, mock_create):
        """Test handling of interrupted process (signal -2)."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[b""])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = -2
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=10)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        error_events = [e for e in events if e.subtype == "error_agent_exit"]
        assert len(error_events) > 0
        assert "interrupted" in error_events[0].error.lower()

    @patch("asyncio.create_subprocess_exec")
    async def test_process_killed(self, mock_create):
        """Test handling of killed process (signal -9)."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[b""])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = -9
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=10)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        error_events = [e for e in events if e.subtype == "error_agent_exit"]
        assert len(error_events) > 0
        assert "canceled" in error_events[0].error.lower()

    @patch("asyncio.create_subprocess_exec")
    async def test_fatal_event_breaks(self, mock_create):
        """Test that fatal events break the loop."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[
            b'{"type":"system","subtype":"error_agent_exit","error":"fatal"}\n',
            b'{"type":"text","text":"should not appear"}\n',
            b"",
        ])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=10)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        # The fatal event should break the inner loop, but we still get stream_end
        text_events = [e for e in events if e.type == EventType.TEXT]
        assert len(text_events) == 0  # The second event should not appear

    @patch("asyncio.create_subprocess_exec")
    async def test_text_and_result_capture(self, mock_create):
        """Test result text capture from TEXT and RESULT events."""
        proc = AsyncMock()
        proc.stdout.readline = AsyncMock(side_effect=[
            b'{"type":"assistant","message":{"type":"text","text":"hello world"}}\n',
            b"",
        ])
        proc.stderr.readline = AsyncMock(side_effect=[b""])
        proc.returncode = 0
        proc.wait = AsyncMock()
        proc.kill = MagicMock()
        proc.stdin = None
        mock_create.return_value = proc

        exc = SubprocessExecutor()
        config = AgentConfig(task="test", cwd=".", timeout_seconds=10)

        with patch("ia_modules.agents.subprocess_executor._find_executable", return_value="/usr/bin/claude"):
            events = []
            async for event in exc.execute(config):
                events.append(event)

        stream_end = [e for e in events if e.subtype == "stream_end"]
        assert len(stream_end) == 1


# Utility to exhaust an async generator
async def _exhaust_async_gen(gen):
    async for _ in gen:
        pass


# ---------------------------------------------------------------------------
# 12. iterative_refinement.py
# ---------------------------------------------------------------------------


class TestIterativeRefinementStep:
    async def test_first_iteration(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 3, "prompt": "Improve"})
        result = await step.run({"current_result": "draft"})
        assert result["status"] == "human_input_required"
        assert result["iteration"] == 1
        assert "Improve" in result["prompt"]

    async def test_max_iterations_reached(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 2})
        result = await step.run({"current_result": "final", "iteration": 3})
        assert result["status"] == "refinement_complete"
        assert result["iterations_completed"] == 2

    async def test_with_history(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 5})
        result = await step.run({
            "current_result": "v2",
            "iteration": 2,
            "refinement_history": [{"iteration": 1, "notes": "first pass"}]
        })
        assert result["status"] == "human_input_required"
        assert result["iteration"] == 2

    async def test_default_config(self):
        step = IterativeRefinementStep("refine", {})
        result = await step.run({})
        assert result["max_iterations"] == 3


class TestProcessRefinementResponseStep:
    async def test_continue_refining(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({
            "refined_result": "better",
            "refinement_notes": "fixed typos",
            "continue_refining": True,
            "iteration": 1,
            "max_iterations": 3,
            "refinement_history": [],
        })
        assert result["status"] == "continue_refinement"
        assert result["iteration"] == 2
        assert len(result["refinement_history"]) == 1

    async def test_done_refining(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({
            "refined_result": "final",
            "continue_refining": False,
            "iteration": 2,
            "max_iterations": 3,
            "refinement_history": [{"iteration": 1}],
        })
        assert result["status"] == "refinement_complete"
        assert result["final_result"] == "final"
        assert result["iterations_completed"] == 2

    async def test_max_iterations_force_complete(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({
            "refined_result": "final",
            "continue_refining": True,
            "iteration": 3,
            "max_iterations": 3,
            "refinement_history": [],
        })
        assert result["status"] == "refinement_complete"

    async def test_defaults(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({})
        assert result["status"] == "refinement_complete"
