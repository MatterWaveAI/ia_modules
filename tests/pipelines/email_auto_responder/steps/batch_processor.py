"""Batch Processor Step - Processes multiple emails in batch"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class BatchProcessorStep(PipelineStep):
    """
    Processes multiple emails in batch, applying classification
    and response generation to each email
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process all fetched emails"""

        emails = data.get("emails", [])

        if not emails:
            return {
                **data,
                "processed_emails": [],
                "summary": {
                    "total": 0,
                    "processed": 0,
                    "urgent": 0,
                    "normal": 0,
                    "spam": 0,
                    "automated": 0,
                    "responses_generated": 0
                }
            }

        # Import the classifier and response generator
        from .email_classifier import EmailClassifierStep
        from .response_generator import ResponseGeneratorStep

        # Create step instances
        classifier = EmailClassifierStep("classifier", self.config)
        response_generator = ResponseGeneratorStep("response_generator", self.config)

        processed_emails = []
        summary = {
            "total": len(emails),
            "processed": 0,
            "urgent": 0,
            "normal": 0,
            "spam": 0,
            "automated": 0,
            "responses_generated": 0,
            "errors": 0
        }

        for idx, email_data in enumerate(emails):
            try:
                # Classify email
                classify_result = await classifier.run({"email": email_data})
                classification = classify_result.get("classification", {})

                # Generate response
                response_result = await response_generator.run({
                    "email": email_data,
                    "classification": classification,
                    "entities": classify_result.get("entities", {})
                })

                # Track stats
                category = classification.get("category", "normal")
                summary[category] = summary.get(category, 0) + 1
                summary["processed"] += 1

                if response_result.get("ready_to_send"):
                    summary["responses_generated"] += 1

                processed_emails.append({
                    "index": idx,
                    "email": email_data,
                    "classification": classification,
                    "entities": classify_result.get("entities", {}),
                    "response": response_result.get("response"),
                    "action": response_result.get("action"),
                    "ready_to_send": response_result.get("ready_to_send", False)
                })

            except Exception as e:
                summary["errors"] += 1
                processed_emails.append({
                    "index": idx,
                    "email": email_data,
                    "error": str(e),
                    "action": "error"
                })

        return {
            **data,
            "processed_emails": processed_emails,
            "summary": summary,
            "processing_complete": True
        }
