"""
Agent Execution System

Provides CLI agent execution via subprocess or A2A server,
plus graph-based orchestration for multi-agent workflows.

Core Components:
- AgentExecutor: Protocol for agent execution backends
- SubprocessExecutor: Spawns CLI agent directly (default)
- A2AExecutor: Dispatches to A2A server via JSON-RPC
- AgentOrchestrator: Graph-based workflow execution
- StateManager: Centralized state with versioning
"""

# Core agent infrastructure
from .core import AgentRole, BaseAgent
from .state import StateManager
from .orchestrator import AgentOrchestrator, Edge

# CLI agent execution
from .executor import (
    AgentExecutor,
    AgentConfig,
    AgentEvent,
    EventType,
    CLIType,
    AgentMode,
    normalize_event,
)
from .subprocess_executor import SubprocessExecutor
from .a2a_executor import A2AExecutor
from .permissions import enforce_agent_claims, ClaimsViolation


__all__ = [
    # Core components
    "AgentRole",
    "BaseAgent",
    "StateManager",
    "AgentOrchestrator",
    "Edge",

    # CLI agent execution
    "AgentExecutor",
    "AgentConfig",
    "AgentEvent",
    "EventType",
    "CLIType",
    "AgentMode",
    "normalize_event",
    "SubprocessExecutor",
    "A2AExecutor",
    "enforce_agent_claims",
    "ClaimsViolation",
]
