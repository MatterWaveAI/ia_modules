"""Tests for SubprocessAgentAdapter — the pattern-compatible agent wrapper."""

from unittest.mock import MagicMock

from ia_modules.utils.llm_adapters import SubprocessAgentAdapter
from ia_modules.agents.executor import (
    AgentEvent, AgentMode, CLIType, EventType,
)


def _make_adapter(**kwargs):
    """Create adapter with mocked executor."""
    adapter = SubprocessAgentAdapter(cwd="/test", **kwargs)
    mock_executor = MagicMock()
    adapter._executor = mock_executor
    return adapter, mock_executor


def _mock_execute(events):
    """Return an async generator function that yields the given events."""
    async def execute(config):
        for e in events:
            yield e
    return execute


class TestSubprocessAgentAdapterConfig:
    def test_default_config(self):
        adapter = SubprocessAgentAdapter(cwd="/test")
        assert adapter.cwd == "/test"
        assert adapter.cli_type == CLIType.CLAUDE_CODE
        assert adapter.mode == AgentMode.RESEARCH
        assert adapter.timeout_seconds == 300.0

    def test_custom_config(self):
        adapter = SubprocessAgentAdapter(
            cwd="/project",
            cli_type=CLIType.OPENCODE,
            mode=AgentMode.EXECUTE,
            tools=["Read", "Bash"],
            system_prompt="Be helpful.",
            provider="anthropic",
            timeout_seconds=60.0,
        )
        assert adapter.cli_type == CLIType.OPENCODE
        assert adapter.mode == AgentMode.EXECUTE
        assert adapter.tools == ["Read", "Bash"]
        assert adapter.system_prompt == "Be helpful."
        assert adapter.provider == "anthropic"


class TestSubprocessAgentAdapterGenerate:
    async def test_returns_result_text(self):
        adapter, mock_exec = _make_adapter()
        mock_exec.execute = _mock_execute([
            AgentEvent(type=EventType.TEXT, text="Thinking..."),
            AgentEvent(type=EventType.RESULT, result="The answer is 42"),
            AgentEvent(type=EventType.SYSTEM, subtype="stream_end"),
        ])

        result = await adapter.generate("What is the answer?")
        assert result == "The answer is 42"

    async def test_returns_last_text_when_no_result(self):
        adapter, mock_exec = _make_adapter()
        mock_exec.execute = _mock_execute([
            AgentEvent(type=EventType.TEXT, text="First thought"),
            AgentEvent(type=EventType.TEXT, text="Final thought"),
            AgentEvent(type=EventType.SYSTEM, subtype="stream_end"),
        ])

        result = await adapter.generate("Think about this")
        assert result == "Final thought"

    async def test_returns_error_on_fatal(self):
        adapter, mock_exec = _make_adapter()
        mock_exec.execute = _mock_execute([
            AgentEvent(
                type=EventType.RESULT, subtype="error_agent_exit",
                error="Agent crashed", result="",
            ),
        ])

        result = await adapter.generate("Do something")
        assert "Error:" in result
        assert "crashed" in result

    async def test_passes_model_to_config(self):
        adapter, mock_exec = _make_adapter()
        configs_seen = []

        async def capture_execute(config):
            configs_seen.append(config)
            yield AgentEvent(type=EventType.RESULT, result="done")
            yield AgentEvent(type=EventType.SYSTEM, subtype="stream_end")

        mock_exec.execute = capture_execute

        await adapter.generate("test", model="claude-sonnet-4-20250514")
        assert len(configs_seen) == 1
        assert configs_seen[0].model == "claude-sonnet-4-20250514"
        assert configs_seen[0].task == "test"

    async def test_research_mode_default_tools(self):
        adapter, mock_exec = _make_adapter(mode=AgentMode.RESEARCH)
        configs_seen = []

        async def capture_execute(config):
            configs_seen.append(config)
            yield AgentEvent(type=EventType.RESULT, result="done")
            yield AgentEvent(type=EventType.SYSTEM, subtype="stream_end")

        mock_exec.execute = capture_execute

        await adapter.generate("research task")
        assert configs_seen[0].tools == ["Read", "Glob", "Grep"]

    async def test_execute_mode_default_tools(self):
        adapter, mock_exec = _make_adapter(mode=AgentMode.EXECUTE)
        configs_seen = []

        async def capture_execute(config):
            configs_seen.append(config)
            yield AgentEvent(type=EventType.RESULT, result="done")
            yield AgentEvent(type=EventType.SYSTEM, subtype="stream_end")

        mock_exec.execute = capture_execute

        await adapter.generate("write code")
        assert "Edit" in configs_seen[0].tools
        assert "Write" in configs_seen[0].tools

    async def test_custom_tools_override(self):
        adapter, mock_exec = _make_adapter(tools=["Read", "Bash"])
        configs_seen = []

        async def capture_execute(config):
            configs_seen.append(config)
            yield AgentEvent(type=EventType.RESULT, result="done")
            yield AgentEvent(type=EventType.SYSTEM, subtype="stream_end")

        mock_exec.execute = capture_execute

        await adapter.generate("custom task")
        assert configs_seen[0].tools == ["Read", "Bash"]

    async def test_empty_result_on_no_events(self):
        adapter, mock_exec = _make_adapter()
        mock_exec.execute = _mock_execute([
            AgentEvent(type=EventType.SYSTEM, subtype="stream_end"),
        ])

        result = await adapter.generate("nothing happens")
        assert result == ""


class TestSubprocessAgentAdapterPatternCompat:
    """Verify the adapter satisfies the pattern interface contract."""

    async def test_works_as_pattern_llm_service(self):
        """Patterns call context['services']['llm'].generate(prompt, model, temperature)."""
        adapter, mock_exec = _make_adapter()
        mock_exec.execute = _mock_execute([
            AgentEvent(type=EventType.RESULT, result="Canberra"),
            AgentEvent(type=EventType.SYSTEM, subtype="stream_end"),
        ])

        # This is exactly how patterns call it
        context = {'services': {'llm': adapter}}
        llm = context['services']['llm']
        result = await llm.generate(
            prompt="What is the capital of Australia?",
            model="gpt-4",
            temperature=0.7,
        )
        assert result == "Canberra"

    async def test_ignores_temperature_and_max_tokens(self):
        """CLI agents don't support temperature/max_tokens — adapter should not crash."""
        adapter, mock_exec = _make_adapter()
        mock_exec.execute = _mock_execute([
            AgentEvent(type=EventType.RESULT, result="ok"),
            AgentEvent(type=EventType.SYSTEM, subtype="stream_end"),
        ])

        # Should not raise
        result = await adapter.generate(
            prompt="test",
            model="gpt-4",
            temperature=0.9,
            max_tokens=1000,
        )
        assert result == "ok"
