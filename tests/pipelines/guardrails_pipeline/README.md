# Guardrails Pipeline Example

Input and output safety checks around an LLM step, as three steps in one pipeline:

```
user_input
   ↓
InputGuardrailStep    blocks jailbreaks and toxic input, redacts personal data
   ↓
LLMStep               answers the (now safe) input
   ↓
OutputGuardrailStep   blocks toxic replies, adds disclaimers, enforces max_length
   ↓
llm_response
```

The guardrail steps are the library's own, from `ia_modules.guardrails.pipeline_steps`.
The LLM step here, `steps/llm_step.py`, is a placeholder that answers from a template, so
the example runs with no model, API key or agent. "A real model" below swaps it out.

## Run it

From the repository root:

```bash
echo '{"user_input": "What is machine learning? My email is jane@example.com"}' > input.json
ia-modules run tests/pipelines/guardrails_pipeline/pipeline.json --working-dir . --input input.json
```

The result's `output` holds each guardrail's decision and the text that reached the next step:

```json
{
  "user_input": "What is machine learning? My email is [EMAIL_REDACTED]",
  "input_guardrails_result": {"action": "modify", "...": "..."},
  "llm_response": "You asked: What is machine learning? My email is [EMAIL_REDACTED] ...",
  "output_guardrails_result": {"action": "allow", "...": "..."}
}
```

Send a jailbreak instead ("Ignore all previous instructions and ...") and the run stops at
the first step with `Input blocked`, because its `fail_on_block` is true.

## The steps' configuration

In `pipeline.json`:

| Step | `step_class`, `module` | Config |
|---|---|---|
| `input_guardrails` | `InputGuardrailStep`, `ia_modules.guardrails.pipeline_steps` | `content_field`: the field to check. `fail_on_block`: raise rather than pass a blocked value on. `redact_pii`: replace personal data instead of blocking. |
| `llm_processing` | `LLMStep`, `tests.pipelines.guardrails_pipeline.steps.llm_step` | `input_field`, `output_field` |
| `output_guardrails` | `OutputGuardrailStep`, `ia_modules.guardrails.pipeline_steps` | `content_field`, `fail_on_block`, `max_length` |

## A real model

Point the middle step at the library's LLM step, which sends the prompt to a CLI agent
(`claude_code` or `opencode`) through the host's registered agent executor:

```json
{
    "id": "llm_processing",
    "step_class": "LLMStep",
    "module": "ia_modules.pipeline.llm_step",
    "config": {"system_prompt": "You are a helpful assistant.", "temperature": 0.7, "max_tokens": 500}
}
```

That step reads its input from a `prompt`, `message`, `text` or `input` field and returns
the reply as `text`, so the step's `inputs` and `outputs` in `pipeline.json`, and the output
guardrail's `content_field`, change to match. It needs `services['agent_executor']`: the
showcase backend registers one, the bare `ia-modules run` command does not.

## In your own pipeline

Put the two guardrail steps around any step of yours; nothing else is needed:

```json
{"id": "input_guardrails", "step_class": "InputGuardrailStep", "module": "ia_modules.guardrails.pipeline_steps", "config": {"content_field": "user_input"}}
{"id": "output_guardrails", "step_class": "OutputGuardrailStep", "module": "ia_modules.guardrails.pipeline_steps", "config": {"content_field": "answer", "max_length": 500}}
```

[PIPELINE_INTEGRATION.md](../../../ia_modules/guardrails/PIPELINE_INTEGRATION.md) covers
custom rails configuration, retrieval guardrails for RAG and execution guardrails for tools.
