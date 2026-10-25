"""
Flow-definition helpers shared by the runner, the loop detector and the CLI.

A flow path names its ends as either ``from``/``to`` (the documented form, and
what GraphPipelineRunner emits) or ``from_step``/``to_step`` (older pipelines
and the CLI validator's original spelling). Both are accepted everywhere:
normalize_flow() is applied once on the way in, so the engine only ever sees
``from``/``to``.
"""
from typing import Any, Dict, Optional, Tuple


def path_endpoints(path: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """The (source, target) step ids of a path, whichever spelling it uses."""
    return (
        path.get("from", path.get("from_step")),
        path.get("to", path.get("to_step")),
    )


def normalize_flow(flow: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """A copy of ``flow`` whose paths use ``from``/``to``.

    A flow whose paths already use that form is returned as it is, as is a
    flow with no paths. Other path keys (condition, metadata) are kept.
    """
    if not flow or not isinstance(flow.get("paths"), list):
        return flow

    paths = []
    changed = False
    for path in flow["paths"]:
        if isinstance(path, dict) and ("from_step" in path or "to_step" in path):
            source, target = path_endpoints(path)
            path = {k: v for k, v in path.items() if k not in ("from_step", "to_step")}
            if source is not None:
                path["from"] = source
            if target is not None:
                path["to"] = target
            changed = True
        paths.append(path)

    if not changed:
        return flow
    return {**flow, "paths": paths}
