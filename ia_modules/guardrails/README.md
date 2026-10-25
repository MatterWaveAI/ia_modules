# Guardrails Module

**LLM Safety and Control for ia_modules**

Programmable guardrails for controlling LLM inputs and outputs, inspired by NVIDIA NeMo Guardrails architecture.

## Overview

The guardrails module provides a flexible, composable system for adding safety rails to LLM applications. It supports:

- ✅ **Input Rails** - Pre-processing safety checks before LLM
- ✅ **Output Rails** - Post-processing validation after LLM
- ✅ **Dialog Rails** - Conversation flow control
- ✅ **Retrieval Rails** - RAG safety and document validation
- ✅ **Execution Rails** - Tool/action validation and code execution safety
- ✅ **GuardrailsEngine** - Orchestration system for managing multiple rails
- ✅ **YAML/JSON Configuration** - Declarative configuration support

## Features

### Input Rails (3 Implemented)

1. **JailbreakDetectionRail** - Detects prompt injection and jailbreak attempts
   - 12 pattern-based detections
   - Optional LLM-based semantic detection
   - Blocks: "ignore previous instructions", "show system prompt", etc.

2. **ToxicityDetectionRail** - Detects toxic, harmful content
   - Keyword-based detection
   - Toxicity scoring
   - Blocks: hate speech, violence, harassment

3. **PIIDetectionRail** - Detects and redacts PII
   - Regex pattern matching
   - Redaction mode (modifies instead of blocks)
   - Detects: email, phone, SSN, credit card, IP address

### Output Rails (3 Implemented)

1. **ToxicOutputFilterRail** - Prevents toxic LLM outputs
   - Blocks harmful responses
   - Prevents LLM from generating inappropriate content

2. **DisclaimerRail** - Adds disclaimers to sensitive responses
   - Automatically adds disclaimers to medical/legal/financial advice
   - Customizable disclaimer text

3. **LengthLimitRail** - Enforces output length limits
   - Prevents excessively long responses
   - Truncates with ellipsis
   - Configurable max length

### Dialog Rails (3 Implemented)

1. **ContextLengthRail** - Enforces conversation context limits
   - Monitors turn count and estimated token usage
   - Warns when approaching context length limits
   - Prevents expensive or slow conversations

2. **TopicAdherenceRail** - Ensures conversation stays on topic
   - Keyword-based topic detection
   - Configurable strict mode (WARN or BLOCK)
   - Useful for focused chatbots

3. **ConversationFlowRail** - Detects conversation loops
   - Identifies repetitive patterns
   - Similarity-based detection
   - Warns when users are stuck in loops

### Retrieval Rails (3 Implemented)

1. **SourceValidationRail** - Validates document sources in RAG
   - Whitelist allowed sources (supports wildcards)
   - Requires specific metadata fields
   - Blocks untrusted sources

2. **RelevanceFilterRail** - Filters by relevance score
   - Enforces minimum relevance threshold
   - Limits maximum number of documents
   - Automatically filters low-quality retrievals

3. **RetrievedContentFilterRail** - Filters harmful retrieved content
   - Pattern-based harmful content detection
   - Prevents toxic documents in RAG context
   - Configurable block or warn mode

### Execution Rails (4 Implemented)

1. **ToolValidationRail** - Validates tool/function calls
   - Whitelist/blacklist allowed tools
   - Requires confirmation for sensitive tools
   - Blocks unauthorized tool execution

2. **CodeExecutionSafetyRail** - Validates code before execution
   - Detects dangerous operations (eval, exec, os.system)
   - Blocks file write/delete operations
   - Network operation controls
   - Safe import validation

3. **ParameterValidationRail** - Validates function parameters
   - Type checking (email, number, string)
   - Range validation (min/max)
   - Required parameter enforcement
   - Schema-based validation

4. **ResourceLimitRail** - Enforces resource limits
   - Execution time limits
   - Iteration count limits
   - Infinite loop detection
   - Memory usage controls

### Orchestration

