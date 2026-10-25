"""
LLM Service Adapters

Adapter classes to bridge different LLM backends with pattern requirements.
Patterns expect: async generate(prompt: str, model: str, temperature: float) -> str

SubprocessAgentAdapter: Spawns a CLI agent subprocess per generate() call.
The agent gets full tool use and reasoning.
"""

import os
import logging
from typing import Optional, Any

from ..agents.executor import AgentConfig, AgentMode, CLIType, EventType
from ..agents.subprocess_executor import SubprocessExecutor

logger = logging.getLogger(__name__)


class SubprocessAgentAdapter:
    """
    Adapts SubprocessExecutor to the simple interface expected by patterns.

    Each generate() call spawns a subprocess agent that can use tools,
    reason in loops, and do real work — then returns the final text result.

    Usage:
        adapter = SubprocessAgentAdapter(cwd="/path/to/project")
        context = {'services': {'llm': adapter}}
        result = await pattern.execute(context)
    """

    def __init__(
        self,
        cwd: Optional[str] = None,
        cli_type: CLIType = CLIType.CLAUDE_CODE,
        mode: AgentMode = AgentMode.RESEARCH,
        tools: Optional[list] = None,
        system_prompt: Optional[str] = None,
        bridge_dir: Optional[str] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 300.0,
    ):
        """
        Initialize adapter.

        Args:
            cwd: Working directory for agent subprocesses
            cli_type: CLI agent type (claude_code or opencode)
            mode: Agent mode (research, execute, plan)
            tools: Tool list override (defaults based on mode)
            system_prompt: Optional system prompt for all calls
            bridge_dir: Path to Node.js bridge scripts (None = direct CLI)
            provider: Optional provider name
            api_key: Optional API key
            timeout_seconds: Per-call timeout (default 5 min)
        """
        self.cwd = cwd or os.getcwd()
        self.cli_type = cli_type
        self.mode = mode
        self.tools = tools
        self.system_prompt = system_prompt
        self.provider = provider
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._executor = SubprocessExecutor(bridge_dir=bridge_dir)

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text by spawning a subprocess agent.

        Args:
            prompt: The prompt/task for the agent
            model: Optional model override
            temperature: Ignored (CLI agents don't expose temperature)
            max_tokens: Ignored (CLI agents don't expose max_tokens)
            **kwargs: Ignored

        Returns:
            Agent's final text result
        """
        config = AgentConfig(
            task=prompt,
            cwd=self.cwd,
            cli_type=self.cli_type,
            mode=self.mode,
            tools=self.tools or (
                ["Read", "Glob", "Grep", "Edit", "Write"]
                if self.mode == AgentMode.EXECUTE
                else ["Read", "Glob", "Grep"]
            ),
            system_prompt=self.system_prompt,
            model=model,
            provider=self.provider,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
        )

        result_text = ""
        error_text = ""

        async for event in self._executor.execute(config):
            if event.type == EventType.TEXT and event.text:
                result_text = event.text
            elif event.type == EventType.RESULT:
                if event.result:
                    result_text = event.result
                if event.error:
                    error_text = event.error
            if event.is_fatal:
                error_text = event.error or "Agent exited with fatal error"
                break

        if error_text and not result_text:
            logger.error("SubprocessAgentAdapter: agent failed: %s", error_text)
            return f"Error: {error_text}"

        return result_text
