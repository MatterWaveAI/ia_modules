"""Email Classification Step - Classifies incoming emails by priority and type"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class EmailClassifierStep(PipelineStep):
    """
    Classifies emails into categories: urgent, normal, spam, automated
    Also extracts key information like sender, subject, sentiment
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.urgent_keywords = config.get("urgent_keywords", [
            "urgent", "asap", "critical", "emergency", "immediate",
            "deadline", "important", "priority", "time-sensitive"
        ])
        self.spam_keywords = config.get("spam_keywords", [
            "congratulations", "winner", "prize", "lottery", "click here",
            "free money", "nigerian prince", "act now", "limited time"
        ])

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify the email"""

        email = data.get("email", {})
        subject = email.get("subject", "").lower()
        body = email.get("body", "").lower()
        sender = email.get("from", "")

        # Classification logic
        classification = {
            "category": "normal",
            "priority": "medium",
            "is_spam": False,
            "is_automated": False,
            "requires_response": True,
            "sentiment": "neutral",
            "confidence": 0.0
        }

        # Check for spam
        spam_score = sum(1 for keyword in self.spam_keywords if keyword in subject or keyword in body)
        if spam_score >= 2:
            classification["category"] = "spam"
            classification["priority"] = "low"
            classification["is_spam"] = True
            classification["requires_response"] = False
            classification["confidence"] = min(spam_score * 0.3, 0.95)

        # Check for urgent
        elif any(keyword in subject or keyword in body for keyword in self.urgent_keywords):
            classification["category"] = "urgent"
            classification["priority"] = "high"
            classification["confidence"] = 0.85

        # Check for automated emails
        elif any(indicator in sender.lower() for indicator in ["noreply", "no-reply", "automated"]):
            classification["category"] = "automated"
            classification["priority"] = "low"
            classification["is_automated"] = True
            classification["requires_response"] = False
            classification["confidence"] = 0.9

        else:
            classification["category"] = "normal"
            classification["priority"] = "medium"
            classification["confidence"] = 0.75

        # Sentiment analysis (simplified)
        positive_words = ["thank", "appreciate", "great", "excellent", "wonderful", "pleased"]
        negative_words = ["complaint", "issue", "problem", "disappointed", "angry", "frustrated"]

        positive_count = sum(1 for word in positive_words if word in body)
        negative_count = sum(1 for word in negative_words if word in body)

        if positive_count > negative_count:
            classification["sentiment"] = "positive"
        elif negative_count > positive_count:
            classification["sentiment"] = "negative"
        else:
            classification["sentiment"] = "neutral"

        # Extract key entities
        entities = {
            "sender": sender,
            "subject": email.get("subject", ""),
            "has_attachments": email.get("attachments", []) != [],
            "word_count": len(body.split()),
            "has_questions": "?" in body
        }

        return {
            **data,
            "classification": classification,
            "entities": entities,
            "processed": True
        }
