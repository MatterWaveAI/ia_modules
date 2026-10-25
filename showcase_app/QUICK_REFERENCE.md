# Pattern Steps - Quick Reference Card

## JSON Template

```json
{
  "name": "pipeline_name",
  "version": "1.0.0",
  "steps": [
    {
      "id": "unique_id",
      "name": "Display Name",
      "step_class": "ClassName",
      "module": "showcase_app.backend.pipelines.pattern_steps",
      "config": { /* step config */ }
    }
  ],
  "flow": {
    "start_at": "unique_id",
    "paths": [
      {
        "from": "unique_id",
        "to": "end_with_success",
        "condition": {"type": "always"}
      }
    ]
  }
}
```

## 📦 Available Patterns

Three reusable pattern `Step` subclasses live in `backend/pipelines/pattern_steps.py`. Two additional patterns (Agentic RAG, Metacognition) exist as service-layer demos in `backend/services/pattern_service.py` — see [PATTERNS_GUIDE.md](PATTERNS_GUIDE.md) for details.

### ReflectionStep
```json
{
  "step_class": "ReflectionStep",
  "config": {
    "initial_output": "text to improve",
    "criteria": {
      "clarity": "Must be clear",
      "accuracy": "Must be accurate"
    },
    "max_iterations": 3
  }
}
```

### PlanningStep
```json
{
  "step_class": "PlanningStep",
  "config": {
    "goal": "What to achieve",
    "constraints": ["constraint 1", "constraint 2"],
    "context": {"key": "value"}
  }
}
```

### ToolUseStep
```json
{
  "step_class": "ToolUseStep",
  "config": {
    "task": "Task description",
    "available_tools": ["calculator", "search"]
  }
}
```

## ⚙️ Run Pipeline

```bash
# From showcase_app/, so backend.pipelines.pattern_steps is importable
cd showcase_app
python -m ia_modules.pipeline.graph_pipeline_runner backend/pipelines/agentic_patterns_demo.json
```

## 🧪 Run Tests

```bash
cd showcase_app
python -m pytest tests/test_pattern_steps.py -v
```

## 🔑 Required Fields

| Field | Example | Description |
|-------|---------|-------------|
| `id` | `"my_step"` | Unique identifier |
| `name` | `"My Step"` | Display name |
| `step_class` | `"ReflectionStep"` | Class name |
| `module` | `"showcase_app.backend.pipelines.pattern_steps"` | Import path |
| `config` | `{}` | Step configuration |
| `flow` | `{...}` | Execution order |

## 📂 Files

- **Implementation**: `backend/pipelines/pattern_steps.py`
- **Example**: `backend/pipelines/agentic_patterns_demo.json`
- **Tests**: `tests/test_pattern_steps.py`
- **Guide**: `PATTERNS_GUIDE.md`

## 🔗 LLM Access

Pattern steps call a local CLI agent through `SubprocessAgentAdapter` (Claude Code by default), so install
and sign in to the `claude` CLI. They do not read `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`.
The showcase backend's own LLM settings live in `backend/.env` (`DEFAULT_LLM_PROVIDER`, `LLM_PROVIDER`,
`LLM_MODEL`, `LLM_API_KEY`).
