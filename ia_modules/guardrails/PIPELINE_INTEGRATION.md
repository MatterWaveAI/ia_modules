# Guardrails Pipeline Integration Guide

Complete guide for integrating guardrails into ia_modules pipelines.

## Overview

Guardrails can be added as pipeline steps in your JSON pipeline configurations. This allows you to add safety checks at any point in your pipeline execution.

## Pipeline Step Classes

### 1. InputGuardrailStep

Pre-configured step for validating user inputs before processing.

**Default Rails**:
- JailbreakDetectionRail - Blocks prompt injection
- ToxicityDetectionRail - Blocks harmful content
- PIIDetectionRail - Redacts sensitive information

**Pipeline JSON**:
```json
{
    "id": "input_validation",
    "name": "Input Safety Check",
    "step_class": "InputGuardrailStep",
    "module": "ia_modules.guardrails.pipeline_steps",
    "config": {
        "content_field": "user_input",
        "fail_on_block": true,
        "redact_pii": true
    }
}
```

**Config Options**:
- `content_field` (str): Field containing input text (default: "user_input")
- `fail_on_block` (bool): Raise error if blocked (default: true)
- `redact_pii` (bool): Redact PII instead of blocking (default: true)
- `rails_config` (str|dict): Optional custom configuration

### 2. OutputGuardrailStep

Pre-configured step for validating LLM outputs.

**Default Rails**:
- ToxicOutputFilterRail - Blocks toxic responses
- DisclaimerRail - Adds disclaimers to sensitive advice
- LengthLimitRail - Enforces maximum length

**Pipeline JSON**:
```json
{
    "id": "output_validation",
    "name": "Output Safety Check",
    "step_class": "OutputGuardrailStep",
    "module": "ia_modules.guardrails.pipeline_steps",
    "config": {
        "content_field": "llm_response",
        "fail_on_block": true,
        "max_length": 500
    }
}
```

**Config Options**:
- `content_field` (str): Field containing output text (default: "llm_response")
- `fail_on_block` (bool): Raise error if blocked (default: true)
- `max_length` (int): Maximum response length (default: 500)
- `rails_config` (str|dict): Optional custom configuration

### 3. RetrievalGuardrailStep

Pre-configured step for validating retrieved documents in RAG pipelines.

**Default Rails**:
- SourceValidationRail - Validates document sources
- RelevanceFilterRail - Filters low-relevance documents

**Pipeline JSON**:
```json
{
    "id": "document_filtering",
    "name": "Filter Retrieved Documents",
    "step_class": "RetrievalGuardrailStep",
    "module": "ia_modules.guardrails.pipeline_steps",
    "config": {
        "documents_field": "retrieved_documents",
        "fail_on_block": false,
        "allowed_sources": ["*.edu", "*.gov", "wikipedia.org"],
        "min_relevance_score": 0.7
    }
}
```

**Config Options**:
- `documents_field` (str): Field containing documents (default: "retrieved_documents")
- `fail_on_block` (bool): Raise error if all blocked (default: false)
- `allowed_sources` (list): Whitelist of allowed sources
- `min_relevance_score` (float): Minimum relevance threshold (0.0-1.0)
- `rails_config` (str|dict): Optional custom configuration

### 4. ExecutionGuardrailStep

Pre-configured step for validating code/tool execution.

**Default Rails**:
- ToolValidationRail - Validates tool calls
- CodeExecutionSafetyRail - Validates code safety

**Pipeline JSON**:
```json
{
    "id": "execution_validation",
    "name": "Validate Execution Safety",
    "step_class": "ExecutionGuardrailStep",
    "module": "ia_modules.guardrails.pipeline_steps",
    "config": {
        "code_field": "code",
        "tool_field": "tool_name",
        "fail_on_block": true,
        "allowed_tools": ["search", "calculator"],
        "blocked_tools": ["delete_database"],
        "allow_file_read": true,
        "allow_network": false
    }
}
```

**Config Options**:
- `code_field` (str): Field containing code (default: "code")
- `tool_field` (str): Field containing tool name (default: "tool_name")
- `fail_on_block` (bool): Raise error if blocked (default: true)
- `allowed_tools` (list): Whitelist of allowed tools
- `blocked_tools` (list): Blacklist of blocked tools
- `allow_file_read` (bool): Allow file read operations
- `allow_network` (bool): Allow network operations
- `rails_config` (str|dict): Optional custom configuration

### 5. GuardrailStep (Generic)

Fully customizable guardrail step for advanced use cases.

**Pipeline JSON**:
```json
{
    "id": "custom_guardrails",
    "name": "Custom Safety Check",
    "step_class": "GuardrailStep",
    "module": "ia_modules.guardrails.pipeline_steps",
    "config": {
        "rail_type": "input",
        "content_field": "message",
        "context_fields": ["metadata", "user_id"],
        "output_field": "guardrails_result",
        "fail_on_block": true,
        "rails_config": {
            "rails": [
                {
                    "class": "JailbreakDetectionRail",
                    "config": {
                        "name": "jailbreak",
                        "type": "input",
                        "enabled": true
                    }
                }
            ]
        }
    }
}
```

