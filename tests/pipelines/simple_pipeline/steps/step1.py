"""
Step 1: Data Preparation
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class Step1(Step):
    """First step to prepare and transform input data"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare and transform input data using resolved inputs"""

        # Get topic from resolved inputs
        topic = input.get("topic", "unknown")

        # Handle None case
        if topic is None:
            topic = "unknown"

        # Transform the topic - make it uppercase and add prefix
        transformed_topic = f"PROCESSED_{topic.upper()}"

        # Return the transformed topic directly
        return {"topic": transformed_topic}