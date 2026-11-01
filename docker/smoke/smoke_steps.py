"""Smoke-test steps for the agent-runner image.

Two trivial steps the release CI strings into `smoke_pipeline.yaml` to
prove the whole runner story against a real Postgres:

1. First attempt runs with `SMOKE_FAIL_STEP=verify`: EchoStep stamps its
   marker and checkpoints, then verify dies. Exit code non-zero.
2. The retry runs with the same `IA_RUN_ID` and a different marker. The
   runner must resume from the checkpoint — so the output carries the
   FIRST attempt's marker (`run-a`), proving EchoStep did not rerun.

If the marker comes back `run-b`, the retry reran the pipeline and the
resume wiring is broken — the smoke job fails.
"""

import os
from typing import Any, Dict

from ia_modules.pipeline.core import Step


def _fail_if_injected(step: Step) -> None:
    """Raise when SMOKE_FAIL_STEP names this step (smoke-run kill switch)."""
    if os.environ.get("SMOKE_FAIL_STEP") == step.name:
        raise RuntimeError(f"injected smoke failure (SMOKE_FAIL_STEP={step.name})")


class EchoStep(Step):
    """Stamp SMOKE_MARKER into the data."""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        _fail_if_injected(self)
        result = dict(data)
        result["echo_marker"] = os.environ.get("SMOKE_MARKER", "unset")
        return result


class VerifyStep(Step):
    """Pass-through step: gives the flow a second hop to resume across."""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        _fail_if_injected(self)
        result = dict(data)
        result["verify_done"] = True
        return result
