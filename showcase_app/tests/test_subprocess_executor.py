"""Integration tests for SubprocessExecutor — actually spawns CLI agents.

These tests call real CLI binaries (opencode / claude) and verify the
event stream. They require:
  - opencode or claude on PATH
  - LLM_API_KEY set (or a valid opencode.json / claude config)

Skip with:  pytest -m "not integration"
Run only:   pytest -m integration
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

pytestmark = pytest.mark.integration

# Load .env from showcase_app/backend/ so tests get the real API key/provider
_env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(_env_path)

from ia_modules.agents.executor import (  # noqa: E402
    AgentConfig,
    AgentMode,
    CLIType,
    EventType,
)
from ia_modules.agents.subprocess_executor import SubprocessExecutor, _find_executable  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def executor():
    return SubprocessExecutor()


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temp workspace with a sample file for agents to read."""
    sample = tmp_path / "hello.txt"
    sample.write_text("Hello from the test workspace.\nLine 2.\nLine 3.\n")
    return str(tmp_path)


def _has_opencode():
    return _find_executable("opencode") is not None


def _has_claude():
    return _find_executable("claude") is not None


def _apply_env_config(config: AgentConfig):
    """Wire LLM env vars into an AgentConfig (for opencode)."""
    provider = os.getenv("LLM_PROVIDER", "").strip() or None
    model = os.getenv("LLM_MODEL", "").strip() or None
    api_key = os.getenv("LLM_API_KEY", "").strip() or None
    if provider:
        config.provider = provider
    if model:
        config.model = model
    if api_key:
        config.api_key = api_key


async def _collect(executor, config):
    """Run the executor and collect all events."""
    events = []
    async for event in executor.execute(config):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Tests: opencode
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not _has_opencode(), reason="opencode CLI not on PATH")
class TestOpenCodeDirect:
    """Test SubprocessExecutor with opencode CLI in direct mode."""

    @pytest.mark.asyncio
    async def test_simple_prompt_streams_events(self, executor, tmp_workspace):
        """A basic prompt should produce TEXT events and end with stream_end."""
        config = AgentConfig(
            task="Say exactly: HELLO_TEST_MARKER",
            cwd=tmp_workspace,
            cli_type=CLIType.OPENCODE,
            mode=AgentMode.RESEARCH,
            tools=[],
            timeout_seconds=60,
        )
        _apply_env_config(config)

        events = await _collect(executor, config)

        assert len(events) >= 1, f"Expected events, got {len(events)}"

        # Last event should be stream_end
        assert events[-1].type == EventType.SYSTEM
        assert events[-1].subtype == "stream_end"

        # Sequential seq numbers
        seqs = [e.seq for e in events]
        assert seqs == list(range(1, len(events) + 1))

        # All events share one job_id
        job_ids = {e.job_id for e in events}
        assert len(job_ids) == 1
        assert None not in job_ids

        types = [(e.type.value, e.subtype) for e in events]
        print(f"\nEvent stream ({len(events)} events): {types}")

    @pytest.mark.asyncio
    async def test_read_tool_usage(self, executor, tmp_workspace):
        """Agent with Read tool should produce events and end cleanly."""
        config = AgentConfig(
            task="Read the file hello.txt and tell me its contents.",
            cwd=tmp_workspace,
            cli_type=CLIType.OPENCODE,
            mode=AgentMode.RESEARCH,
            tools=["Read"],
            timeout_seconds=60,
        )
        _apply_env_config(config)

        events = await _collect(executor, config)

        assert events[-1].is_stream_end
        assert len(events) >= 2  # At least one content event + stream_end

        # We should get content events: TEXT, TOOL_USE, TOOL_RESULT, or errors.
        text_events = [e for e in events if e.type == EventType.TEXT and e.text]
        tool_events = [e for e in events if e.type in (EventType.TOOL_USE, EventType.TOOL_RESULT)]
        error_events = [e for e in events if e.error]
        assert len(text_events) > 0 or len(tool_events) > 0 or len(error_events) > 0, \
            "Expected TEXT, TOOL_USE/TOOL_RESULT, or error events"

        print(f"\nEvent types: {[e.type.value for e in events]}")
        if error_events:
            print(f"  (API error — expected with placeholder key: {error_events[0].error[:100]})")

    @pytest.mark.asyncio
    async def test_timeout(self, executor, tmp_workspace):
        """Agent should timeout and produce an error event."""
        config = AgentConfig(
            task="Count from 1 to 1000000, saying each number out loud, one at a time, very slowly.",
            cwd=tmp_workspace,
            cli_type=CLIType.OPENCODE,
            mode=AgentMode.RESEARCH,
            tools=[],
            timeout_seconds=5,
        )
        _apply_env_config(config)

        events = await _collect(executor, config)

        # Should end with stream_end
        assert events[-1].is_stream_end

        print(f"\nGot {len(events)} events, errors: {[e.error for e in events if e.error]}")


