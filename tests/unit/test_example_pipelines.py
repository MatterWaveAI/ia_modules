"""
Every example under tests/pipelines validates and runs offline with the inputs it
declares. An example that needs an outside service says so in EXTERNAL and is
skipped; a folder without a pipeline.json must have a README saying what it is.
"""
import asyncio
import json
from pathlib import Path

import pytest

from ia_modules.cli.validate import validate_pipeline
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner

PIPELINES = Path(__file__).parent.parent / "pipelines"

EXTERNAL = {
    "vector_rag_pipeline": "needs chromadb and an OpenAI key (index_pipeline.json / query_pipeline.json)",
}

SAMPLE_VALUES = {
    "string": "sample text",
    "integer": 2,
    "number": 0.7,
    "boolean": True,
    "array": [{"id": 1, "value": "alpha"}, {"id": 2, "value": "beta"}],
    "object": {"key": "value"},
}


def declared_inputs(config, tmp_path):
    """A value for every declared parameter: its default, else a sample of its type."""
    inputs = {}
    for parameter in config.get("parameters") or []:
        if not isinstance(parameter, dict) or "name" not in parameter:
            continue
        kind = (parameter.get("schema") or {}).get("type", "string")
        inputs[parameter["name"]] = parameter.get("default", SAMPLE_VALUES.get(kind, "sample"))
    if "output_dir" in inputs:
        inputs["output_dir"] = str(tmp_path)  # examples that write files write them here
    return inputs


def example_dirs():
    return [d for d in sorted(PIPELINES.iterdir()) if d.is_dir() and not d.name.startswith("_")]


@pytest.mark.parametrize("example", example_dirs(), ids=lambda d: d.name)
async def test_example_validates_and_runs(example, tmp_path, monkeypatch):
    if example.name in EXTERNAL:
        pytest.skip(EXTERNAL[example.name])

    pipeline_file = example / "pipeline.json"
    if not pipeline_file.exists():
        assert (example / "README.md").exists(), f"{example.name}: no pipeline.json and no README saying what it is"
        pytest.skip(f"{example.name}: step fixtures, not a runnable example")

    config = json.loads(pipeline_file.read_text(encoding="utf-8"))
    result = validate_pipeline(config)
    assert result.is_valid, f"{example.name} does not validate: {result.errors}"

    # Anything an example writes relative to the working directory lands here
    monkeypatch.chdir(tmp_path)
    runner = GraphPipelineRunner()
    outcome = await asyncio.wait_for(runner.run_pipeline_from_json(config, declared_inputs(config, tmp_path)), 60)

    status = runner.services.get("execution_tracker").get_all_executions()[0]["status"]
    paused_for_human = isinstance(outcome, dict) and outcome.get("status") == "waiting_for_human"
    assert status == "completed" or paused_for_human, f"{example.name} ended with status {status!r}"
    assert runner.execution_stats.get("steps_executed", 0) >= 1
