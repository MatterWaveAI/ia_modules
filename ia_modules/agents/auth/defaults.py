"""Default a2a permissions by agent type.

Used when creating an agent key without explicit permissions.
Callers can override via manifest or UI.
"""

import copy

DEFAULT_A2A_PERMISSIONS: dict[str, dict] = {
    "llm": {
        "allowed_modes": ["research"],
        "allowed_tools": ["Read", "Glob", "Grep"],
        "limits": {
            "max_turns": 30,
            "max_duration_seconds": 300,
        },
    },
    "processor": {
        "allowed_modes": ["research", "plan"],
        "allowed_tools": ["Read", "Glob", "Grep"],
        "limits": {
            "max_turns": 50,
            "max_duration_seconds": 600,
        },
    },
    "custom": {
        "allowed_modes": ["research", "plan", "execute"],
        "allowed_tools": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
        "limits": {
            "max_turns": 100,
            "max_duration_seconds": 900,
        },
    },
}


def get_default_permissions(agent_type_id: str) -> dict:
    """Get default a2a permissions for an agent type.

    Falls back to 'llm' defaults for unknown types.
    """
    return copy.deepcopy(DEFAULT_A2A_PERMISSIONS.get(agent_type_id, DEFAULT_A2A_PERMISSIONS["llm"]))
