# Multi-Agent Collaboration Pipeline

A sophisticated pipeline demonstrating multiple AI agents working together using established agentic design patterns. Agents iterate and refine their work through structured collaboration.

## Architecture

This pipeline implements a cyclical collaboration pattern where specialized agents work together:

```
┌─────────────┐
│  Planning   │ ──> Creates execution plan
│    Agent    │     (Planning Pattern)
└──────┬──────┘
       │
       v
┌─────────────┐
│  Execution  │ ──> Executes the plan
│    Agent    │     (Tool Use Pattern)
└──────┬──────┘
       │
       v
┌─────────────┐
│   Critic    │ ──> Provides feedback
│    Agent    │     (Reflection Pattern)
└──────┬──────┘
       │
       v
┌──────────────┐
│Metacognition │ ──> Analyzes process
│    Agent     │     (Metacognition Pattern)
└──────┬───────┘
       │
       v
┌──────────────┐
│   Decision   │ ──> Continue or finish?
│    Logic     │
└──────┬───────┘
       │
       ├──> If quality threshold not met ──> Loop back to Planning
       │
       └──> If threshold met or max iterations ──> Synthesis Agent
```

## Agents

### 1. Planning Agent
- **Pattern:** Planning
- **Role:** Break down tasks into actionable steps
- **Responsibilities:**
  - Decompose high-level goals
  - Create structured execution plans
  - Adapt based on feedback from previous iterations

### 2. Execution Agent
- **Pattern:** Tool Use
- **Role:** Execute the plan
- **Responsibilities:**
  - Select appropriate tools for each step
  - Execute planned actions
  - Track execution metrics

### 3. Critic Agent
- **Pattern:** Reflection
- **Role:** Provide quality feedback
- **Responsibilities:**
  - Evaluate execution results against criteria
  - Identify strengths and weaknesses
  - Suggest specific improvements

### 4. Metacognition Agent
- **Pattern:** Metacognition
- **Role:** Monitor collaboration effectiveness
- **Responsibilities:**
  - Analyze execution patterns
  - Assess collaboration health
  - Recommend strategy adjustments

### 5. Synthesis Agent
- **Pattern:** Integration
- **Role:** Combine all insights
- **Responsibilities:**
  - Synthesize multi-iteration results
  - Document process evolution
  - Produce comprehensive final output

## Usage

### Input Parameters

```json
{
  "task": "Research and write a technical blog post on microservices",
  "max_iterations": 3
}
```

- `task` (required): High-level task description
- `max_iterations` (optional): Maximum collaboration cycles (default: 3)

### Example Execution

```python
import json
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner

# Load the pipeline definition (run from the repository root)
with open("tests/pipelines/multi_agent_collaboration/pipeline.json") as f:
    pipeline = json.load(f)

# Create runner
runner = GraphPipelineRunner()

# Execute
result = await runner.run_pipeline_from_json(
    pipeline_config=pipeline,
    input_data={
        "task": "Design a scalable API architecture",
        "max_iterations": 3
    }
)

# Access final output
print(result["final_output"])
```

### Output Structure

```json
{
  "task": "...",
  "iteration": 3,
  "final_output": "Comprehensive markdown report",
  "synthesis": {
    "collaboration_summary": {
      "total_iterations": 3,
      "agents_participated": ["Planning", "Execution", "Reflection", "Metacognition"],
      "final_quality_score": 0.87,
      "patterns_applied": ["planning", "tool_use", "reflection", "metacognition"]
    },
    "iteration_breakdown": [
      {
        "iteration": 1,
        "steps_planned": 4,
        "tools_used": 3,
        "quality_score": 0.65,
        "strategy_adjustments": 4
      }
    ],
    "insights": [...],
    "recommendations": [...]
  },
  "execution_history": [...]
}
```

## Iteration Flow

Each iteration follows this sequence:

1. **Planning Agent** creates/refines execution plan
2. **Execution Agent** implements the plan using selected tools
3. **Critic Agent** evaluates results and provides feedback
4. **Metacognition Agent** analyzes collaboration effectiveness
5. **Decision Logic** determines if another iteration is needed:
   - If quality threshold met (default: 0.8) → Proceed to synthesis
   - If max iterations reached → Proceed to synthesis
   - Otherwise → Loop back to planning with feedback

6. **Synthesis Agent** (final step) produces comprehensive output

## Quality Improvement

The pipeline demonstrates iterative quality improvement:

- **Iteration 1:** Baseline (~0.6-0.7 quality)
- **Iteration 2:** Refinement based on critique (~0.7-0.8 quality)
- **Iteration 3:** Polish and optimization (~0.8-0.9 quality)

Quality improves through:
- Incorporation of critic feedback
- Strategy adjustments from metacognition
- Refined planning in subsequent iterations
- Accumulated learning across iterations

## Agentic Patterns Demonstrated

### 1. Planning Pattern
Decomposes complex tasks into manageable steps with reasoning and success criteria.

### 2. Tool Use Pattern
Selects and applies appropriate tools dynamically based on task requirements.

### 3. Reflection Pattern
Self-critique and iterative improvement through structured feedback.

### 4. Metacognition Pattern
Self-monitoring of execution and strategy adjustment based on performance analysis.

## Customization

### Adjust Quality Threshold

In `pipeline.json`:
```json
{
  "id": "decide_continue",
  "config": {
    "quality_threshold": 0.85  // Increase for higher quality requirements
  }
}
```

### Modify Iteration Limit

In input data:
```json
{
  "task": "Your task",
  "max_iterations": 5  // Allow more refinement cycles
}
```

### Extend with Additional Agents

1. Create new agent step in `steps/` directory
2. Add to `pipeline.json` steps array
3. Add flow paths to connect to existing agents

## Real-World Applications

- **Content Generation:** Iteratively create and refine written content
- **Code Development:** Plan, implement, review, and refine code
- **Research Synthesis:** Gather, analyze, critique, and synthesize research
- **Problem Solving:** Break down complex problems, solve, evaluate, refine
- **Decision Making:** Analyze options, execute decisions, evaluate outcomes

## Integration with LLM Services

To use a real LLM instead of simulation, swap an agent step for the built-in `LLMStep` (or `AgentStep` for an
agent that needs tools and a workspace):

```json
{
  "id": "planner",
  "name": "Planning Agent",
  "step_class": "LLMStep",
  "module": "ia_modules.pipeline.llm_step",
  "config": {
    "system_prompt": "You are a planning agent. Break the task into concrete steps.",
    "cli_type": "claude_code",
    "max_tokens": 2000
  }
}
```

## Performance Metrics

The pipeline tracks:
- **Iteration Count:** Number of refinement cycles
- **Quality Score:** 0.0-1.0 rating from critic
- **Agent Participation:** Which agents contributed
- **Tool Usage:** Tools selected and applied
- **Strategy Adjustments:** Metacognition recommendations
- **Execution Time:** Duration per iteration

## License

Part of the ia_modules pipeline system.
