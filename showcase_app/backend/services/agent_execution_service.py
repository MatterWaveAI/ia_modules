"""Agent Execution Service — tracks agent runs in DB, reads NDJSON logs from disk."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_executions (
    job_id TEXT PRIMARY KEY,
    execution_id TEXT,
    step_name TEXT,
    task TEXT,
    agent_role TEXT,
    agent_mode TEXT,
    cli_type TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    log_path TEXT,
    event_count INTEGER DEFAULT 0,
    result_text TEXT,
    error_text TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    metadata_json TEXT
)
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_agent_exec_status ON agent_executions(status)",
    "CREATE INDEX IF NOT EXISTS idx_agent_exec_started ON agent_executions(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_agent_exec_role ON agent_executions(agent_role)",
]


class AgentExecutionService:
    """Tracks agent executions in DB, reads NDJSON log files from disk."""

    def __init__(self, db_manager, logs_dir: str):
        self.db = db_manager
        self.logs_dir = Path(logs_dir)

    async def initialize(self):
        """Create the agent_executions table if it doesn't exist."""
        try:
            await self.db.execute_async(CREATE_TABLE_SQL)
            for idx_sql in CREATE_INDEXES_SQL:
                try:
                    await self.db.execute_async(idx_sql)
                except Exception:
                    pass  # Index may already exist
            logger.info("agent_executions table ready")
        except Exception as e:
            logger.error("Failed to create agent_executions table: %s", e)
            raise

    async def record_start(
        self,
        job_id: str,
        task: str = "",
        agent_role: str = "",
        agent_mode: str = "",
        cli_type: str = "",
        execution_id: str = None,
        step_name: str = None,
        log_path: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Record an agent execution starting."""
        now = datetime.now(timezone.utc).isoformat()
        if not log_path:
            log_path = str(self.logs_dir / job_id / "agent.jsonl")

        params = {
            "job_id": job_id,
            "execution_id": execution_id,
            "step_name": step_name,
            "task": task or "",
            "agent_role": agent_role,
            "agent_mode": agent_mode,
            "cli_type": cli_type,
            "status": "running",
            "log_path": log_path,
            "event_count": 0,
            "started_at": now,
            "metadata_json": json.dumps(metadata) if metadata else None,
        }

        sql = """
            INSERT OR REPLACE INTO agent_executions
                (job_id, execution_id, step_name, task, agent_role, agent_mode,
                 cli_type, status, log_path, event_count, started_at, metadata_json)
            VALUES
                (:job_id, :execution_id, :step_name, :task, :agent_role, :agent_mode,
                 :cli_type, :status, :log_path, :event_count, :started_at, :metadata_json)
        """
        try:
            await self.db.execute_async(sql, params)
        except Exception as e:
            logger.warning("Failed to record agent start: %s", e)

        return params

    async def record_complete(
        self,
        job_id: str,
        event_count: int = 0,
        result_text: str = None,
        error_text: str = None,
        duration_seconds: float = None,
    ):
        """Record an agent execution completing."""
        now = datetime.now(timezone.utc).isoformat()
        status = "failed" if error_text else "completed"

        sql = """
            UPDATE agent_executions
            SET status = :status, event_count = :event_count,
                result_text = :result_text, error_text = :error_text,
                completed_at = :completed_at, duration_seconds = :duration_seconds
            WHERE job_id = :job_id
        """
        params = {
            "status": status,
            "event_count": event_count,
            "result_text": result_text,
            "error_text": error_text,
            "completed_at": now,
            "duration_seconds": duration_seconds,
            "job_id": job_id,
        }
        try:
            await self.db.execute_async(sql, params)
        except Exception as e:
            logger.warning("Failed to record agent complete: %s", e)

    async def list_executions(
        self,
        status: str = None,
        role: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List agent executions from DB."""
        conditions = []
        params: Dict[str, Any] = {}
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if role:
            conditions.append("agent_role = :role")
            params["role"] = role

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT * FROM agent_executions
            {where}
            ORDER BY started_at DESC
            LIMIT :lim OFFSET :off
        """
        params["lim"] = limit
        params["off"] = offset

        try:
            result = await self.db.execute_async(sql, params)
            if result is None:
                return []
            rows = result.rows if hasattr(result, "rows") else (result if isinstance(result, list) else [])
            return [dict(r) if hasattr(r, "keys") else r for r in rows]
        except Exception as e:
            logger.error("Failed to list executions: %s", e)
            return []

    async def get_execution(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a single execution by job_id."""
        sql = "SELECT * FROM agent_executions WHERE job_id = :job_id"
        try:
            result = await self.db.execute_async(sql, {"job_id": job_id})
            if result is None:
                return None
            rows = result.rows if hasattr(result, "rows") else (result if isinstance(result, list) else [])
            if rows:
                r = rows[0]
                return dict(r) if hasattr(r, "keys") else r
            return None
        except Exception as e:
            logger.error("Failed to get execution: %s", e)
            return None

    async def get_log_events(
        self,
        job_id: str,
        event_types: List[str] = None,
        offset: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Read NDJSON events from the agent's log file on disk."""
        log_path = self.logs_dir / job_id / "agent.jsonl"
        if not log_path.exists():
            return []

        events = []
        line_num = 0
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event_types and event.get("type") not in event_types:
                        continue

                    line_num += 1
                    if line_num <= offset:
                        continue
                    events.append(event)
                    if len(events) >= limit:
                        break
        except Exception as e:
            logger.error("Failed to read log file %s: %s", log_path, e)

        return events

    async def get_log_summary(self, job_id: str) -> Dict[str, Any]:
        """Get summary stats from an agent's NDJSON log file."""
        log_path = self.logs_dir / job_id / "agent.jsonl"
        summary: Dict[str, Any] = {
            "job_id": job_id,
            "total_events": 0,
            "text_events": 0,
            "tool_use_events": 0,
            "tool_result_events": 0,
            "reasoning_events": 0,
            "error_events": 0,
            "tools_used": [],
            "duration_seconds": None,
            "first_event_at": None,
            "last_event_at": None,
        }
        if not log_path.exists():
            return summary

        tools_seen: set = set()
        first_ts = None
        last_ts = None

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    summary["total_events"] += 1
                    etype = event.get("type", "")

                    if etype == "text":
                        summary["text_events"] += 1
                    elif etype == "tool_use":
                        summary["tool_use_events"] += 1
                        tool_name = event.get("tool", "")
                        if tool_name:
                            tools_seen.add(tool_name)
                    elif etype == "tool_result":
                        summary["tool_result_events"] += 1
                    elif etype == "reasoning":
                        summary["reasoning_events"] += 1

                    if event.get("error"):
                        summary["error_events"] += 1

                    ts = event.get("timestamp")
                    if ts:
                        if first_ts is None:
                            first_ts = ts
                        last_ts = ts
        except Exception as e:
            logger.error("Failed to summarize log %s: %s", log_path, e)

        summary["tools_used"] = sorted(tools_seen)
        summary["first_event_at"] = first_ts
        summary["last_event_at"] = last_ts

        if first_ts and last_ts:
            try:
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                summary["duration_seconds"] = round((t1 - t0).total_seconds(), 2)
            except Exception:
                pass

        return summary

    async def scan_and_backfill(self) -> Dict[str, Any]:
        """Scan logs_dir for job directories not yet tracked in DB."""
        if not self.logs_dir.exists():
            return {"scanned": 0, "added": 0, "errors": 0}

        scanned = 0
        added = 0
        errors = 0

        for entry in self.logs_dir.iterdir():
            if not entry.is_dir():
                continue
            job_id = entry.name
            scanned += 1

            existing = await self.get_execution(job_id)
            if existing:
                continue

            log_file = entry / "agent.jsonl"
            if not log_file.exists():
                continue

            try:
                first_event = None
                last_event = None
                event_count = 0
                with open(log_file, "r", encoding="utf-8") as f:
                    for raw_line in f:
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        try:
                            evt = json.loads(raw_line)
                            event_count += 1
                            if first_event is None:
                                first_event = evt
                            last_event = evt
                        except json.JSONDecodeError:
                            continue

                started_at = (first_event or {}).get("timestamp", datetime.now(timezone.utc).isoformat())
                completed_at = (last_event or {}).get("timestamp")
                step_name = (first_event or {}).get("step_name", "")
                execution_id = (first_event or {}).get("execution_id")

                status = "completed"
                error_text = None
                result_text = None
                if last_event:
                    if last_event.get("error"):
                        status = "failed"
                        error_text = last_event.get("error", "")[:2000]
                    if last_event.get("result"):
                        result_text = last_event.get("result", "")[:5000]

                params = {
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "step_name": step_name,
                    "task": "",
                    "agent_role": "",
                    "agent_mode": "",
                    "cli_type": "",
                    "status": status,
                    "log_path": str(log_file),
                    "event_count": event_count,
                    "result_text": result_text,
                    "error_text": error_text,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "metadata_json": None,
                }
                sql = """
                    INSERT OR IGNORE INTO agent_executions
                        (job_id, execution_id, step_name, task, agent_role, agent_mode,
                         cli_type, status, log_path, event_count, result_text, error_text,
                         started_at, completed_at, metadata_json)
                    VALUES
                        (:job_id, :execution_id, :step_name, :task, :agent_role, :agent_mode,
                         :cli_type, :status, :log_path, :event_count, :result_text, :error_text,
                         :started_at, :completed_at, :metadata_json)
                """
                await self.db.execute_async(sql, params)
                added += 1
            except Exception as e:
                logger.warning("Failed to backfill job %s: %s", job_id, e)
                errors += 1

        logger.info("Backfill scan: scanned=%d added=%d errors=%d", scanned, added, errors)
        return {"scanned": scanned, "added": added, "errors": errors}
