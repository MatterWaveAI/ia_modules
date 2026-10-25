"""Response Generation Step - Generates appropriate email responses"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class ResponseGeneratorStep(PipelineStep):
    """
    Generates contextually appropriate email responses based on
    classification and content analysis
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.sender_name = config.get("sender_name", "Support Team")
        self.sender_email = config.get("sender_email", "support@company.com")
        self.company_name = config.get("company_name", "Our Company")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate appropriate response"""

        classification = data.get("classification", {})
        entities = data.get("entities", {})
        email = data.get("email", {})

        category = classification.get("category", "normal")
        sentiment = classification.get("sentiment", "neutral")
        requires_response = classification.get("requires_response", True)

        if not requires_response:
            return {
                **data,
                "response": None,
                "action": "no_response_needed",
                "reason": f"Email classified as {category} - no response required"
            }

        # Generate response based on category and sentiment
        response = self._generate_response(
            category=category,
            sentiment=sentiment,
            email=email,
            entities=entities
        )

        return {
            **data,
            "response": response,
            "action": "response_generated",
            "ready_to_send": True
        }

    def _generate_response(
        self,
        category: str,
        sentiment: str,
        email: Dict[str, Any],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate response based on email characteristics"""

        sender = entities.get("sender", "")
        subject = entities.get("subject", "")
        has_questions = entities.get("has_questions", False)

        # Base response structure
        response = {
            "to": sender,
            "from": self.sender_email,
            "subject": f"Re: {subject}",
            "body": "",
            "priority": "normal",
            "tone": "professional"
        }

        # Urgent emails
        if category == "urgent":
            response["priority"] = "high"
            response["tone"] = "prompt"

            if sentiment == "negative":
                response["body"] = f"""Thank you for bringing this urgent matter to our attention.

We understand the critical nature of your request and have immediately escalated it to our priority queue. A senior team member will review your case and respond within the next 2 hours.

Your issue reference number is: #{self._generate_ticket_id()}

We appreciate your patience as we work to resolve this as quickly as possible.

Best regards,
{self.sender_name}
{self.company_name}"""
            else:
                response["body"] = f"""Thank you for your urgent message.

We've received your request and have prioritized it for immediate attention. Our team is currently reviewing the details and will respond with next steps within 2 hours.

Reference: #{self._generate_ticket_id()}

Best regards,
{self.sender_name}
{self.company_name}"""

        # Normal emails with questions
        elif has_questions:
            response["tone"] = "helpful"

            if sentiment == "negative":
                response["body"] = f"""Thank you for reaching out, and I apologize for any inconvenience you've experienced.

I've carefully reviewed your questions and concerns. To provide you with the most accurate and helpful response, I'd like to gather a bit more information about your situation.

A member of our support team will contact you within 24 hours to address your specific questions and work toward a resolution.

Ticket Reference: #{self._generate_ticket_id()}

We value your business and appreciate your patience.

Best regards,
{self.sender_name}
{self.company_name}"""
            else:
                response["body"] = f"""Thank you for your inquiry!

I've received your questions and want to ensure you get the most helpful response possible. Our team is reviewing the details and will provide a comprehensive answer within 24 hours.

In the meantime, you might find these resources helpful:
- Knowledge Base: www.company.com/help
- FAQ: www.company.com/faq

Your ticket reference: #{self._generate_ticket_id()}

Best regards,
{self.sender_name}
{self.company_name}"""

        # Normal emails - acknowledgment
        else:
            response["tone"] = "friendly"

            if sentiment == "positive":
                response["body"] = f"""Thank you so much for your kind message!

We truly appreciate your feedback and are delighted to hear about your positive experience. Messages like yours make what we do so rewarding.

If you ever need anything else, please don't hesitate to reach out. We're always here to help!

Warm regards,
{self.sender_name}
{self.company_name}"""

            elif sentiment == "negative":
                response["body"] = f"""Thank you for taking the time to share your feedback.

I'm sorry to hear about your experience, and I want to assure you that we take all feedback seriously. We've documented your concerns and will investigate this matter thoroughly.

A team member will reach out within 24-48 hours to discuss this further and work toward a satisfactory resolution.

Reference: #{self._generate_ticket_id()}

We appreciate your patience and the opportunity to make this right.

Best regards,
{self.sender_name}
{self.company_name}"""

            else:
                response["body"] = f"""Thank you for your email.

We've received your message and wanted to confirm that we're reviewing the details. A team member will respond within 24-48 hours with the information you need.

If your matter is urgent, please let us know and we'll prioritize accordingly.

Reference: #{self._generate_ticket_id()}

Best regards,
{self.sender_name}
{self.company_name}"""

        return response

    def _generate_ticket_id(self) -> str:
        """Generate a simple ticket reference ID"""
        import random
        return f"TICKET-{random.randint(10000, 99999)}"
