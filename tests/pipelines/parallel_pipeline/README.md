# Parallel Data Processing Pipeline

Fan-out and fan-in: the input is split into chunks, three stream processors run on
them, and their results are merged and summarised.

```
loaded_data
   ↓
step1  DataSplitterStep (split_count: 3)   → data_chunks, chunk_count
   ├─ step2  StreamProcessorStep (stream 1) → processed_data
   ├─ step3  StreamProcessorStep (stream 2) → processed_data
   └─ step4  StreamProcessorStep (stream 3) → processed_data
   ↓
step5  ResultsMergerStep                   → merged_results
   ↓
step6  CompletedStatsCollectorStep         → statistics
```

`step1` has three outgoing `always` paths, so the runner executes steps 2 to 4 as
parallel branches, and `step5` runs once all three have finished.

## Run it

```bash
echo '{"loaded_data": [{"value": 1}, {"value": 2}, {"value": 3}, {"value": 4}, {"value": 5}, {"value": 6}]}' > input.json
ia-modules run tests/pipelines/parallel_pipeline/pipeline.json --working-dir . --input input.json
```

`loaded_data` (an array) is required. Give it at least as many items as `split_count`,
or some streams receive an empty chunk.

The steps compute statistics locally; no model or service is needed.

## Output

`data_chunks` and `chunk_count` from the splitter, each stream's result under its step
id (`step2`, `step3`, `step4`), `merged_results` with a `processing_summary`, and
`statistics` plus `total_records_processed` from the collector.
