# Agent-Based Processing Pipeline

Three agent steps in a row: one ingests the input, one decides whether to accept it,
one produces the final result. Each step is an `LLMStep` that sends its prompt to a CLI
agent when one is available.

```
task, content
   ↓
data_ingestor      SimpleAgentStep (processing_type: ingestion)
   ↓
decision_agent     DecisionAgentStep (decision_logic: validation) → decision, confidence, reasoning
   ↓
final_processor    SimpleAgentStep (processing_type: final_processing)
   ↓
agent_output
```

## Run it

From the repository root:

```bash
echo '{"task": "summarise the quarterly numbers", "content": "Revenue rose 12% ..."}' > input.json
ia-modules run tests/pipelines/agent_pipeline/pipeline.json --working-dir . --input input.json
```

Parameters, both optional: `task` (what the agent should do) and `content` (what it
should work on).

## With and without an agent

The steps need `services['agent_executor']` to spawn a CLI agent (`claude_code` or
`opencode`); the showcase backend registers one, and `LLM_PROVIDER`, `LLM_MODEL` and
`LLM_API_KEY` configure it (see `ia_modules.pipeline.llm_config`). Then each step's
`agent_output` is the model's reply and `agent_job_id` points at its NDJSON log.

Without an executor, under pytest or the bare `ia-modules run`, each step returns a
rule-based result in the same shape (`metadata.agent_kind` is `rule_based`): the
decision agent accepts when there is both a task and content, and the other two
summarise what they were given. The pipeline completes either way.

## Output

`agent_output` from the final step, plus `decision`, `confidence` and `reasoning`
from the decision agent; each step's full result is also under its own id
(`data_ingestor`, `decision_agent`, `final_processor`).
