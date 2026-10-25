"""Test steps for data flow pipeline testing"""

from ia_modules.pipeline.core import Step
from typing import Dict, Any


class DataTransformStep(Step):
    """Test step that transforms data"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Transform input data by adding a processed flag and multiplying value
        result = {
            **data,
            f"{self.name}_processed": True,
            "value": data.get("value", 0) * 2
        }
        return result


class DataAccumulatorStep(Step):
    """Test step that accumulates data from previous steps"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Accumulate all data and add summary
        history = data.get("_history", [])
        current_value = data.get("value", 0)

        result = {
            **data,
            "_history": history + [current_value],
            "accumulated": sum(history) + current_value,
            f"{self.name}_complete": True
        }
        return result


class DataFilterStep(Step):
    """Test step that filters data based on conditions"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Filter out internal keys (starting with _)
        filtered = {k: v for k, v in data.items() if not k.startswith("_")}
        filtered["filtered_keys"] = [k for k in data.keys() if k.startswith("_")]
        filtered[f"{self.name}_filtered"] = True
        return filtered


class DataValidatorStep(Step):
    """Test step that validates data schema"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Validate required fields exist
        required_fields = self.config.get("required_fields", [])
        missing = [f for f in required_fields if f not in data]

        result = {
            **data,
            "validation_passed": len(missing) == 0,
            "missing_fields": missing,
            f"{self.name}_validated": True
        }
        return result
