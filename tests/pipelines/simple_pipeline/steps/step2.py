"""
Step 2: Data Enrichment
"""

from typing import Dict, Any

from ia_modules.pipeline.core import Step


class Step2(Step):
    """Second step to enrich the data with additional information"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich the data with additional information"""

        # Get topic from resolved inputs
        current_topic = input.get("topic", "unknown")
        transformed_topic = f"{current_topic.lower()}_enriched"

        # Return the transformed topic directly
        return {"topic": transformed_topic}
