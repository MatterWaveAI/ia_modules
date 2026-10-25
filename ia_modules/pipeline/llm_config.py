"""
LLM and agent configuration from the environment.

Shared by whatever runs LLMStep or AgentStep: the showcase backend, the
example pipelines under tests/pipelines, and your own steps.

Environment variables:
    DEFAULT_LLM_PROVIDER  - CLI type: "opencode" or "claude_code" (default "opencode")
    LLM_PROVIDER          - provider name passed to the CLI (e.g. "zai-coding-plan")
    LLM_MODEL             - model name (e.g. "glm-5.1")
    LLM_API_KEY           - API key for the provider

    AGENT_CWD             - workspace the agents run in (default: the root given, or the working directory)
    AGENT_LOGS_DIR        - directory for agent NDJSON logs (default: <root>/logs/agents)
    AGENT_TIMEOUT         - timeout in seconds (default: 120)

Tools are defined per agent role, not globally; the mode is derived from them.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


@lru_cache(maxsize=1)
def get_llm_config() -> Dict[str, Any]:
    """LLM settings from the environment: cli_type, plus provider/model/api_key when set."""
    cli_type = os.getenv("DEFAULT_LLM_PROVIDER", "opencode").strip().lower()
    config: Dict[str, Any] = {"cli_type": cli_type}
    for key, variable in (("provider", "LLM_PROVIDER"), ("model", "LLM_MODEL"), ("api_key", "LLM_API_KEY")):
        value = os.getenv(variable, "").strip()
        if value:
            config[key] = value
    return config


_WRITE_TOOLS = {"Edit", "Write", "Bash"}


def derive_mode(tools: list[str]) -> str:
    """"execute" when any tool can change files (Edit, Write, Bash), otherwise "research"."""
    return "execute" if _WRITE_TOOLS.intersection(tools) else "research"


@lru_cache(maxsize=None)
def get_agent_config(root: Optional[str] = None) -> Dict[str, Any]:
    """Agent workspace settings from the environment: cwd, logs_dir, timeout_seconds.

    Relative AGENT_CWD and AGENT_LOGS_DIR resolve against ``root`` (default: the
    working directory). Cached per root, so the directories are created once.
    """
    base = Path(root or os.getcwd()).resolve()
    cwd_raw = os.getenv("AGENT_CWD", "").strip()
    cwd = str(base.joinpath(cwd_raw).resolve()) if cwd_raw else str(base)
    logs_raw = os.getenv("AGENT_LOGS_DIR", "").strip()
    logs_dir = str(base.joinpath(logs_raw).resolve()) if logs_raw else str(base / "logs" / "agents")
    timeout = int(os.getenv("AGENT_TIMEOUT", "120"))

    Path(cwd).mkdir(parents=True, exist_ok=True)
    Path(logs_dir).mkdir(parents=True, exist_ok=True)

    return {"cwd": cwd, "logs_dir": logs_dir, "timeout_seconds": timeout}
