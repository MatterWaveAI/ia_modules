"""LLMStep — a pipeline step for simple LLM prompt execution.

Extends AgentStep to handle the common case where you just want to send a
system prompt + user input to a CLI agent and get a text response back.
No workspace or code needed — just prompt in, text out.

Usage in pipeline config:
    steps:
      - name: chat_response
        step_class: LLMStep
        config:
          system_prompt: "You are a helpful AI assistant."
          temperature: 0.7
          max_tokens: 2048
          cli_type: opencode       # or claude_code
          mode: research           # research | execute | plan
          # Optional:
          model: "glm-5"
          provider: "zai-coding-plan"

The user's message is passed via input_data["prompt"] or input_data["message"].
"""

import logging
import tempfile
from typing import Any, Dict

from .agent_step import AgentStep

logger = logging.getLogger(__name__)


class LLMStep(AgentStep):
    """Pipeline step that sends a prompt to a CLI agent and returns the response.

    This is a thin wrapper around AgentStep that:
    1. Builds the task from system_prompt + user input (no explicit "task" config needed)
    2. Uses a temp directory as cwd (no workspace required)
    3. Defaults to research mode with no tools (pure LLM conversation)

    Config keys (in addition to AgentStep keys):
        system_prompt (str): System instructions for the LLM.
        temperature (float): Generation temperature (passed as metadata).
        max_tokens (int): Max response tokens (passed as metadata).
    """

    def _build_task_from_input(self, data: Dict[str, Any]) -> str:
        """Compose the agent task from system_prompt + user input."""
        system_prompt = self.config.get(
            "system_prompt", "You are a helpful AI assistant."
        )
        user_message = (
            data.get("prompt")
            or data.get("message")
            or data.get("text")
            or data.get("input", "")
        )
        return f"{system_prompt}\n\nUser: {user_message}"

    def _build_agent_config(self, data: Dict[str, Any]):
        """Override to inject the composed task and sensible defaults."""
        # Set the task from prompt + input
        self.config.setdefault("task", "")
        self.config["task"] = self._build_task_from_input(data)

        # Use a temp dir as cwd — LLM steps don't need a workspace
        if "cwd" not in self.config:
            self.config["cwd"] = tempfile.gettempdir()

        # Default to research mode with no tools (pure conversation)
        self.config.setdefault("mode", "research")
        if "tools" not in self.config:
            self.config["tools"] = []

        # Shorter timeout for simple LLM calls
        self.config.setdefault("timeout_seconds", 120)

        return super()._build_agent_config(data)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the LLM step and return the response text."""
        result = await super().run(data)

        # Normalize output — the consumer expects {"text": "..."} for chat agents
        response_text = result.get("result", "")
        return {
            "text": response_text,
            "result": response_text,
            "agent_job_id": result.get("agent_job_id"),
            "event_count": result.get("event_count", 0),
        }
