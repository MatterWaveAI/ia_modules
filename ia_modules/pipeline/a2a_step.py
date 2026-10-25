"""A2AStep — dispatches work to a remote A2A agent server.

Pipeline/orchestrator step that sends agent execution to a remote A2A
server via JSON-RPC. The A2A server handles subprocess spawning, NDJSON
normalization, and log persistence.

Usage in pipeline config:
    A2AStep("remote_researcher", {
        "task": "Analyze the codebase for security issues",
        "a2a_url": "http://agent-server:3008",
        "mode": "research",
        "cli_type": "claude_code",
        "system_prompt": "You are a security auditor.",
        "tools": ["Read", "Glob", "Grep"],
    })
"""

import logging
import os
from typing import Any, Dict, Optional

from ia_modules.agents.a2a_executor import A2AExecutor
from ia_modules.agents.executor import (
    AgentConfig,
    AgentMode,
    CLIType,
    EventType,
)
from ia_modules.pipeline.core import Step

logger = logging.getLogger(__name__)

_MODE_MAP = {
    "research": AgentMode.RESEARCH,
    "execute": AgentMode.EXECUTE,
    "plan": AgentMode.PLAN,
}
_CLI_MAP = {
    "claude_code": CLIType.CLAUDE_CODE,
    "opencode": CLIType.OPENCODE,
}


class A2AStep(Step):
    """Pipeline step that dispatches to a remote A2A agent server.

    Config keys:
        task (str): Prompt for the agent. Supports {key} placeholders.
        a2a_url (str): A2A server URL. Default from A2A_SERVER_URL env.
        callback_url (str): Where server posts events back.
        mode (str): "research" | "execute" | "plan". Default "research".
        cli_type (str): "claude_code" | "opencode". Default "claude_code".
        model (str): Optional model override.
        provider (str): Optional provider.
        system_prompt (str): Optional system prompt.
        tools (list[str]): Optional tool list.
        cwd (str): Working directory for remote agent.
        timeout_seconds (float): Agent timeout. Default 1800.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self._executor: Optional[A2AExecutor] = None

    def _get_executor(self) -> A2AExecutor:
        """Get or create the A2AExecutor."""
        if self._executor is None:
            self._executor = A2AExecutor(
                a2a_url=self.config.get("a2a_url"),
                callback_url=self.config.get("callback_url"),
            )
        return self._executor

    def _build_agent_config(self, data: Dict[str, Any]) -> AgentConfig:
        """Build AgentConfig from step config + runtime input data."""
        task = self.config.get("task", "")
        if isinstance(task, str):
            try:
                task = task.format(**data)
            except (KeyError, IndexError):
                pass

        mode_str = self.config.get("mode", "research")
        cli_str = self.config.get("cli_type", "claude_code")
        tools = self.config.get("tools") or ["Read", "Glob", "Grep"]

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
            agent_id=self.config.get("agent_id"),
            business_id=self.config.get("business_id"),
            execution_id=data.get("_execution_id"),
            task_id=self.config.get("task_id"),
            timeout_seconds=self.config.get("timeout_seconds", 1800.0),
            metadata=data,
        )

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to A2A server and return submission result."""
        agent_config = self._build_agent_config(data)
        executor = self._get_executor()

        # Log to pipeline NDJSON if available
        pipeline_ndjson = self.get_ndjson_logger()
        if pipeline_ndjson:
            await pipeline_ndjson.log(
                "system", subtype="a2a_dispatched",
                step_name=self.name,
                agent_job_id=agent_config.job_id,
                a2a_url=executor.a2a_url,
                agent_mode=agent_config.mode.value,
                agent_cli_type=agent_config.cli_type.value,
                agent_task=agent_config.task[:200],
            )

        self.logger.info(
            "Dispatching to A2A: job=%s url=%s mode=%s",
            agent_config.job_id, executor.a2a_url, agent_config.mode.value,
        )

        result_event = None
        error_text = ""

        async for event in executor.execute(agent_config):
            if event.type == EventType.SYSTEM and event.subtype == "submitted":
                result_event = event
            elif event.is_error:
                error_text = event.error or "A2A server error"

        if pipeline_ndjson:
            await pipeline_ndjson.log(
                "system",
                subtype="a2a_error" if error_text else "a2a_submitted",
                step_name=self.name,
                agent_job_id=agent_config.job_id,
                error=error_text or None,
            )

        if error_text and not result_event:
            raise RuntimeError(f"A2A step '{self.name}' failed: {error_text}")

        return {
            "agent_job_id": agent_config.job_id,
            "a2a_url": executor.a2a_url,
            "submitted": result_event is not None,
            "task_id": agent_config.job_id,
        }
