"""Example pipeline steps for showcase app"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from ia_modules.pipeline.core import Step
import asyncio
import random
from datetime import datetime, timezone


class TransformStep(Step):
    """Simple text transform step"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        text = data.get("text", "")
        operation = self.config.get("operation", "uppercase")
        await asyncio.sleep(0.3)

        if operation == "uppercase":
            text = text.upper()
        elif operation == "lowercase":
            text = text.lower()
        elif operation == "reverse":
            text = text[::-1]

        return {"text": text}


class GreetingStep(Step):
    """Simple greeting step"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        name = data.get("name", "World")
        await asyncio.sleep(0.5)  # Simulate work

        return {
            "message": f"Hello, {name}!",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class LoadDataStep(Step):
    """Load data step"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        await asyncio.sleep(0.7)

        # Simulate loading data
        return {
            "records": [
                {"id": 1, "value": 100},
                {"id": 2, "value": 200},
                {"id": 3, "value": 300},
            ],
            "count": 3
        }


class ValidateDataStep(Step):
    """Validate data step"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        await asyncio.sleep(0.5)

        records = data.get("records", [])

        # Validate all records have required fields
        valid = all("id" in r and "value" in r for r in records)

        if not valid:
            raise ValueError("Invalid data format")

        return {
            "records": records,
            "validated": True
        }


class TransformDataStep(Step):
    """Transform data step"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        await asyncio.sleep(0.8)

        records = data.get("records", [])

        # Transform: add 10% to all values
        transformed = [
            {**r, "value": r["value"] * 1.1, "transformed": True}
            for r in records
        ]

        return {
            "records": transformed,
            "count": len(transformed)
        }


class ExportDataStep(Step):
    """Export data step"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        await asyncio.sleep(0.6)

        records = data.get("records", [])

        # Simulate export
        export_path = f"/tmp/export_{datetime.now(timezone.utc).timestamp()}.json"

        return {
            "exported": len(records),
            "path": export_path,
            "status": "complete"
        }


class RetryDemoStep(Step):
    """Demonstrates retry logic"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.attempt_count = 0

    async def run(self, data: dict) -> dict:
        self.attempt_count += 1
        await asyncio.sleep(0.5)

        # Simulate random failure (70% success rate)
        success = random.random() > 0.3

        if success:
            return {
                "attempt": self.attempt_count,
                "message": f"Succeeded on attempt {self.attempt_count}",
                "status": "completed"
            }
        else:
            raise Exception(f"Failed on attempt {self.attempt_count}")


class ParallelProcessStep(Step):
    """Step for parallel processing demo"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.step_id = config.get("step_id", name)

    async def run(self, data: dict) -> dict:
        # Simulate varying work time
        work_time = random.uniform(0.5, 2.0)
        await asyncio.sleep(work_time)

        return {
            "step_id": self.step_id,
            "processing_time": work_time,
            "result": f"Processed by {self.step_id}"
        }


class HumanApprovalStep(Step):
    """Human approval step (HITL demo)"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        # In a real implementation, this would:
        # 1. Save state to database
        # 2. Send notification to reviewer
        # 3. Wait for external resume signal
        # 4. Load state and continue

        # For demo, we'll just simulate it
        content = data.get("content", "Sample content")

        return {
            "status": "awaiting_approval",
            "content": content,
            "message": "This step requires human approval"
        }
