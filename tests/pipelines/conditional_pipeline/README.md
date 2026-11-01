# Conditional Processing Pipeline

Routing on a value: records are scored for quality, and the score against a threshold
decides which of two processors runs before the results are aggregated.

```
test_data, threshold
   ↓
data_ingestor            → ingested_data
   ↓
quality_checker          → quality_score (0..1)
   ├─ score ≥ threshold → high_quality_processor   full refinement
   └─ score < threshold → low_quality_processor    basic cleanup
   ↓
results_aggregator       → aggregated_results
```

The two branches are `expression` conditions on `quality_score`, with the threshold
taken from the `threshold` parameter (`{{ parameters.threshold }}`).

## Run it

From the repository root:

```bash
echo '{"threshold": 0.7, "test_data": [{"id": 1, "value": "alpha"}, {"id": 2, "value": null}]}' > input.json
ia-modules run tests/pipelines/conditional_pipeline/pipeline.json --working-dir . --input input.json
```

Both parameters are required: `threshold` (number) and `test_data` (an array of
records). Leaving one out fails before anything runs, naming it.

## With and without an agent

`quality_checker` and the two processors are `LLMStep`s. With a registered agent
executor (the showcase backend has one) the model scores the records and describes its
processing. Without one, under pytest or the bare CLI, the checker scores records by how
many of their fields are filled, and the processors normalise (full) or trim and drop
nulls (basic), which is the behaviour this example had before it was LLM-backed. The
routing works the same way in both cases.

## Output

`quality_score`, `data_quality` (Poor/Fair/Good/Excellent), `processing_level` (`full` or
`basic`), `processed_data`, and `aggregated_results` with `total_records_processed` and a
`processing_summary`.
