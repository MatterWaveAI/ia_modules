"""AgentExecutor protocol — the contract for running CLI agents.

Defines:
- AgentExecutor: Protocol that all executors implement
- AgentConfig: Configuration for a CLI agent execution
- AgentEvent: Normalized event from an agent execution
- normalize_event(): Converts raw CLI NDJSON into AgentEvent
- CLIType, AgentMode, EventType: Enums

Implementations:
- SubprocessExecutor: spawns CLI agent directly (default, no server needed)
- A2AExecutor: dispatches to an A2A server via JSON-RPC (distributed setups)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable


class CLIType(str, Enum):
    """Supported CLI agent types."""
    CLAUDE_CODE = "claude_code"
    OPENCODE = "opencode"


class AgentMode(str, Enum):
    """Agent execution modes — controls tool access."""
    RESEARCH = "research"   # Read-only: Read, Glob, Grep
    EXECUTE = "execute"     # Read+Write: Read, Glob, Grep, Edit, Write
    PLAN = "plan"           # Read-only, planning focused


class EventType(str, Enum):
    """Unified event types from CLI agents."""
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    RESULT = "result"
    SYSTEM = "system"
    STEP_START = "step_start"
    STEP_FINISH = "step_finish"


@dataclass
class AgentConfig:
    """Configuration for a CLI agent execution.

    Maps to the stdin JSON config that bridge scripts expect,
    and to the metadata that A2A server accepts.
    """
    task: str
    cwd: str
    cli_type: CLIType = CLIType.CLAUDE_CODE
    mode: AgentMode = AgentMode.RESEARCH
    tools: List[str] = field(default_factory=lambda: ["Read", "Glob", "Grep"])
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    agent_id: Optional[str] = None
    business_id: Optional[str] = None
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: Optional[str] = None
    task_id: Optional[str] = None
    docs_dir: Optional[str] = None
    chat_history: Optional[List[Dict[str, str]]] = None
    timeout_seconds: float = 1800.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentEvent:
    """A single normalized event from an agent execution.

    Events stream as the agent runs — text output, tool calls, results, errors.
    Unified format regardless of CLI type (Claude Code or OpenCode).
    """
    type: EventType
    subtype: Optional[str] = None
    text: Optional[str] = None
    tool: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    result: Optional[str] = None
    error: Optional[str] = None
    tool_use_id: Optional[str] = None
    job_id: Optional[str] = None
    seq: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.subtype in ("error", "error_agent_exit", "provider_error")

    @property
    def is_fatal(self) -> bool:
        return self.subtype in ("error_agent_exit", "provider_error")

    @property
    def is_stream_end(self) -> bool:
        return self.type == EventType.SYSTEM and self.subtype == "stream_end"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to NDJSON-compatible dict."""
        d: Dict[str, Any] = {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "_seq": self.seq,
        }
        if self.subtype:
            d["subtype"] = self.subtype
        if self.text is not None:
            d["text"] = self.text
        if self.tool:
            d["tool"] = self.tool
        if self.input is not None:
            d["input"] = self.input
        if self.output is not None:
            d["output"] = self.output
        if self.result is not None:
            d["result"] = self.result
        if self.error:
            d["error"] = self.error
        if self.tool_use_id:
            d["tool_use_id"] = self.tool_use_id
        if self.job_id:
            d["job_id"] = self.job_id
        d.update(self.metadata)
        return d


