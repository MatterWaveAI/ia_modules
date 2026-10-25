"""Tests for AgentStep and CentralLoggingService NDJSON wiring."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from ia_modules.pipeline.agent_step import AgentStep
from ia_modules.pipeline.ndjson_logger import NdjsonLogger
from ia_modules.pipeline.services import CentralLoggingService, ServiceRegistry
from ia_modules.agents.executor import AgentEvent, AgentMode, CLIType, EventType


# --- CentralLoggingService NDJSON wiring ---

class TestCentralLoggerNdjsonWiring:
    async def test_log_queues_ndjson_entry(self, tmp_path):
        ndjson = NdjsonLogger(str(tmp_path / "test.jsonl"))
        cl = CentralLoggingService()
        cl.set_ndjson_logger(ndjson)

        cl.info("step started", step_name="fetch")
        cl.error("timeout hit", step_name="fetch", data={"url": "http://x"})

        assert len(cl._ndjson_pending) == 2
        assert cl._ndjson_pending[0]["level"] == "INFO"
        assert cl._ndjson_pending[1]["level"] == "ERROR"
        await ndjson.close()

    async def test_flush_writes_ndjson(self, tmp_path):
        log_path = str(tmp_path / "test.jsonl")
        ndjson = NdjsonLogger(log_path)
        cl = CentralLoggingService()
        cl.set_ndjson_logger(ndjson)

        cl.info("hello", step_name="s1")
        cl.warning("careful", step_name="s2", data={"count": 3})
        await cl.flush_ndjson()
        await ndjson.close()

        lines = Path(log_path).read_text().strip().split("\n")
        assert len(lines) == 2

        e1 = json.loads(lines[0])
        assert e1["type"] == "log"
        assert e1["subtype"] == "info"
        assert e1["step_name"] == "s1"
        assert e1["text"] == "hello"

        e2 = json.loads(lines[1])
        assert e2["subtype"] == "warning"
        assert e2["data"] == {"count": 3}

    async def test_flush_clears_pending(self, tmp_path):
        ndjson = NdjsonLogger(str(tmp_path / "test.jsonl"))
        cl = CentralLoggingService()
        cl.set_ndjson_logger(ndjson)

        cl.info("msg")
        await cl.flush_ndjson()
        assert len(cl._ndjson_pending) == 0

        # Second flush writes nothing new
        await cl.flush_ndjson()
        lines = Path(tmp_path / "test.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1
        await ndjson.close()

    async def test_no_ndjson_logger_no_queue(self):
        cl = CentralLoggingService()
        cl.info("msg")
        assert len(cl._ndjson_pending) == 0

    async def test_still_collects_execution_logs(self, tmp_path):
        ndjson = NdjsonLogger(str(tmp_path / "test.jsonl"))
        cl = CentralLoggingService()
        cl.set_ndjson_logger(ndjson)

        cl.info("msg1")
        cl.error("msg2")
        assert len(cl.execution_logs) == 2
        assert cl.execution_logs[0].message == "msg1"
        await ndjson.close()


class TestServiceRegistryAutoWire:
    def test_register_ndjson_auto_wires(self, tmp_path):
        registry = ServiceRegistry()
        ndjson = NdjsonLogger(str(tmp_path / "test.jsonl"))
        registry.register("ndjson_logger", ndjson)

        cl = registry.get("central_logger")
        assert cl._ndjson_logger is ndjson

    def test_no_auto_wire_for_other_services(self):
        registry = ServiceRegistry()
        registry.register("database", MagicMock())

        cl = registry.get("central_logger")
        assert cl._ndjson_logger is None


# --- AgentStep config building ---

class TestAgentStepConfig:
    def test_build_agent_config_defaults(self):
        step = AgentStep("research", {
            "task": "Analyze code",
            "cwd": "/project",
        })
        config = step._build_agent_config({})

        assert config.task == "Analyze code"
        assert config.cwd == "/project"
        assert config.mode == AgentMode.RESEARCH
        assert config.cli_type == CLIType.CLAUDE_CODE
        assert config.tools == ["Read", "Glob", "Grep"]

    def test_build_agent_config_execute_mode(self):
        step = AgentStep("writer", {
            "task": "Write tests",
            "cwd": "/project",
            "mode": "execute",
        })
        config = step._build_agent_config({})

        assert config.mode == AgentMode.EXECUTE
        assert "Write" in config.tools
        assert "Edit" in config.tools

    def test_build_agent_config_custom_tools(self):
        step = AgentStep("custom", {
            "task": "Do stuff",
            "cwd": "/project",
            "tools": ["Read", "Bash"],
        })
        config = step._build_agent_config({})
        assert config.tools == ["Read", "Bash"]

    def test_build_agent_config_template_resolution(self):
        step = AgentStep("dynamic", {
            "task": "Analyze {filename} for {issue_type}",
            "cwd": "/project",
        })
        config = step._build_agent_config({
            "filename": "main.py",
            "issue_type": "security",
        })
        assert config.task == "Analyze main.py for security"

    def test_build_agent_config_template_missing_key(self):
        step = AgentStep("dynamic", {
            "task": "Analyze {filename} for {missing_key}",
            "cwd": "/project",
        })
        config = step._build_agent_config({"filename": "main.py"})
        # Should not crash, leaves template as-is
        assert "{missing_key}" in config.task

    def test_build_agent_config_optional_fields(self):
        step = AgentStep("full", {
            "task": "Work",
            "cwd": "/project",
            "model": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "system_prompt": "You are helpful.",
            "timeout_seconds": 300,
            "business_id": "biz-1",
        })
        config = step._build_agent_config({})

        assert config.model == "claude-sonnet-4-20250514"
        assert config.provider == "anthropic"
        assert config.system_prompt == "You are helpful."
        assert config.timeout_seconds == 300
        assert config.business_id == "biz-1"


# --- AgentStep.run() with mocked executor ---

class TestAgentStepRun:
    async def test_run_writes_agent_ndjson(self, tmp_path):
        """Agent events should be written to a separate NDJSON file."""
        step = AgentStep("research", {
            "task": "Analyze code",
            "cwd": "/project",
            "logs_dir": str(tmp_path),
        })
        step.services = ServiceRegistry()

        # Mock the executor to yield a few events
        events = [
            AgentEvent(type=EventType.TEXT, text="Looking at files..."),
            AgentEvent(type=EventType.TOOL_USE, tool="Read", input={"path": "/foo"}),
            AgentEvent(type=EventType.RESULT, result="Analysis complete"),
            AgentEvent(type=EventType.SYSTEM, subtype="stream_end"),
        ]

        async def mock_execute(config):
            for e in events:
                yield e

        mock_executor = MagicMock()
        mock_executor.execute = mock_execute
        step._executor = mock_executor

        result = await step.run({})

        # TEXT events are preferred over RESULT events for result capture
        assert result["result"] == "Looking at files..."
        assert result["event_count"] == 4
        assert "agent_job_id" in result

        # Check agent NDJSON file was created
        agent_log = Path(result["agent_log_path"])
        assert agent_log.exists()
        lines = agent_log.read_text().strip().split("\n")
        assert len(lines) == 4

        # Verify event types in log
        event_types = [json.loads(line)["type"] for line in lines]
        assert event_types == ["text", "tool_use", "result", "system"]

    async def test_run_logs_agent_spawned_to_pipeline_ndjson(self, tmp_path):
        """Pipeline NDJSON should get agent_spawned and agent_completed events."""
        pipeline_log = str(tmp_path / "pipeline.jsonl")
        pipeline_ndjson = NdjsonLogger(pipeline_log)

        services = ServiceRegistry()
        services.register("ndjson_logger", pipeline_ndjson)

        step = AgentStep("research", {
            "task": "Analyze",
            "cwd": "/project",
            "logs_dir": str(tmp_path / "agent_logs"),
        })
        step.services = services

        # Mock executor with minimal events
        async def mock_execute(config):
            yield AgentEvent(type=EventType.RESULT, result="Done")
            yield AgentEvent(type=EventType.SYSTEM, subtype="stream_end")

        mock_executor = MagicMock()
        mock_executor.execute = mock_execute
        step._executor = mock_executor

        await step.run({})
        await pipeline_ndjson.close()

        lines = Path(pipeline_log).read_text().strip().split("\n")
        events = [json.loads(line) for line in lines]

        subtypes = [e.get("subtype") for e in events]
        assert "agent_spawned" in subtypes
        assert "agent_completed" in subtypes

        spawned = next(e for e in events if e.get("subtype") == "agent_spawned")
        assert "agent_job_id" in spawned
        assert "agent_log_path" in spawned
        assert spawned["step_name"] == "research"

    async def test_run_logs_to_central_logger(self, tmp_path):
        """CentralLoggingService should get agent spawn/complete entries."""
        services = ServiceRegistry()
        step = AgentStep("research", {
            "task": "Analyze",
            "cwd": "/project",
            "logs_dir": str(tmp_path),
        })
        step.services = services

        async def mock_execute(config):
            yield AgentEvent(type=EventType.RESULT, result="Done")
            yield AgentEvent(type=EventType.SYSTEM, subtype="stream_end")

        mock_executor = MagicMock()
        mock_executor.execute = mock_execute
        step._executor = mock_executor

        await step.run({})

        cl = services.get("central_logger")
        messages = [e.message for e in cl.execution_logs]
        assert any("Agent spawned" in m for m in messages)
        assert any("Agent completed" in m for m in messages)

    async def test_run_captures_error(self, tmp_path):
        """Fatal agent errors should be captured in output."""
        step = AgentStep("research", {
            "task": "Analyze",
            "cwd": "/project",
            "logs_dir": str(tmp_path),
        })
        step.services = ServiceRegistry()

        async def mock_execute(config):
            yield AgentEvent(
                type=EventType.RESULT, subtype="error_agent_exit",
                error="Agent crashed",
            )

        mock_executor = MagicMock()
        mock_executor.execute = mock_execute
        step._executor = mock_executor

        with pytest.raises(RuntimeError, match="Agent crashed"):
            await step.run({})


# --- Step convenience methods ---

class TestStepConvenience:
    def test_get_ndjson_logger(self, tmp_path):
        from ia_modules.pipeline.core import Step
        step = Step("test", {})
        ndjson = NdjsonLogger(str(tmp_path / "test.jsonl"))
        services = ServiceRegistry()
        services.register("ndjson_logger", ndjson)
        step.services = services

        assert step.get_ndjson_logger() is ndjson

    def test_get_central_logger(self):
        from ia_modules.pipeline.core import Step
        step = Step("test", {})
        services = ServiceRegistry()
        step.services = services

        cl = step.get_central_logger()
        assert cl is not None
        assert hasattr(cl, "info")

    def test_get_ndjson_logger_none_when_no_services(self):
        from ia_modules.pipeline.core import Step
        step = Step("test", {})
        assert step.get_ndjson_logger() is None
        assert step.get_central_logger() is None