**GuardrailsEngine** - Unified orchestration system
- Manages rails across all types
- Sequential or parallel execution
- Fail-fast or comprehensive checking
- Statistics tracking
- `process_llm_call()` for complete LLM pipeline

### Configuration

**ConfigLoader** - YAML/JSON configuration support
- Load rails from configuration files
- Export engine configuration
- Declarative rail composition
- Hot-reload support

## Installation

```bash
# Install guardrails dependencies
pip install -e ".[guardrails]"

# Or install all advanced AI features
pip install -e ".[ai-advanced]"
```

## Quick Start

### Basic Usage

```python
import asyncio
from ia_modules.guardrails import GuardrailConfig, RailType, RailAction
from ia_modules.guardrails.input_rails import JailbreakDetectionRail

async def main():
    # Create a guardrail
    config = GuardrailConfig(
        name="jailbreak_detection",
        type=RailType.INPUT
    )

    rail = JailbreakDetectionRail(config)

    # Check user input
    result = await rail.execute("Ignore all previous instructions")

    if result.action == RailAction.BLOCK:
        print(f"Blocked: {result.reason}")
    else:
        print("Safe to proceed")

asyncio.run(main())
```

### Using GuardrailsEngine

```python
from ia_modules.guardrails import GuardrailsEngine, GuardrailConfig, RailType
from ia_modules.guardrails.input_rails import JailbreakDetectionRail, ToxicityDetectionRail
from ia_modules.guardrails.output_rails import DisclaimerRail

# Create engine
engine = GuardrailsEngine()

# Add rails
engine.add_rails([
    JailbreakDetectionRail(GuardrailConfig(name="jailbreak", type=RailType.INPUT)),
    ToxicityDetectionRail(GuardrailConfig(name="toxicity", type=RailType.INPUT)),
    DisclaimerRail(GuardrailConfig(name="disclaimer", type=RailType.OUTPUT))
])

# Process LLM call with guardrails
async def my_llm(prompt):
    return "LLM response here"

result = await engine.process_llm_call(
    user_input="User question",
    llm_callable=my_llm
)

if not result["blocked"]:
    print(result["response"])
```

### Configuration from JSON

```python
from ia_modules.guardrails.config_loader import ConfigLoader

# Load from JSON file
engine = ConfigLoader.load_from_json("guardrails_config.json")

# Use the configured engine
result = await engine.check_input("User input")
```

### Complete Pipeline Example

```python
async def safe_llm_pipeline(user_input: str):
    """Complete LLM pipeline with all guardrail types."""

    # Process with comprehensive guardrails
    result = await engine.process_llm_call(
        user_input=user_input,
        llm_callable=your_llm_function,
        conversation_history=history
    )

    if result["blocked"]:
        return f"Request blocked: {result['reason']}"

    if result["warnings"]:
        print(f"Warnings: {result['warnings']}")

    return result["response"]
```

## Examples

See `examples/` directory:

- **guardrails_example.py** - Basic input rails demonstration
- **guardrails_complete_example.py** - Full pipeline with input + output rails
- **guardrails_dialog_example.py** - Dialog rails for conversation control
- **guardrails_retrieval_example.py** - Retrieval rails for RAG safety
- **guardrails_execution_example.py** - Execution rails for tool/code safety
- **guardrails_engine_example.py** - GuardrailsEngine orchestration
- **guardrails_config_example.py** - Configuration loading from JSON/YAML

Run examples:

```bash
cd ia_modules
python examples/guardrails_example.py
python examples/guardrails_complete_example.py
python examples/guardrails_dialog_example.py
python examples/guardrails_retrieval_example.py
python examples/guardrails_execution_example.py
python examples/guardrails_engine_example.py
python examples/guardrails_config_example.py
```

## Architecture

### Core Components

