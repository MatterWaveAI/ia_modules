# Iterative Refinement

Human-in-the-loop progressive enhancement: a draft is generated, a person refines it,
and the pipeline loops back for another round until they are satisfied or the
iteration limit is reached.

```
topic
   ↓
generate_draft        → current_result (a markdown draft), iteration 1
   ↓
refine_content        IterativeRefinementStep: pauses with a form (ui_schema)
   ↓                  the person returns refined_result, refinement_notes, continue_refining
process_refinement    records the round
   ├─ status == continue_refinement → refine_content   (next round)
   └─ otherwise                     → finalize_document → document, metadata
```

`refine_content` and `process_refinement` are `ia_modules.pipeline.iterative_refinement`'s
`IterativeRefinementStep` and `ProcessRefinementResponseStep`; `max_iterations` (3 here)
is the step's config.

## Run it

```bash
echo '{"topic": "vector databases"}' > input.json
ia-modules run tests/pipelines/iterative_refinement_pipeline/pipeline.json --working-dir . --input input.json
```

`topic` is optional (the draft step defaults it). The run stops at the first
`refine_content` with `status: waiting_for_human`; the result carries the `ui_schema`
form and the draft to refine. Continuing needs a host that resumes pipelines with human
input, which the showcase backend does through its HITL manager; the bare CLI has no way
to answer the form.

## Output

While paused: `status` (`human_input_required`), `prompt`, `ui_schema`, `iteration`,
`current_result`, `refinement_history`, `max_iterations`. When finished:
`document`, `metadata` (`iterations`, `refinements`, `refinement_notes`) and
`status: finalized`.
