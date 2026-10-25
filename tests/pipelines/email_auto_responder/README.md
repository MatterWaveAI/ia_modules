# Email Auto Responder Pipeline

An intelligent email processing system that automatically classifies incoming emails and generates contextually appropriate responses. This pipeline demonstrates practical AI agent capabilities for customer service automation.

## Overview

The Email Auto Responder pipeline consists of two main agents:

1. **Email Classifier** - Analyzes and categorizes incoming emails
2. **Response Generator** - Creates appropriate automated responses

```
┌─────────────────┐        ┌──────────────────┐
│ Email Classifier│  ────> │Response Generator│
│                 │        │                  │
│ • Spam Check    │        │ • Urgent Reply   │
│ • Priority      │        │ • Standard Reply │
│ • Sentiment     │        │ • No Reply       │
│ • Entity Extract│        │ • Custom Tone    │
└─────────────────┘        └──────────────────┘
```

## Features

### Email Classification

Automatically categorizes emails into:

- **Urgent** - Contains time-sensitive keywords (ASAP, critical, emergency, etc.)
- **Normal** - Standard business correspondence
- **Spam** - Detected promotional or suspicious content
- **Automated** - System-generated emails (noreply addresses)

Additional analysis:
- **Sentiment Analysis** - Positive, neutral, or negative tone
- **Priority Scoring** - High, medium, or low priority
- **Entity Extraction** - Sender, subject, attachments, questions
- **Confidence Scoring** - Classification reliability

### Response Generation

Creates contextually appropriate responses based on:

- Email category (urgent/normal/spam/automated)
- Sentiment (positive/negative/neutral)
- Content type (questions, complaints, feedback)
- Priority level

Response features:
- Appropriate tone (professional, friendly, empathetic)
- Ticket reference numbers
- Response time commitments
- Resource links
- Custom company branding

## Usage

### Input Format

```json
{
  "email": {
    "from": "customer@example.com",
    "subject": "Urgent: Payment Issue",
    "body": "I'm having a critical problem with my last payment. The transaction failed but I was still charged. This is very frustrating and I need help immediately!",
    "attachments": []
  },
  "sender_name": "Customer Support",
  "company_name": "TechCorp"
}
```

### Example Execution

```python
import json
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner

# Load the pipeline definition (run from the repository root)
with open("tests/pipelines/email_auto_responder/pipeline.json") as f:
    pipeline = json.load(f)

# Create runner
runner = GraphPipelineRunner()

# Process email
result = await runner.run_pipeline_from_json(
    pipeline_config=pipeline,
    input_data={
        "email": {
            "from": "customer@example.com",
            "subject": "Question about pricing",
            "body": "Hi! I'd like to know more about your enterprise pricing. Do you offer volume discounts?",
            "attachments": []
        },
        "sender_name": "Sales Team",
        "company_name": "TechCorp"
    }
)

# Access response
print(result["response"]["body"])
```

### Output Structure

```json
{
  "email": {...},
  "classification": {
    "category": "urgent",
    "priority": "high",
    "is_spam": false,
    "is_automated": false,
    "requires_response": true,
    "sentiment": "negative",
    "confidence": 0.85
  },
  "entities": {
    "sender": "customer@example.com",
    "subject": "Urgent: Payment Issue",
    "has_attachments": false,
    "word_count": 28,
    "has_questions": false
  },
  "response": {
    "to": "customer@example.com",
    "from": "support@company.com",
    "subject": "Re: Urgent: Payment Issue",
    "body": "Thank you for bringing this urgent matter...",
    "priority": "high",
    "tone": "empathetic"
  },
  "action": "response_generated",
  "ready_to_send": true
}
```

## Classification Rules

### Urgent Detection
Triggered by keywords:
- urgent, asap, critical, emergency
- immediate, deadline, time-sensitive
- priority, important

### Spam Detection
Triggered by patterns:
- Prize/lottery notifications
- "Click here" or "Act now"
- Free money claims
- Suspicious sender patterns

### Automated Email Detection
- noreply@ addresses
- no-reply@ addresses
- automated@ addresses
- System-generated patterns

### Sentiment Analysis
**Positive indicators:**
- thank, appreciate, great, excellent
- wonderful, pleased, happy

**Negative indicators:**
- complaint, issue, problem
- disappointed, angry, frustrated

## Response Templates

### Urgent + Negative
```
Immediate escalation
Priority queue assignment
2-hour response commitment
Ticket reference provided
Empathetic tone
```

### Normal + Questions
```
Acknowledgment of inquiry
24-hour response commitment
Resource links provided
Helpful tone
Ticket reference
```

### Positive Feedback
```
Appreciation message
Warm, friendly tone
Encouragement to reach out again
No ticket needed
```