def normalize_event(raw: dict, seq: int = 0, job_id: Optional[str] = None) -> AgentEvent:
    """Normalize a raw CLI NDJSON dict into an AgentEvent.

    Handles both Claude Code and OpenCode event formats.
    Ported from a2a_server/normalize.py so consumers don't need
    the A2A server package.
    """
    etype = raw.get("type", "")
    timestamp = raw.get("timestamp", datetime.now(timezone.utc).isoformat())

    # Claude Code: assistant message with nested content array
    if etype == "assistant":
        return _normalize_assistant(raw, seq, job_id or '', timestamp)

    # OpenCode: tool_use with part.tool, part.state
    if etype == "tool_use":
        part = raw.get("part") or {}
        state = part.get("state") or {} if isinstance(part, dict) else {}
        return AgentEvent(
            type=EventType.TOOL_USE,
            tool=part.get("tool", "") if isinstance(part, dict) else "",
            input=state.get("input") if isinstance(state, dict) else None,
            output=state.get("output") if isinstance(state, dict) else None,
            tool_use_id=part.get("callID", "") if isinstance(part, dict) else "",
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    # text / reasoning
    if etype in ("text", "reasoning"):
        part = raw.get("part") or {}
        text = part.get("text", "") if isinstance(part, dict) else ""
        evt_type = EventType.REASONING if etype == "reasoning" else EventType.TEXT
        return AgentEvent(
            type=evt_type, text=text or raw.get("text", ""),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    # result (from bridge)
    if etype == "result":
        return AgentEvent(
            type=EventType.RESULT, result=raw.get("result", ""),
            subtype=raw.get("subtype"),
            error=raw.get("error"),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    # system events
    if etype == "system":
        return AgentEvent(
            type=EventType.SYSTEM, subtype=raw.get("subtype"),
            text=raw.get("text"), result=raw.get("result_text"),
            error=raw.get("error"),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
            metadata={k: v for k, v in raw.items()
                      if k not in ("type", "subtype", "text", "error", "timestamp",
                                   "result_text", "_seq", "job_id")},
        )

    # tool_result
    if etype == "tool_result":
        return AgentEvent(
            type=EventType.TOOL_RESULT, output=raw.get("output"),
            tool_use_id=raw.get("tool_use_id", ""),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    # step lifecycle (OpenCode)
    if etype in ("step_start", "step_finish"):
        evt_type = EventType.STEP_START if etype == "step_start" else EventType.STEP_FINISH
        return AgentEvent(
            type=evt_type, seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    # error events (OpenCode: {"type":"error","error":{"name":"...","data":{"message":"..."}}})
    if etype == "error":
        err = raw.get("error", {})
        err_msg = err if isinstance(err, str) else ""
        if isinstance(err, dict):
            err_data = err.get("data", {})
            err_msg = err_data.get("message", "") if isinstance(err_data, dict) else str(err_data)
            if not err_msg:
                err_msg = err.get("name", "Unknown error")
        return AgentEvent(
            type=EventType.RESULT, subtype="error",
            error=err_msg, result=err_msg,
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    # Unknown — wrap as system
    return AgentEvent(
        type=EventType.SYSTEM, subtype="unknown",
        seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
    )


def _normalize_assistant(raw: dict, seq: int, job_id: str, timestamp: str) -> AgentEvent:
    """Normalize a Claude Code assistant message with nested content blocks."""
    message = raw.get("message") or {}
    blocks = message.get("content") or []

    if not blocks:
        return AgentEvent(
            type=EventType.TEXT, text=raw.get("text", ""),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    block = blocks[0]
    bt = block.get("type", "")

    if bt == "tool_use":
        return AgentEvent(
            type=EventType.TOOL_USE, tool=block.get("name", ""),
            input=block.get("input", {}), tool_use_id=block.get("id", ""),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    if bt == "tool_result":
        output = block.get("content", "")
        if isinstance(output, list):
            output = "".join(b.get("text", "") for b in output if isinstance(b, dict))
        return AgentEvent(
            type=EventType.TOOL_RESULT, output=output,
            tool_use_id=block.get("tool_use_id", ""),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    if bt == "text":
        return AgentEvent(
            type=EventType.TEXT, text=block.get("text", ""),
            seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
        )

    return AgentEvent(
        type=EventType.TEXT, text=str(block),
        seq=seq, job_id=job_id, timestamp=timestamp, raw=raw,
    )


@runtime_checkable
class AgentExecutor(Protocol):
    """Protocol for agent execution backends.

    Implementations yield AgentEvent objects as the agent runs.
    The final event should be a stream_end system event.
    """

    async def execute(self, config: AgentConfig) -> AsyncIterator[AgentEvent]:
        """Run an agent and stream events."""
        ...

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running agent execution. Returns True if killed."""
        ...