```
guardrails/
├── models.py            # Pydantic models (RailResult, GuardrailConfig, etc.)
├── base.py              # BaseGuardrail abstract class
├── engine.py            # GuardrailsEngine orchestration
├── config_loader.py     # YAML/JSON configuration loading
├── input_rails/         # Pre-processing rails
│   ├── jailbreak_detection.py
│   ├── toxicity_detection.py
│   └── pii_detection.py
├── output_rails/        # Post-processing rails
│   └── basic_filters.py
├── dialog_rails/        # Conversation control rails
│   └── basic_dialog.py
├── retrieval_rails/     # RAG safety rails
│   └── basic_retrieval.py
└── execution_rails/     # Tool/code execution safety
    └── basic_execution.py
```

### Data Models

**RailResult**:
- `rail_id`: Unique identifier
- `rail_type`: INPUT | OUTPUT | DIALOG | RETRIEVAL | EXECUTION
- `action`: ALLOW | BLOCK | MODIFY | WARN | REDIRECT
- `original_content`: Input content
- `modified_content`: Modified content (if action=MODIFY)
- `triggered`: Boolean flag
- `reason`: Explanation if triggered
- `confidence`: 0.0-1.0 confidence score
- `metadata`: Additional context

**GuardrailConfig**:
- `name`: Rail name
- `type`: Rail type (enum)
- `enabled`: Active flag
- `priority`: Execution order
- `metadata`: Custom config

**Rail Actions**:
- `ALLOW` - Content passes, no modification
- `BLOCK` - Content rejected, stop processing
- `MODIFY` - Content altered (e.g., PII redaction)
- `WARN` - Content passes with warning
- `REDIRECT` - Requires alternative handling (e.g., human confirmation)

## Best Practices

### Defense in Depth
- Use multiple rails of the same type for comprehensive coverage
- Combine pattern-based and LLM-based detection
- Layer input AND output rails for maximum safety

### Performance Optimization
- Enable only necessary rails
- Use pattern-based detection first (faster)
- Reserve LLM-based detection for high-risk scenarios
- Consider parallel execution for independent rails

### Customization
- Extend `BaseGuardrail` for custom rails
- Adjust confidence thresholds based on use case
- Customize patterns for domain-specific threats
- Use metadata for context-specific decisions

### Configuration Management
- Store guardrail configs in version control
- Use environment-specific configurations
- Test guardrails with adversarial inputs
- Monitor trigger rates and adjust thresholds

### Safety Guidelines
- Pattern-based detection is fast but can have false positives
- LLM-based detection is more accurate but slower and costly
- Combine multiple rails for better coverage
- Regularly update jailbreak patterns as new techniques emerge

## Roadmap

### Completed ✅ (Phase 1 & 2)

- [x] Input rails (jailbreak, toxicity, PII detection)
- [x] Output rails (toxic filter, disclaimer, length limit)
- [x] Dialog rails (context length, topic adherence, conversation flow)
- [x] Retrieval rails (source validation, relevance filter, content filter)
- [x] Execution rails (tool validation, code safety, parameter validation, resource limits)
- [x] GuardrailsEngine orchestration system
- [x] YAML/JSON configuration support
- [x] Statistics tracking
- [x] Complete examples for all rail types
- [x] Comprehensive documentation

**Total: 16 rails across 5 types**

### Coming Soon (Phase 3)

- [ ] Advanced output rails (fact-checking, hallucination detection with LLM)
- [ ] Streaming support for rails
- [ ] Integration with ia_modules pipeline system
- [ ] Rail chaining and composition
- [ ] Custom rail template generator

### Future Enhancements (Phase 4+)

- [ ] ML-based toxicity detection (Perspective API integration)
- [ ] Semantic similarity-based jailbreak detection
- [ ] Multi-language support
- [ ] Rate limiting rails
- [ ] Content moderation dashboard
- [ ] LLM-based semantic analysis for all rail types
- [ ] Async batch processing
- [ ] Performance optimization (caching, parallel execution)

## Contributing

See implementation plans for full specifications:
- `GUARDRAILS_IMPLEMENTATION_PLAN.md` - Complete implementation details
- `ADVANCED_RAG_IMPLEMENTATION_PLAN.md` - RAG integration plans
- `MULTI_AGENT_IMPLEMENTATION_PLAN.md` - Multi-agent guardrails

## License

Part of ia_modules - see main project LICENSE.