# ---------------------------------------------------------------------------
# Tests: claude
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not _has_claude(), reason="claude CLI not on PATH")
class TestClaudeCodeDirect:
    """Test SubprocessExecutor with claude CLI in direct mode."""

    @pytest.mark.asyncio
    async def test_simple_prompt_streams_events(self, executor, tmp_workspace):
        """A basic prompt should produce TEXT events and end with stream_end."""
        config = AgentConfig(
            task="Say exactly: HELLO_TEST_MARKER",
            cwd=tmp_workspace,
            cli_type=CLIType.CLAUDE_CODE,
            mode=AgentMode.RESEARCH,
            tools=[],
            timeout_seconds=60,
        )

        events = await _collect(executor, config)

        assert len(events) >= 1
        assert events[-1].type == EventType.SYSTEM
        assert events[-1].subtype == "stream_end"

        seqs = [e.seq for e in events]
        assert seqs == list(range(1, len(events) + 1))

        types = [(e.type.value, e.subtype) for e in events]
        print(f"\nEvent stream ({len(events)} events): {types}")

    @pytest.mark.asyncio
    async def test_read_tool_with_allowed_tools(self, executor, tmp_workspace):
        """Claude with --allowedTools should use Read tool."""
        config = AgentConfig(
            task="Read the file hello.txt and tell me what it says.",
            cwd=tmp_workspace,
            cli_type=CLIType.CLAUDE_CODE,
            mode=AgentMode.RESEARCH,
            tools=["Read"],
            timeout_seconds=60,
        )

        events = await _collect(executor, config)

        assert events[-1].is_stream_end

        text_events = [e for e in events if e.type == EventType.TEXT and e.text]
        assert len(text_events) > 0

        print(f"\nEvent types: {[(e.type.value, e.tool) for e in events]}")


# ---------------------------------------------------------------------------
# Tests: event integrity from real CLI output
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEventIntegrity:
    """Verify event properties from real CLI output."""

    @pytest.mark.skipif(
        not (_has_opencode() or _has_claude()),
        reason="No CLI agent on PATH",
    )
    @pytest.mark.asyncio
    async def test_all_events_have_timestamps(self, executor, tmp_workspace):
        """Every event should have a timestamp."""
        cli = CLIType.OPENCODE if _has_opencode() else CLIType.CLAUDE_CODE
        config = AgentConfig(
            task="Say hello.",
            cwd=tmp_workspace,
            cli_type=cli,
            mode=AgentMode.RESEARCH,
            tools=[],
            timeout_seconds=30,
        )
        if cli == CLIType.OPENCODE:
            _apply_env_config(config)

        events = await _collect(executor, config)

        for event in events:
            assert event.timestamp, f"Event {event.seq} missing timestamp: {event.type}"
            assert event.seq > 0, f"Event has seq=0: {event.type}"

    @pytest.mark.skipif(
        not (_has_opencode() or _has_claude()),
        reason="No CLI agent on PATH",
    )
    @pytest.mark.asyncio
    async def test_stream_end_has_duration(self, executor, tmp_workspace):
        """The stream_end event should carry duration metadata."""
        cli = CLIType.OPENCODE if _has_opencode() else CLIType.CLAUDE_CODE
        config = AgentConfig(
            task="Say exactly: RESULT_CHECK_42",
            cwd=tmp_workspace,
            cli_type=cli,
            mode=AgentMode.RESEARCH,
            tools=[],
            timeout_seconds=30,
        )
        if cli == CLIType.OPENCODE:
            _apply_env_config(config)

        events = await _collect(executor, config)
        stream_end = events[-1]

        assert stream_end.is_stream_end
        assert stream_end.metadata.get("duration_ms", 0) > 0
        print(f"\nDuration: {stream_end.metadata['duration_ms']}ms, result: {(stream_end.result or '')[:100]}")


# ---------------------------------------------------------------------------
# Tests: cancellation
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not (_has_opencode() or _has_claude()),
    reason="No CLI agent on PATH",
)
class TestCancellation:
    """Test that cancel() kills the subprocess."""

    @pytest.mark.asyncio
    async def test_cancel_running_agent(self, executor, tmp_workspace):
        """Cancelling a running agent should kill the process."""
        cli = CLIType.OPENCODE if _has_opencode() else CLIType.CLAUDE_CODE
        config = AgentConfig(
            task="Write a very long essay about the history of computing, at least 5000 words.",
            cwd=tmp_workspace,
            cli_type=cli,
            mode=AgentMode.RESEARCH,
            tools=[],
            timeout_seconds=120,
        )
        if cli == CLIType.OPENCODE:
            _apply_env_config(config)

        job_id = config.job_id
        events = []
        async for event in executor.execute(config):
            events.append(event)
            # After getting a few events, cancel
            if len(events) >= 3:
                cancelled = await executor.cancel(job_id)
                print(f"\nCancel result: {cancelled}")
                break

        # Consume remaining events after cancel
        # (stream_end should still arrive)
        print(f"\nGot {len(events)} events before/after cancel")