**Config Options**:
- `rail_type` (str): Type of rail ("input"|"output"|"dialog"|"retrieval"|"execution")
- `content_field` (str): Field containing content to check
- `context_fields` (list): Fields to pass as context
- `output_field` (str): Where to store guardrails result
- `fail_on_block` (bool): Raise error if blocked
- `rails_config` (str|dict): Rails configuration (file path or dict)

## Complete Pipeline Examples

### Example 1: LLM Pipeline with Guardrails

```json
{
    "name": "Safe LLM Pipeline",
    "version": "1.0.0",
    "parameters": [
        {"name": "user_input", "schema": {"type": "string"}, "required": true}
    ],
    "steps": [
        {
            "id": "input_guardrails",
            "step_class": "InputGuardrailStep",
            "module": "ia_modules.guardrails.pipeline_steps",
            "config": {"content_field": "user_input"}
        },
        {
            "id": "llm_processing",
            "step_class": "LLMStep",
            "module": "your_module.llm_step"
        },
        {
            "id": "output_guardrails",
            "step_class": "OutputGuardrailStep",
            "module": "ia_modules.guardrails.pipeline_steps",
            "config": {"content_field": "llm_response"}
        }
    ],
    "flow": {
        "start_at": "input_guardrails",
        "paths": [
            {"from": "input_guardrails", "to": "llm_processing"},
            {"from": "llm_processing", "to": "output_guardrails"}
        ]
    }
}
```

### Example 2: RAG Pipeline with Document Filtering

```json
{
    "name": "RAG with Guardrails",
    "steps": [
        {
            "id": "validate_query",
            "step_class": "InputGuardrailStep",
            "module": "ia_modules.guardrails.pipeline_steps",
            "config": {"content_field": "query"}
        },
        {
            "id": "retrieve_docs",
            "step_class": "RetrievalStep",
            "module": "your_module.retrieval"
        },
        {
            "id": "filter_docs",
            "step_class": "RetrievalGuardrailStep",
            "module": "ia_modules.guardrails.pipeline_steps",
            "config": {
                "documents_field": "retrieved_documents",
                "allowed_sources": ["*.edu", "wikipedia.org"],
                "min_relevance_score": 0.7
            }
        },
        {
            "id": "generate",
            "step_class": "RAGLLMStep",
            "module": "your_module.rag_llm"
        },
        {
            "id": "validate_output",
            "step_class": "OutputGuardrailStep",
            "module": "ia_modules.guardrails.pipeline_steps"
        }
    ]
}
```

## Custom Configuration Files

You can load guardrails from external JSON files:

**guardrails_config.json**:
```json
{
    "rails": [
        {
            "class": "JailbreakDetectionRail",
            "config": {"name": "jailbreak", "type": "input", "enabled": true}
        },
        {
            "class": "ToxicityDetectionRail",
            "config": {"name": "toxicity", "type": "input", "enabled": true}
        }
    ]
}
```

**In pipeline.json**:
```json
{
    "id": "input_guardrails",
    "step_class": "InputGuardrailStep",
    "module": "ia_modules.guardrails.pipeline_steps",
    "config": {
        "rails_config": "path/to/guardrails_config.json"
    }
}
```

## Running Pipelines with Guardrails

```python
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
import json

# Load pipeline
with open("pipeline.json") as f:
    config = json.load(f)

# Run with input
runner = GraphPipelineRunner()
result = await runner.run_pipeline_from_json(
    config,
    {"user_input": "What is machine learning?"}
)

# Check guardrails results
input_result = result.get("input_guardrails_result")
output_result = result.get("output_guardrails_result")

print(f"Input action: {input_result['action']}")
print(f"Output action: {output_result['action']}")
```

## Error Handling

When a guardrail blocks content with `fail_on_block=true`, it raises a `PipelineError`:

```python
from ia_modules.pipeline.errors import PipelineError

try:
    result = await runner.run_pipeline_from_json(config, input_data)
except PipelineError as e:
    if "blocked" in str(e).lower():
        print(f"Content blocked by guardrails: {e}")
    else:
        raise
```

## Best Practices

1. **Defense in Depth**: Use both input and output guardrails
2. **Fail Fast**: Set `fail_on_block=true` for critical safety checks
3. **PII Redaction**: Use `redact_pii=true` instead of blocking when possible
4. **Source Validation**: Always validate document sources in RAG pipelines
5. **Custom Configs**: Use external config files for reusability
6. **Monitor Stats**: Check guardrails_result for trigger rates and warnings

## Testing

See [tests/pipelines/guardrails_pipeline/](../../tests/pipelines/guardrails_pipeline/) for complete working examples.

## Visual Canvas Integration

All guardrail steps can be added to visual pipeline canvases and will appear as:

- **InputGuardrailStep**: Shield icon, blue color
- **OutputGuardrailStep**: Check icon, green color
- **RetrievalGuardrailStep**: Filter icon, purple color
- **ExecutionGuardrailStep**: Lock icon, red color

## Further Reading

- [Guardrails README](README.md) - Complete module documentation
- [Pipeline Tests](../../tests/pipelines/guardrails_pipeline/) - Integration tests
