"""
Service System for Pipeline Dependency Injection

Production-ready service registry for pipeline components.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json


class LogEntry:
    """Represents a single log entry"""
    def __init__(self, level: str, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        self.timestamp = datetime.now()
        self.level = level
        self.message = message
        self.step_name = step_name
        self.data = data or {}


class CentralLoggingService:
    """Central logging service that collects logs during execution and writes to database.

    When an NdjsonLogger is attached (via ``set_ndjson_logger``), every log()
    call also queues an NDJSON event. Call ``await flush_ndjson()`` to write
    pending entries — Pipeline does this automatically at step boundaries.
    """

    def __init__(self):
        self.execution_logs: List[LogEntry] = []
        self.current_execution_id: Optional[str] = None
        self._ndjson_logger = None
        self._ndjson_pending: List[Dict[str, Any]] = []

    def set_execution_id(self, execution_id: str):
        """Set the current execution ID for logging"""
        self.current_execution_id = execution_id

    def set_ndjson_logger(self, ndjson_logger) -> None:
        """Attach an NdjsonLogger so log() calls also produce NDJSON events."""
        self._ndjson_logger = ndjson_logger

    def log(self, level: str, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Log a message to the central service"""
        entry = LogEntry(level, message, step_name, data)
        self.execution_logs.append(entry)

        # Queue NDJSON event if logger attached
        if self._ndjson_logger is not None:
            self._ndjson_pending.append({
                "level": level,
                "message": message,
                "step_name": step_name,
                "data": data,
            })

    async def flush_ndjson(self) -> None:
        """Write pending log entries to the attached NdjsonLogger."""
        if not self._ndjson_logger or not self._ndjson_pending:
            return
        pending = self._ndjson_pending
        self._ndjson_pending = []
        for entry in pending:
            await self._ndjson_logger.log(
                "log",
                subtype=entry["level"].lower(),
                step_name=entry["step_name"],
                text=entry["message"],
                data=entry["data"],
            )

    def info(self, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Log an info message"""
        self.log("INFO", message, step_name, data)

    def error(self, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Log an error message"""
        self.log("ERROR", message, step_name, data)

    def warning(self, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Log a warning message"""
        self.log("WARNING", message, step_name, data)

    def success(self, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Log a success message"""
        self.log("SUCCESS", message, step_name, data)

    async def write_to_database(self, db_service):
        """Write all collected logs to the database"""
        if not self.current_execution_id or not db_service:
            return

        try:
            for log_entry in self.execution_logs:
                # Write each log entry to database
                if hasattr(db_service, 'log_execution_event'):
                    await db_service.log_execution_event(
                        execution_id=self.current_execution_id,
                        event_type=log_entry.level,
                        message=log_entry.message,
                        step_name=log_entry.step_name,
                        data=json.dumps(log_entry.data),
                        timestamp=log_entry.timestamp.isoformat()
                    )
        except Exception:
            pass  # Silently fail database logging

    def clear_logs(self):
        """Clear all collected logs"""
        self.execution_logs.clear()
        self.current_execution_id = None


class ServiceRegistry:
    """Simple service container for dependency injection"""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        # Initialize central logging service
        self._services['central_logger'] = CentralLoggingService()

    def register(self, name: str, service: Any):
        """Register a service.

        When registering ``ndjson_logger``, auto-attaches it to the
        CentralLoggingService so log() calls also produce NDJSON events.
        """
        self._services[name] = service
        # Auto-wire: central_logger ↔ ndjson_logger
        if name == "ndjson_logger":
            cl = self._services.get("central_logger")
            if cl and hasattr(cl, "set_ndjson_logger"):
                cl.set_ndjson_logger(service)

    def get(self, name: str) -> Optional[Any]:
        """Get a service by name"""
        return self._services.get(name)

    def has(self, name: str) -> bool:
        """Check if service is registered"""
        return name in self._services

    async def cleanup_all(self):
        """Cleanup all services that support it"""
        for service in self._services.values():
            if hasattr(service, 'cleanup'):
                await service.cleanup()
