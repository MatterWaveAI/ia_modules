# Agentic Design Patterns Guide

This guide covers the AI agent patterns implemented as pipeline steps in the showcase app.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Reflection Pattern](#reflection-pattern)
- [Planning Pattern](#planning-pattern)
- [Tool Use Pattern](#tool-use-pattern)
- [Creating Pipelines](#creating-pipelines)
- [API Reference](#api-reference)

## Overview

The showcase app ships five agentic patterns, split across two layers.

**Reusable pipeline Steps** — live in [pattern_steps.py](backend/pipelines/pattern_steps.py) as `Step` subclasses and can be dropped into any JSON pipeline config:

| Pattern | Class | Purpose | Research |
|---------|-------|---------|----------|
| **Reflection** | `ReflectionStep` | Self-critique and iterative improvement | [Bai et al., 2022](https://arxiv.org/abs/2212.08073) |
| **Planning** | `PlanningStep` | Multi-step goal decomposition | [Wei et al., 2022](https://arxiv.org/abs/2201.11903) |
| **Tool Use** | `ToolUseStep` | Dynamic capability selection | [Schick et al., 2023](https://arxiv.org/abs/2302.04761) |

All three share the same shape (`__init__(name, config)` + `async run(data)`) and delegate LLM calls to `SubprocessAgentAdapter`, which shells out to a local CLI agent.

**Service-layer demos** — live in [pattern_service.py](backend/services/pattern_service.py) as demo methods exposed through the pattern API (they power the frontend visualizations in [PatternsPage.jsx](frontend/src/pages/PatternsPage.jsx)):

| Pattern | Method | Purpose |
|---------|--------|---------|
| **Agentic RAG** | `agentic_rag_example()` | Query refinement + relevance evaluation |
| **Metacognition** | `metacognition_example()` | Self-monitoring and strategy adjustment |

These two are not (yet) packaged as reusable `Step` subclasses — to use them from a pipeline, wrap them in an `LLMStep` or `FunctionStep`. This guide documents the three reusable Steps in detail.

## Quick Start

### Prerequisites

Pattern steps call a local CLI agent through `SubprocessAgentAdapter` (Claude Code by default), so install
and sign in to the `claude` CLI. They do not read `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`.
The showcase backend's own LLM settings live in `backend/.env` (`DEFAULT_LLM_PROVIDER`, `LLM_PROVIDER`,
`LLM_MODEL`, `LLM_API_KEY`).

### Run Example

```bash
# From showcase_app/, so backend.pipelines.pattern_steps is importable
cd showcase_app
python -m ia_modules.pipeline.graph_pipeline_runner backend/pipelines/agentic_patterns_demo.json
```

### Run Tests

```bash
cd showcase_app
pytest tests/test_pattern_steps.py -v
```

## Reflection Pattern

### Description

The Reflection pattern implements iterative improvement through self-critique. The agent generates output, evaluates it against defined criteria, and refines until quality thresholds are met.

### Configuration

```python
{
  "initial_output": str,      # Text to improve
  "criteria": {               # Quality criteria
    "name": "description"
  },
  "max_iterations": int       # Maximum refinement cycles
}
```

### Example

```json
{
  "id": "improve_text",
  "name": "Improve Content",
  "step_class": "ReflectionStep",
  "module": "showcase_app.backend.pipelines.pattern_steps",
  "config": {
    "initial_output": "Draft article text...",
    "criteria": {
      "clarity": "Text should be clear and concise",
      "accuracy": "Facts must be verifiable",
      "completeness": "Cover all key points"
    },
    "max_iterations": 3
  }
}
```

### Output

```python
{
  "final_output": str,        # Improved text
  "final_score": float,       # Quality score (0-10)
  "iterations": list,         # Iteration history
  "total_iterations": int,    # Number of iterations
  "improved": bool            # Whether quality improved
}
```

### Python Usage

```python
from showcase_app.backend.pipelines.pattern_steps import ReflectionStep

step = ReflectionStep(
    name="improve",
    config={
        "initial_output": "Draft text",
        "criteria": {"clarity": "Must be clear"},
        "max_iterations": 3
    }
)

result = await step.run({})
print(result["final_output"])
```

## Planning Pattern

### Description

The Planning pattern breaks down complex goals into structured, executable sub-tasks with dependencies and expected outcomes.

### Configuration

```python
{
  "goal": str,               # Objective to achieve
  "constraints": list,       # Limitations/requirements
  "context": dict           # Additional information
}
```

### Example

```json
{
  "id": "create_plan",
  "name": "Create Research Plan",
  "step_class": "PlanningStep",
  "module": "showcase_app.backend.pipelines.pattern_steps",
  "config": {
    "goal": "Research renewable energy solutions",
    "constraints": [
      "Budget under $20,000",
      "Focus on solar power",
      "Complete within 2 weeks"
    ],
    "context": {
      "location": "Northeast US",
      "property_size": "2000 sq ft"
    }
  }
}
```

### Output

```python
{
  "goal": str,                # Original goal
  "plan": list,               # Structured steps
  "is_valid": bool,           # Plan validation result
  "validation_feedback": str, # Validation commentary
  "total_steps": int,         # Number of steps
  "estimated_time": str       # Time estimate
}
```

Each plan step includes:
```python
{
  "step_number": int,
  "action": str,
  "expected_outcome": str,
  "dependencies": list
}
```

### Python Usage

```python
from showcase_app.backend.pipelines.pattern_steps import PlanningStep

step = PlanningStep(
    name="plan",
    config={
        "goal": "Launch product feature",
        "constraints": ["3-month timeline", "Team of 5"]
    }
)

result = await step.run({})
for step_item in result["plan"]:
    print(f"{step_item['step_number']}: {step_item['action']}")
```

## Tool Use Pattern

### Description

The Tool Use pattern analyzes task requirements and dynamically selects appropriate tools for execution.

### Configuration

```python
{
  "task": str,              # Task description
  "available_tools": list   # Available tool names
}
```

### Example

```json
{
  "id": "solve_problem",
  "name": "Solve with Tools",
  "step_class": "ToolUseStep",
  "module": "showcase_app.backend.pipelines.pattern_steps",
  "config": {
    "task": "Calculate compound interest for $1000 at 5% over 10 years",
    "available_tools": [
      "calculator",
      "search",
      "code_executor"
    ]
  }
}
```

### Output

```python
{
  "task": str,              # Original task
  "selected_tools": list,   # Tools selected
  "tool_results": list,     # Results from each tool
  "final_answer": str,      # Synthesized answer
  "tools_used": int         # Number of tools used
}
```

### Python Usage

```python
from showcase_app.backend.pipelines.pattern_steps import ToolUseStep

step = ToolUseStep(
    name="solve",
    config={
        "task": "Calculate ROI",
        "available_tools": ["calculator", "search"]
    }
)

result = await step.run({})
print(result["final_answer"])
```

## Creating Pipelines

### Basic Structure

```json
{
  "name": "pipeline_name",
  "version": "1.0.0",
  "steps": [
    {
      "id": "unique_id",
      "name": "Display Name",
      "step_class": "PatternStepClass",
      "module": "showcase_app.backend.pipelines.pattern_steps",
      "config": {}
    }
  ],
  "flow": {
    "start_at": "unique_id",
    "paths": [
      {
        "from": "source_id",
        "to": "target_id",
        "condition": {"type": "always"}
      }
    ]
  }
}
```

### Multi-Pattern Pipeline

```json
{
  "name": "content_creation",
  "version": "1.0.0",
  "steps": [
    {
      "id": "plan",
      "name": "Plan Content",
      "step_class": "PlanningStep",
      "module": "showcase_app.backend.pipelines.pattern_steps",
      "config": {
        "goal": "Write article about AI",
        "constraints": ["1000 words", "Beginner audience"]
      }
    },
    {
      "id": "research",
      "name": "Research Topics",
      "step_class": "ToolUseStep",
      "module": "showcase_app.backend.pipelines.pattern_steps",
      "config": {
        "task": "Find latest AI developments",
        "available_tools": ["search"]
      }
    },
    {
      "id": "refine",
      "name": "Refine Quality",
      "step_class": "ReflectionStep",
      "module": "showcase_app.backend.pipelines.pattern_steps",
      "config": {
        "initial_output": "Draft text...",
        "criteria": {
          "accuracy": "Facts must be correct",
          "clarity": "Easy to understand"
        },
        "max_iterations": 3
      }
    }
  ],
  "flow": {
    "start_at": "plan",
    "paths": [
      {
        "from": "plan",
        "to": "research",
        "condition": {"type": "always"}
      },
      {
        "from": "research",
        "to": "refine",
        "condition": {"type": "always"}
      },
      {
        "from": "refine",
        "to": "end_with_success",
        "condition": {"type": "always"}
      }
    ]
  }
}
```

### Running Pipelines

```bash
# From file
python -m ia_modules.pipeline.graph_pipeline_runner your_pipeline.json

# With input data (a JSON string as the second argument)
python -m ia_modules.pipeline.graph_pipeline_runner your_pipeline.json '{"topic": "AI"}'
```

### Programmatic Execution

```python
from ia_modules.pipeline.graph_pipeline_runner import run_graph_pipeline_from_file

result = await run_graph_pipeline_from_file(
    pipeline_file="content_creation.json",
    input_data={}
)

print(result["plan"]["plan"])
print(result["research"]["final_answer"])
print(result["refine"]["final_output"])
```

## API Reference

### ReflectionStep

```python
class ReflectionStep(Step):
    def __init__(self, name: str, config: dict):
        """
        Args:
            name: Step name
            config: {
                "initial_output": str,
                "criteria": dict,
                "max_iterations": int
            }
        """

    async def run(self, data: dict) -> dict:
        """
        Returns:
            {
                "final_output": str,
                "final_score": float,
                "iterations": list,
                "total_iterations": int,
                "improved": bool
            }
        """
```

### PlanningStep

```python
class PlanningStep(Step):
    def __init__(self, name: str, config: dict):
        """
        Args:
            name: Step name
            config: {
                "goal": str,
                "constraints": list,
                "context": dict
            }
        """

    async def run(self, data: dict) -> dict:
        """
        Returns:
            {
                "goal": str,
                "plan": list,
                "is_valid": bool,
                "validation_feedback": str,
                "total_steps": int,
                "estimated_time": str
            }
        """
```

### ToolUseStep

```python
class ToolUseStep(Step):
    def __init__(self, name: str, config: dict):
        """
        Args:
            name: Step name
            config: {
                "task": str,
                "available_tools": list
            }
        """

    async def run(self, data: dict) -> dict:
        """
        Returns:
            {
                "task": str,
                "selected_tools": list,
                "tool_results": list,
                "final_answer": str,
                "tools_used": int
            }
        """
```

## Files

- **Implementation**: `backend/pipelines/pattern_steps.py`
- **Example Pipeline**: `backend/pipelines/agentic_patterns_demo.json`
- **Tests**: `tests/test_pattern_steps.py`
- **Quick Reference**: `QUICK_REFERENCE.md`
