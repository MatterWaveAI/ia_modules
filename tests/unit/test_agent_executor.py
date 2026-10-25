"""Tests for agent executor protocol, types, and normalize_event."""

from ia_modules.agents.executor import (
    AgentConfig,
    AgentEvent,
    AgentMode,
    CLIType,
    EventType,
    normalize_event,
)


# --- AgentConfig defaults ---

class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig(task="hello", cwd="/tmp")
        assert config.cli_type == CLIType.CLAUDE_CODE
        assert config.mode == AgentMode.RESEARCH
        assert config.tools == ["Read", "Glob", "Grep"]
        assert config.timeout_seconds == 1800.0
        assert config.job_id  # auto-generated UUID

    def test_custom_values(self):
        config = AgentConfig(
            task="do stuff",
            cwd="/work",
            cli_type=CLIType.OPENCODE,
            mode=AgentMode.EXECUTE,
            tools=["Read", "Write", "Edit"],
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            business_id="biz-123",
        )
        assert config.cli_type == CLIType.OPENCODE
        assert config.mode == AgentMode.EXECUTE
        assert config.model == "claude-sonnet-4-20250514"
        assert config.business_id == "biz-123"


# --- AgentEvent properties ---

class TestAgentEvent:
    def test_is_error(self):
        e = AgentEvent(type=EventType.RESULT, subtype="error")
        assert e.is_error
        assert not e.is_fatal

    def test_is_fatal(self):
        e = AgentEvent(type=EventType.RESULT, subtype="error_agent_exit")
        assert e.is_error
        assert e.is_fatal

    def test_is_stream_end(self):
        e = AgentEvent(type=EventType.SYSTEM, subtype="stream_end")
        assert e.is_stream_end

    def test_not_stream_end(self):
        e = AgentEvent(type=EventType.TEXT, text="hello")
        assert not e.is_stream_end
        assert not e.is_error

    def test_to_dict(self):
        e = AgentEvent(
            type=EventType.TEXT, text="hello", seq=1, job_id="j1",
        )
        d = e.to_dict()
        assert d["type"] == "text"
        assert d["text"] == "hello"
        assert d["_seq"] == 1
        assert d["job_id"] == "j1"

    def test_to_dict_omits_none(self):
        e = AgentEvent(type=EventType.SYSTEM, subtype="stream_end", seq=1)
        d = e.to_dict()
        assert "text" not in d
        assert "tool" not in d
        assert "error" not in d
        assert d["subtype"] == "stream_end"


# --- normalize_event ---

class TestNormalizeEvent:
    def test_text_event(self):
        raw = {"type": "text", "part": {"text": "hello world"}}
        event = normalize_event(raw, seq=1, job_id="j1")
        assert event.type == EventType.TEXT
        assert event.text == "hello world"
        assert event.seq == 1

    def test_reasoning_event(self):
        raw = {"type": "reasoning", "part": {"text": "thinking..."}}
        event = normalize_event(raw, seq=2)
        assert event.type == EventType.REASONING
        assert event.text == "thinking..."

    def test_result_event(self):
        raw = {"type": "result", "result": "done", "subtype": "success"}
        event = normalize_event(raw, seq=3, job_id="j2")
        assert event.type == EventType.RESULT
        assert event.result == "done"
        assert event.subtype == "success"

    def test_result_error(self):
        raw = {"type": "result", "subtype": "error", "error": "boom"}
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.RESULT
        assert event.error == "boom"
        assert event.is_error

    def test_system_event(self):
        raw = {"type": "system", "subtype": "stream_end", "duration_ms": 1234}
        event = normalize_event(raw, seq=5)
        assert event.type == EventType.SYSTEM
        assert event.is_stream_end
        assert event.metadata.get("duration_ms") == 1234

    def test_tool_use_opencode(self):
        raw = {
            "type": "tool_use",
            "part": {
                "tool": "Read",
                "callID": "call-1",
                "state": {"input": {"path": "/foo"}, "output": "contents"},
            },
        }
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.TOOL_USE
        assert event.tool == "Read"
        assert event.input == {"path": "/foo"}
        assert event.output == "contents"
        assert event.tool_use_id == "call-1"

    def test_tool_result(self):
        raw = {"type": "tool_result", "output": "file contents", "tool_use_id": "tu-1"}
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.TOOL_RESULT
        assert event.output == "file contents"

    def test_assistant_text_block(self):
        raw = {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Here is my answer"}],
            },
        }
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.TEXT
        assert event.text == "Here is my answer"

    def test_assistant_tool_use_block(self):
        raw = {
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "name": "Read",
                    "id": "tu-2",
                    "input": {"file_path": "/foo.py"},
                }],
            },
        }
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.TOOL_USE
        assert event.tool == "Read"
        assert event.input == {"file_path": "/foo.py"}

    def test_assistant_tool_result_block(self):
        raw = {
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "tu-3",
                    "content": [{"text": "line 1"}, {"text": "line 2"}],
                }],
            },
        }
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.TOOL_RESULT
        assert event.output == "line 1line 2"

    def test_step_lifecycle(self):
        for etype, expected in [("step_start", EventType.STEP_START), ("step_finish", EventType.STEP_FINISH)]:
            event = normalize_event({"type": etype}, seq=1)
            assert event.type == expected

    def test_unknown_event(self):
        raw = {"type": "something_new", "data": 42}
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.SYSTEM
        assert event.subtype == "unknown"

    def test_empty_assistant_message(self):
        raw = {"type": "assistant", "message": {"content": []}, "text": "fallback"}
        event = normalize_event(raw, seq=1)
        assert event.type == EventType.TEXT
        assert event.text == "fallback"
