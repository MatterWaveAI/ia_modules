"""
Shared LLM and agent configuration loader.

Reads provider, model, API key, workspace, tools, and logging config from
environment variables (loaded by main.py via dotenv).

Environment variables (see .env.example):
    DEFAULT_LLM_PROVIDER  - CLI type: "opencode" or "anthropic"
    LLM_PROVIDER          - provider name passed to CLI (e.g. "zai-coding-plan")
    LLM_MODEL             - model name (e.g. "glm-5.1")
    LLM_API_KEY           - API key for the provider
    PATTERN_MAX_TOKENS    - max tokens (default 2000)
    PATTERN_TEMPERATURE   - temperature (default 0.7)

    AGENT_CWD             - shared workspace for agents (default: project root)
    AGENT_LOGS_DIR        - directory for agent NDJSON logs (default: ./logs/agents)
    AGENT_TIMEOUT         - timeout in seconds (default: 120)

Tools are defined per agent role, not globally. Mode is derived from tools.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ia_modules.agents.subprocess_executor import (
    get_shared_executor,
)
# The environment readers live in the library, shared with the example pipelines;
# here relative AGENT_CWD / AGENT_LOGS_DIR resolve against showcase_app/.
from ia_modules.pipeline.llm_config import derive_mode, get_llm_config  # noqa: F401  (re-exported)
from ia_modules.pipeline.llm_config import get_agent_config as _get_agent_config
from ia_modules.pipeline.llm_step import LLMStep
from ia_modules.pipeline.services import ServiceRegistry

logger = logging.getLogger(__name__)

# Default project root (two levels up from this file: services/ -> backend/ -> showcase_app/)
_DEFAULT_CWD = str(Path(__file__).resolve().parent.parent.parent)


def get_agent_config() -> Dict[str, Any]:
    """Agent workspace settings: cwd, logs_dir, timeout_seconds."""
    return _get_agent_config(_DEFAULT_CWD)


class LLMCallResult:
    """Result of an llm_call — carries text and the NDJSON job_id."""
    __slots__ = ("text", "job_id", "event_count")

    def __init__(self, text: Optional[str], job_id: Optional[str] = None, event_count: int = 0):
        self.text = text
        self.job_id = job_id
        self.event_count = event_count

    def __bool__(self):
        return self.text is not None

    def __str__(self):
        return self.text or ""


async def llm_call(
    system_prompt: str,
    user_message: str,
    timeout: int = 120,
    step_name: str = "_shared_llm",
    **extra_config: Any,
) -> LLMCallResult:
    """Make an LLM call via LLMStep using env-configured provider.

    Returns an LLMCallResult with .text and .job_id.
    .text is None on failure (caller should fall back).
    .job_id is the NDJSON log directory name (for reading events later).
    Uses AGENT_CWD as working directory so opencode.json is written there.
    """
    env_config = get_llm_config()
    agent_cfg = get_agent_config()
    step_config = {
        "system_prompt": system_prompt,
        "timeout_seconds": timeout,
        "cwd": agent_cfg["cwd"],
        "logs_dir": agent_cfg["logs_dir"],
        **env_config,
        **extra_config,
    }

    executor = get_shared_executor()

    step = LLMStep(step_name, step_config)
    # Attach a minimal service registry carrying the shared executor
    # so AgentStep._get_executor() finds it (standalone steps have no
    # orchestrator wiring services for them).
    step_services = ServiceRegistry()
    step_services.register("agent_executor", executor)
    step.services = step_services

    try:
        result = await step.run({"prompt": user_message})
    except Exception as e:
        logger.warning("LLM call failed (step=%s): %s", step_name, e, exc_info=True)
        return LLMCallResult(None)

    text = result.get("text", "").strip() or None
    return LLMCallResult(text, result.get("agent_job_id"), result.get("event_count", 0))
