"""Tests for NdjsonLogger — NDJSON file logging for pipelines."""

import json
import pytest
from pathlib import Path

from ia_modules.pipeline.ndjson_logger import NdjsonLogger


@pytest.fixture
def log_path(tmp_path):
    return str(tmp_path / "test.jsonl")


class TestNdjsonLogger:
    async def test_creates_file_on_first_write(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("test_event")
        await logger.close()
        assert Path(log_path).exists()

    async def test_creates_parent_dirs(self, tmp_path):
        deep_path = str(tmp_path / "a" / "b" / "c" / "log.jsonl")
        logger = NdjsonLogger(deep_path)
        await logger.log("test_event")
        await logger.close()
        assert Path(deep_path).exists()

    async def test_writes_valid_ndjson(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("text", text="hello")
        await logger.log("step_start", step_name="fetch")
        await logger.close()

        lines = Path(log_path).read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "type" in parsed
            assert "timestamp" in parsed
            assert "_seq" in parsed

    async def test_seq_increments(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("a")
        await logger.log("b")
        await logger.log("c")
        await logger.close()

        lines = Path(log_path).read_text().strip().split("\n")
        seqs = [json.loads(line)["_seq"] for line in lines]
        assert seqs == [1, 2, 3]

    async def test_default_metadata_merged(self, log_path):
        logger = NdjsonLogger(log_path, default_metadata={"job_id": "j1", "pipeline": "test"})
        await logger.log("text", text="hi")
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["job_id"] == "j1"
        assert event["pipeline"] == "test"
        assert event["text"] == "hi"

    async def test_extra_kwargs(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("system", custom_field="value", count=42)
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["custom_field"] == "value"
        assert event["count"] == 42

    async def test_omits_none_fields(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("text")
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert "subtype" not in event
        assert "step_name" not in event
        assert "text" not in event
        assert "error" not in event

    async def test_log_returns_event_dict(self, log_path):
        logger = NdjsonLogger(log_path)
        event = await logger.log("step_start", step_name="s1")
        await logger.close()

        assert event["type"] == "step_start"
        assert event["step_name"] == "s1"
        assert event["_seq"] == 1


class TestNdjsonLoggerConvenience:
    async def test_pipeline_start(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log_pipeline_start("my_pipe", "exec-1", {"key": "val"})
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["type"] == "system"
        assert event["subtype"] == "pipeline_start"
        assert event["pipeline_name"] == "my_pipe"
        assert event["execution_id"] == "exec-1"
        assert event["data"] == {"key": "val"}

    async def test_pipeline_end_success(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log_pipeline_end("my_pipe", "exec-1", duration_ms=1500)
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["subtype"] == "pipeline_end"
        assert event["duration_ms"] == 1500

    async def test_pipeline_end_error(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log_pipeline_end("my_pipe", "exec-1", error="boom")
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["subtype"] == "pipeline_error"
        assert event["error"] == "boom"

    async def test_step_start(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log_step_start("fetch_data", {"url": "http://example.com"})
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["type"] == "step_start"
        assert event["step_name"] == "fetch_data"

    async def test_step_end_success(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log_step_end("fetch_data", duration_ms=200, output_data={"items": 5})
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["type"] == "step_finish"
        assert event["duration_ms"] == 200

    async def test_step_end_error(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log_step_end("fetch_data", error="timeout")
        await logger.close()

        event = json.loads(Path(log_path).read_text().strip())
        assert event["type"] == "step_error"
        assert event["error"] == "timeout"


class TestNdjsonLoggerLifecycle:
    async def test_close_idempotent(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("test")
        await logger.close()
        await logger.close()  # should not raise

    async def test_cleanup_calls_close(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("test")
        await logger.cleanup()
        assert logger._file is None

    async def test_append_after_close_reopens(self, log_path):
        logger = NdjsonLogger(log_path)
        await logger.log("first")
        await logger.close()
        await logger.log("second")
        await logger.close()

        lines = Path(log_path).read_text().strip().split("\n")
        assert len(lines) == 2