### Negative Feedback
```
Apology for experience
Investigation commitment
24-48 hour follow-up
Ticket reference
Professional, empathetic tone
```

## Customization

### Adjust Classification Keywords

In `pipeline.json`:
```json
{
  "id": "classify",
  "config": {
    "urgent_keywords": ["urgent", "critical", "custom_keyword"],
    "spam_keywords": ["spam_pattern", "unwanted_phrase"]
  }
}
```

### Customize Response Branding

In `pipeline.json`:
```json
{
  "id": "generate_response",
  "config": {
    "sender_name": "Your Team Name",
    "sender_email": "your-email@company.com",
    "company_name": "Your Company"
  }
}
```

### Extend Classification Logic

Add custom rules in `email_classifier.py`:

```python
# Custom VIP detection
vip_domains = ["vip-customer.com", "enterprise-client.com"]
if any(domain in sender for domain in vip_domains):
    classification["category"] = "vip"
    classification["priority"] = "critical"
```

### Add Response Templates

Create new response logic in `response_generator.py`:

```python
# Custom VIP response
if category == "vip":
    response["body"] = """Dear Valued Client,

    Thank you for reaching out. Your account has been flagged
    for premium support. Our senior team will respond within 1 hour.

    [Custom VIP template]
    """
```

## Real-World Applications

### Customer Support
- 24/7 automated acknowledgments
- Priority triaging
- Response time commitments
- Ticket generation

### Sales Inquiries
- Lead qualification
- Immediate engagement
- Resource delivery
- Follow-up scheduling

### Complaint Management
- Rapid escalation
- Empathetic responses
- Investigation tracking
- Resolution commitment

### Feedback Collection
- Appreciation messages
- Survey delivery
- Review requests
- Engagement maintenance

## Integration Options

### Email Service Integration

```python
import imaplib
import email as email_lib

# Fetch emails
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login('email@example.com', 'password')
mail.select('inbox')

_, data = mail.search(None, 'UNSEEN')
for num in data[0].split():
    _, msg_data = mail.fetch(num, '(RFC822)')
    email_message = email_lib.message_from_bytes(msg_data[0][1])

    # Process with pipeline
    result = await runner.run_pipeline_from_json(
        pipeline_config=pipeline,
        input_data={
            "email": {
                "from": email_message['From'],
                "subject": email_message['Subject'],
                "body": email_message.get_payload(),
                "attachments": []
            }
        }
    )

    # Send response if needed
    if result.get("ready_to_send"):
        send_email(result["response"])
```

### LLM Enhancement

Replace the rule-based classification step with the built-in `LLMStep`, which sends the prompt to a CLI agent
(Claude Code or OpenCode) and returns its text:

```json
{
  "id": "classify_email",
  "name": "Classify Email",
  "step_class": "LLMStep",
  "module": "ia_modules.pipeline.llm_step",
  "config": {
    "system_prompt": "Classify the email as urgent, normal, spam or automated, give its sentiment (positive, neutral, negative) and say whether it needs a response.",
    "cli_type": "claude_code"
  }
}
```

`LLMStep` reads the user message from `data["prompt"]`, `data["message"]`, `data["text"]` or `data["input"]`.

## Performance Metrics

The pipeline tracks:
- **Classification Accuracy** - % correctly categorized
- **Response Time** - Processing duration
- **Sentiment Detection** - Positive/negative identification rate
- **Spam Detection Rate** - % spam caught
- **Response Generation** - % requiring manual review

## Testing

Example test cases:

```python
# Test urgent detection
urgent_email = {
    "email": {
        "from": "client@example.com",
        "subject": "URGENT: Server Down",
        "body": "This is critical! Our production server is down!",
        "attachments": []
    }
}

# Test spam detection
spam_email = {
    "email": {
        "from": "winner@lottery.com",
        "subject": "Congratulations! You Won!",
        "body": "Click here to claim your prize! Act now!",
        "attachments": []
    }
}

# Test positive sentiment
positive_email = {
    "email": {
        "from": "happy@customer.com",
        "subject": "Thank You!",
        "body": "I really appreciate your excellent service. Thank you!",
        "attachments": []
    }
}
```

## Limitations

- Rule-based classification (not ML-based)
- English language only
- Simple sentiment analysis
- No learning/adaptation
- Template-based responses

## Future Enhancements

- [ ] ML-based classification
- [ ] Multi-language support
- [ ] Advanced NLP sentiment analysis
- [ ] Learning from feedback
- [ ] Dynamic template generation
- [ ] Attachment processing
- [ ] Email thread analysis
- [ ] Integration with CRM systems
- [ ] A/B testing of responses
- [ ] Analytics dashboard

## License

Part of the ia_modules pipeline system.
