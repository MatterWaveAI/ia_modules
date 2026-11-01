"""Test steps for branching tree pattern testing"""

from ia_modules.pipeline.core import Step
from typing import Dict, Any


class RootStep(Step):
    """Root step that branches to multiple terminal steps"""

    async def run(self, data: Dict[str, Any]) -> Any:
        value = data.get("value", "")
        return {
            "result": f"{value}_processed",
            "should_branch": data.get("should_branch", True)
        }


class AlwaysBranchStep(Step):
    """Step that always executes (terminal branch)"""

    async def run(self, data: Dict[str, Any]) -> Any:
        return {
            "result": "always_executed"
        }


class ConditionalBranchStep(Step):
    """Step that executes conditionally (terminal branch)"""

    async def run(self, data: Dict[str, Any]) -> Any:
        return {
            "result": "conditionally_executed"
        }
