"""
Step 3: Data Finalization
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class Step3(Step):
    """Third step to finalize and format the data for output"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize and format the data for output"""

        # Get topic from resolved inputs
        current_topic = input.get("topic", "unknown")
        transformed_topic = f"FINAL_{current_topic[::-1]}"

        # Return the final transformed topic
        return {"topic": transformed_topic}
