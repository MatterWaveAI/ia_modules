"""NDJSON Logger — writes pipeline and agent events as newline-delimited JSON.

Default logging backend for ia_modules pipelines. Each event is one JSON line
appended to a .jsonl file, making logs streamable and easy to tail.

Usage:
    logger = NdjsonLogger("/path/to/logs/execution.jsonl")
    await logger.log("step_start", step_name="fetch_data", data={"url": "..."})
    await logger.close()

Or register on ServiceRegistry for automatic pipeline integration:
    services = ServiceRegistry()
    services.register("ndjson_logger", NdjsonLogger("/path/to/run.jsonl"))
    pipeline = Pipeline(name="my_pipe", steps=steps, flow=flow, services=services)
    # Pipeline will automatically log step lifecycle events
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, IO, Optional

logger = logging.getLogger(__name__)


class NdjsonLogger:
    """Appends JSON-line events to a .jsonl file.

    Each `log()` call writes exactly one line, flushed immediately so
    tailers see it in real time. Uses synchronous file I/O in a thread
    executor to avoid blocking the event loop without extra dependencies.

    Args:
        path: File path for the .jsonl log. Parent dirs are created automatically.
        default_metadata: Dict merged into every event (e.g. execution_id, pipeline_name).
    """

    def __init__(
        self,
        path: str,
        default_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.path = Path(path)
        self.default_metadata = default_metadata or {}
        self._seq = 0
        self._file: Optional[IO] = None

    def _ensure_open(self):
        """Lazily open the file on first write (called in thread)."""
        if self._file is None:
            os.makedirs(str(self.path.parent), exist_ok=True)
            self._file = open(self.path, "a", encoding="utf-8")

    def _write_sync(self, line: str):
        """Write a single line — runs in executor thread."""
        self._ensure_open()
        self._file.write(line + "\n")
        self._file.flush()

    async def log(
        self,
        event_type: str,
        *,
        subtype: Optional[str] = None,
        step_name: Optional[str] = None,
        text: Optional[str] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        **extra,
    ) -> Dict[str, Any]:
        """Write one NDJSON event line.

        Returns the event dict that was written.
        """
        self._seq += 1
        event: Dict[str, Any] = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_seq": self._seq,
        }
        if subtype:
            event["subtype"] = subtype
        if step_name:
            event["step_name"] = step_name
        if text is not None:
            event["text"] = text
        if result is not None:
            event["result"] = result
        if error:
            event["error"] = error
        if data:
            event["data"] = data

        # Merge defaults and extras
        event.update(self.default_metadata)
        event.update(extra)

        line = json.dumps(event, default=str, separators=(",", ":"))
        self._write_sync(line)
        return event

    # ── Convenience methods for pipeline lifecycle ──

    async def log_pipeline_start(
        self, pipeline_name: str, execution_id: str, input_data: Optional[Dict] = None,
    ):
        return await self.log(
            "system", subtype="pipeline_start",
            pipeline_name=pipeline_name, execution_id=execution_id,
            data=input_data,
        )

    async def log_pipeline_end(
        self,
        pipeline_name: str,
        execution_id: str,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
    ):
        return await self.log(
            "system",
            subtype="pipeline_error" if error else "pipeline_end",
            pipeline_name=pipeline_name,
            execution_id=execution_id,
            duration_ms=duration_ms,
            error=error,
        )

    async def log_step_start(
        self, step_name: str, input_data: Optional[Dict] = None,
    ):
        return await self.log(
            "step_start", step_name=step_name, data=input_data,
        )

    async def log_step_end(
        self,
        step_name: str,
        duration_ms: Optional[int] = None,
        output_data: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        return await self.log(
            "step_finish" if not error else "step_error",
            step_name=step_name,
            duration_ms=duration_ms,
            data=output_data,
            error=error,
        )

    async def close(self):
        """Flush and close the underlying file."""
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None

    async def cleanup(self):
        """ServiceRegistry cleanup hook."""
        await self.close()
