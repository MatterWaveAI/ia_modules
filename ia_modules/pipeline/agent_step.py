"""AgentStep — a pipeline step that spawns a CLI agent.

Runs a CLI agent (Claude Code or OpenCode) via SubprocessExecutor as part of
a pipeline. Agent events stream to a **separate** NDJSON file (one per agent
run), linked to the pipeline execution by execution_id.

The pipeline's own NdjsonLogger gets an "agent_spawned" / "agent_completed"
event so the two log files can be correlated.

Usage in pipeline config:
    AgentStep("research", {
        "task": "Analyze the codebase for security issues",
        "cwd": "/path/to/project",
        "mode": "research",          # research | execute | plan
        "cli_type": "claude_code",   # claude_code | opencode
        "logs_dir": "/path/to/logs", # where agent NDJSON goes
        # Optional:
        "model": "claude-sonnet-4-20250514",
        "provider": "anthropic",
        "system_prompt": "You are a security auditor.",
        "tools": ["Read", "Glob", "Grep"],
        "timeout_seconds": 600,
    })
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ia_modules.agents.executor import (
    AgentConfig,
    AgentMode,
    CLIType,
    EventType,
)
from ia_modules.agents.subprocess_executor import SubprocessExecutor
from ia_modules.pipeline.core import Step
from ia_modules.pipeline.ndjson_logger import NdjsonLogger

logger = logging.getLogger(__name__)

# Map string config values to enums
_MODE_MAP = {
    "research": AgentMode.RESEARCH,
    "execute": AgentMode.EXECUTE,
    "plan": AgentMode.PLAN,
}
_CLI_MAP = {
    "claude_code": CLIType.CLAUDE_CODE,
    "opencode": CLIType.OPENCODE,
}


class AgentStep(Step):
    """Pipeline step that spawns a CLI agent subprocess.

    Config keys:
        task (str): The prompt/task for the agent. Can use ``{key}`` placeholders
            that get resolved from input data at runtime.
        cwd (str): Working directory for the agent.
        mode (str): "research", "execute", or "plan". Default "research".
        cli_type (str): "claude_code" or "opencode". Default "claude_code".
        logs_dir (str): Directory for agent NDJSON logs. Default "./logs".
        model (str): Optional model override.
        provider (str): Optional provider.
        system_prompt (str): Optional system prompt.
        tools (list[str]): Optional tool list override.
        timeout_seconds (float): Agent timeout. Default 1800.
        bridge_dir (str): Optional path to Node.js bridge scripts.

    Input data passthrough:
        The step's input ``data`` dict is available for task template resolution
        and is passed through as agent metadata. The agent's final result text
        is returned as ``{"result": "...", "agent_job_id": "...", ...}``.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self._executor: Optional[SubprocessExecutor] = None

    @property
    def agent_available(self) -> bool:
        """Whether run() can spawn an agent: an executor was set, or the host
        registered one as services['agent_executor']. Example steps use this to
        fall back to a rule-based result under pytest or the bare CLI."""
        if getattr(self, "_executor", None) is not None:
            return True
        return bool(self.services and self.services.get("agent_executor"))

    def _get_executor(self) -> SubprocessExecutor:
        """Resolve the shared SubprocessExecutor from services.

        The host app is required to register a single process-wide
        ``SubprocessExecutor`` under ``agent_executor`` on the
        pipeline's ``ServiceRegistry``. This is the one gate that
        enforces the concurrency semaphore across every pipeline run;
        constructing a fresh per-step executor would silently defeat
        it, so a missing registration is a wiring bug and raises.
        """
        if self._executor is None:
            shared = self.services.get("agent_executor") if self.services else None
            if shared is None:
                raise RuntimeError(
                    f"AgentStep '{self.name}' requires services['agent_executor'] "
                    "— register a shared SubprocessExecutor in the host app."
                )
            self._executor = shared
        return self._executor

    def _build_agent_config(self, data: Dict[str, Any]) -> AgentConfig:
        """Build AgentConfig from step config + runtime input data."""
        # Resolve task template with input data
        task = self.config.get("task", "")
        if isinstance(task, str):
            try:
                task = task.format(**data)
            except (KeyError, IndexError):
                pass  # Leave unresolved placeholders as-is

        mode_str = self.config.get("mode", "research")
        cli_str = self.config.get("cli_type", "claude_code")

        tools = self.config.get("tools")
        if tools is None:
            # Default tools based on mode
            mode = _MODE_MAP.get(mode_str, AgentMode.RESEARCH)
            if mode == AgentMode.EXECUTE:
                tools = ["Read", "Glob", "Grep", "Edit", "Write"]
            else:
                tools = ["Read", "Glob", "Grep"]

        # Resolve cwd template with input data
        cwd = self.config.get("cwd", os.getcwd())
        if isinstance(cwd, str):
            try:
                cwd = cwd.format(**data)
            except (KeyError, IndexError):
                pass

        return AgentConfig(
            task=task,
            cwd=cwd,
            cli_type=_CLI_MAP.get(cli_str, CLIType.CLAUDE_CODE),
            mode=_MODE_MAP.get(mode_str, AgentMode.RESEARCH),
            tools=tools,
            system_prompt=self.config.get("system_prompt"),
            model=self.config.get("model"),
            provider=self.config.get("provider"),
            api_key=self.config.get("api_key"),
            business_id=self.config.get("business_id"),
            agent_id=self.config.get("agent_id"),
            execution_id=data.get("_execution_id"),
            task_id=self.config.get("task_id"),
            docs_dir=self.config.get("docs_dir"),
            timeout_seconds=self.config.get("timeout_seconds", 1800.0),
            metadata={**data, "logs_dir": self.config.get("logs_dir", "./logs")},
        )

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Spawn agent, stream events to agent NDJSON file, return result."""
        agent_config = self._build_agent_config(data)
        job_id = agent_config.job_id
        executor = self._get_executor()

        # Determine execution_id from pipeline context if available
        execution_id = data.get("_execution_id") or data.get("execution_id")

        # Set up agent-specific NDJSON log file
        logs_dir = self.config.get("logs_dir", "./logs")
        agent_log_path = Path(logs_dir) / job_id / "agent.jsonl"
        agent_logger = NdjsonLogger(
            str(agent_log_path),
            default_metadata={
                "job_id": job_id,
                "execution_id": execution_id,
                "step_name": self.name,
            },
        )

        # Get pipeline's ndjson logger (if registered)
        pipeline_ndjson = self.services.get("ndjson_logger") if self.services else None

        # Get central logger (if registered)
        central_logger = self.services.get("central_logger") if self.services else None

        # Log agent spawn to pipeline log
        if pipeline_ndjson:
            await pipeline_ndjson.log(
                "system", subtype="agent_spawned",
                step_name=self.name,
                agent_job_id=job_id,
                agent_log_path=str(agent_log_path),
                agent_mode=agent_config.mode.value,
                agent_cli_type=agent_config.cli_type.value,
                agent_task=agent_config.task[:200],
            )
        if central_logger:
            central_logger.info(
                f"Agent spawned: job={job_id} mode={agent_config.mode.value}",
                step_name=self.name,
                data={"agent_job_id": job_id, "agent_log_path": str(agent_log_path)},
            )

        self.logger.info(
            "Spawning agent: job=%s mode=%s cli=%s",
            job_id, agent_config.mode.value, agent_config.cli_type.value,
        )

        # Stream agent events to agent-specific NDJSON file
        result_text = ""
        error_text = ""
        event_count = 0

        try:
            async for event in executor.execute(agent_config):
                event_count += 1
                # Write every agent event to the agent's own log
                await agent_logger.log(
                    event.type.value,
                    subtype=event.subtype,
                    text=event.text,
                    result=event.result,
                    error=event.error,
                    tool=event.tool,
                    tool_use_id=event.tool_use_id,
                    data={"input": event.input} if event.input else None,
                    output=event.output,
                )

                # Capture final result (prefer TEXT over generic RESULT)
                if event.type == EventType.TEXT and event.text:
                    result_text = event.text
                elif event.type == EventType.RESULT:
                    if event.result and not result_text:
                        result_text = event.result
                    if event.error:
                        error_text = event.error

                if event.is_fatal:
                    error_text = event.error or "Agent exited with fatal error"
                    break
        except (FileNotFoundError, OSError) as e:
            error_text = f"Agent setup failed: {e}"
            self.logger.error("Agent setup failed: %s", e)
        except asyncio.CancelledError:
            self.logger.warning("Agent %s cancelled", job_id)
            await agent_logger.close()
            raise
        except KeyboardInterrupt:
            self.logger.warning("Agent %s interrupted", job_id)
            await agent_logger.close()
            raise
        finally:
            await agent_logger.close()

        # Log agent completion to pipeline log
        if pipeline_ndjson:
            await pipeline_ndjson.log(
                "system",
                subtype="agent_error" if error_text else "agent_completed",
                step_name=self.name,
                agent_job_id=job_id,
                event_count=event_count,
                error=error_text or None,
            )
        if central_logger:
            if error_text:
                central_logger.error(
                    f"Agent failed: job={job_id} error={error_text[:200]}",
                    step_name=self.name,
                    data={"agent_job_id": job_id},
                )
            else:
                central_logger.success(
                    f"Agent completed: job={job_id} events={event_count}",
                    step_name=self.name,
                    data={"agent_job_id": job_id, "event_count": event_count},
                )

        self.logger.info("Agent finished: job=%s events=%d", job_id, event_count)

        # Build step output
        output: Dict[str, Any] = {
            "result": result_text,
            "agent_job_id": job_id,
            "agent_log_path": str(agent_log_path),
            "event_count": event_count,
        }
        if error_text:
            if "interrupted" in error_text.lower():
                self.logger.warning("Agent %s interrupted", job_id)
                output["error"] = "Agent interrupted"
                return output
            if result_text:
                # Agent produced output but exited non-zero (common with opencode).
                # Treat as a warning, not a failure.
                self.logger.warning("Agent %s exited non-zero but produced output", job_id)
            else:
                output["error"] = error_text
                raise RuntimeError(
                    f"Agent step '{self.name}' failed: {error_text}"
                )

        return output
