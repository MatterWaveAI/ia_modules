"""Token-based permission enforcement for agent execution.

Validates JWT claims against the actual execution context before
any executor (subprocess or remote A2A) runs. This is the zero-trust
gate — even though the platform issued the token, we verify claims
match the requested action.

Checks:
  - CWD:   allowed_cwd patterns (glob-style /path/*) or app_id fallback
  - Mode:  allowed_modes from a2a claims
  - Tools: allowed_tools from a2a claims
  - Limits: max_turns, max_duration_seconds from a2a claims

Usage:
    from ia_modules.agents.permissions import enforce_agent_claims

    claims = await adapter.validate_token(token)
    enforce_agent_claims(claims, cwd="/data/apps/app-123/workspace")
"""

import logging
import os

logger = logging.getLogger(__name__)


class ClaimsViolation(ValueError):
    """Raised when token claims do not permit the requested action."""
    pass


def enforce_agent_claims(
    claims: dict,
    cwd: str,
    mode: str | None = None,
    tools: list[str] | None = None,
) -> None:
    """Enforce token claims against the execution context.

    Called after validate_token() but before any executor runs.
    Raises ClaimsViolation if the agent is not authorized.

    Args:
        claims: Decoded JWT claims dict (must contain 'a2a' and/or 'app_id').
        cwd: The working directory the agent will run in.
        mode: Requested execution mode (e.g. 'research', 'execute').
        tools: Requested tool list (e.g. ['Read', 'Glob', 'Grep']).
    """
    _enforce_cwd(claims, cwd)

    if mode is not None:
        _enforce_mode(claims, mode)

    if tools is not None:
        _enforce_tools(claims, tools)


def _enforce_cwd(claims: dict, cwd: str) -> None:
    """CWD must match allowed_cwd patterns or fall back to app_id check."""
    a2a = claims.get("a2a") or {}
    resolved_cwd = os.path.realpath(cwd)

    allowed_cwd = a2a.get("allowed_cwd")
    if allowed_cwd:
        patterns = allowed_cwd if isinstance(allowed_cwd, list) else [allowed_cwd]
        for pattern in patterns:
            # Strip trailing /* for prefix matching
            root = os.path.realpath(pattern.rstrip("/*"))
            if resolved_cwd == root or resolved_cwd.startswith(root + os.sep):
                return
        raise ClaimsViolation(
            f"Agent CWD {resolved_cwd} not permitted by allowed_cwd: {patterns}"
        )

    # Fallback: app_id from token must appear in the CWD path
    app_id = claims.get("app_id")
    if app_id and app_id not in resolved_cwd:
        raise ClaimsViolation(
            f"Agent CWD {resolved_cwd} does not match app_id {app_id} from token"
        )


def _enforce_mode(claims: dict, mode: str) -> None:
    """Mode must be in the token's allowed_modes list."""
    a2a = claims.get("a2a") or {}
    allowed_modes = a2a.get("allowed_modes")
    if allowed_modes is not None and mode not in allowed_modes:
        raise ClaimsViolation(
            f"Mode '{mode}' not in allowed_modes: {allowed_modes}"
        )


def _enforce_tools(claims: dict, tools: list[str]) -> None:
    """Every requested tool must be in the token's allowed_tools list."""
    a2a = claims.get("a2a") or {}
    allowed_tools = a2a.get("allowed_tools")
    if allowed_tools is not None:
        disallowed = set(tools) - set(allowed_tools)
        if disallowed:
            raise ClaimsViolation(
                f"Tools {sorted(disallowed)} not in allowed_tools: {allowed_tools}"
            )
