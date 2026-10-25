"""
Pipeline Execution Tracking System

Provides database persistence and real-time monitoring of pipeline executions
with WebSocket updates for live viewing.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

try:
    from nexusql import DatabaseManager
except ImportError:
    # Fallback to database interface
    from ia_modules.database import DatabaseInterface as DatabaseManager

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Pipeline execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_FOR_HUMAN = "waiting_for_human"


class StepStatus(Enum):
    """Pipeline step status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionRecord:
    """Pipeline execution record"""
    execution_id: str
    pipeline_id: str
    pipeline_name: str
    status: ExecutionStatus
    started_at: str
    completed_at: Optional[str] = None
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['status'] = self.status.value
        return result


@dataclass
class StepExecutionRecord:
    """Pipeline step execution record"""
    step_execution_id: str
    execution_id: str
    step_id: str
    step_name: str
    step_type: str
    status: StepStatus
    started_at: str
    completed_at: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['status'] = self.status.value
        return result


class ExecutionTracker:
    """Tracks pipeline executions with database persistence and real-time updates"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.active_executions: Dict[str, ExecutionRecord] = {}
        self.websocket_connections: List[Any] = []  # WebSocket connections for real-time updates

    async def _load_active_executions(self):
        """Load active executions from database"""
        try:
            active_statuses = [ExecutionStatus.PENDING.value, ExecutionStatus.RUNNING.value]
            query = "SELECT * FROM pipeline_executions WHERE status IN (:status1, :status2) ORDER BY started_at DESC"

            rows = self.db.execute(query, {'status1': active_statuses[0], 'status2': active_statuses[1]})

            for row in rows:
                # Normalize timestamps from database (PostgreSQL returns datetime, SQLite returns string)
                started_at = row['started_at']
                if isinstance(started_at, datetime):
                    started_at = started_at.replace(tzinfo=None).isoformat()
                
                completed_at = row['completed_at']
                if completed_at and isinstance(completed_at, datetime):
                    completed_at = completed_at.replace(tzinfo=None).isoformat()
                
                execution = ExecutionRecord(
                    execution_id=row['execution_id'],
                    pipeline_id=row['pipeline_id'],
                    pipeline_name=row['pipeline_name'],
                    status=ExecutionStatus(row['status']),
                    started_at=started_at,
                    completed_at=completed_at,
                    total_steps=row.get('total_steps', 0),
                    completed_steps=row.get('completed_steps', 0),
                    failed_steps=row.get('failed_steps', 0),
                    input_data=json.loads(row['input_data']) if row.get('input_data') else None,
                    output_data=json.loads(row['output_data']) if row.get('output_data') else None,
                    error_message=row['error_message'],
                    execution_time_ms=row.get('execution_time_ms'),
                    metadata=json.loads(row['metadata_json']) if row.get('metadata_json') else None
                )
                self.active_executions[execution.execution_id] = execution

            logger.info(f"Loaded {len(self.active_executions)} active executions")

        except Exception as e:
            logger.error(f"Failed to load active executions: {e}")

    async def start_execution(self,
                            pipeline_id: str,
                            pipeline_name: str,
                            input_data: Dict[str, Any],
                            total_steps: int = 0,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start tracking a new pipeline execution"""

        logger.info(f"START: start_execution called for pipeline {pipeline_name}")
        
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        execution = ExecutionRecord(
            execution_id=execution_id,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            status=ExecutionStatus.RUNNING,
            started_at=now,
            total_steps=total_steps,
            input_data=input_data,
            metadata=metadata or {}
        )

        logger.info(f"BEFORE INSERT: About to insert execution {execution_id}")
        # Insert new execution to database
        await self._insert_execution(execution)
        logger.info(f"AFTER INSERT: Completed inserting execution {execution_id}")

        # Track in memory
        self.active_executions[execution_id] = execution

        # Broadcast update
        await self._broadcast_execution_update(execution)

        logger.info(f"Started execution tracking: {execution_id} for pipeline {pipeline_name}")
        return execution_id

    async def update_execution_status(self,
                                    execution_id: str,
                                    status: ExecutionStatus,
                                    completed_steps: Optional[int] = None,
                                    failed_steps: Optional[int] = None,
                                    output_data: Optional[Dict[str, Any]] = None,
                                    error_message: Optional[str] = None):
        """Update execution status"""

        if execution_id not in self.active_executions:
            logger.warning(f"Execution {execution_id} not found in active executions")
            return

        execution = self.active_executions[execution_id]

        # Update step counts first (before validation)
        if completed_steps is not None:
            execution.completed_steps = completed_steps

        if failed_steps is not None:
            execution.failed_steps = failed_steps

        if output_data is not None:
            execution.output_data = output_data

        if error_message is not None:
            execution.error_message = error_message

        # Validate: COMPLETED status should have at least one completed step
        if status == ExecutionStatus.COMPLETED:
            if execution.total_steps > 0 and execution.completed_steps == 0:
                logger.error(
                    f"Cannot mark execution {execution_id} as COMPLETED: "
                    f"has {execution.total_steps} total steps but 0 completed_steps. "
                    f"This indicates a data integrity issue."
                )
                raise ValueError(
                    f"Execution {execution_id} cannot be marked as COMPLETED with 0 completed steps. "
                    f"Total steps: {execution.total_steps}, Completed: {execution.completed_steps}"
                )

        # Update status after validation passes
        execution.status = status

        # Set completion time for terminal states (use naive datetime for consistency)
        if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            execution.completed_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Calculate execution time (both timestamps are now naive)
            if execution.started_at and execution.completed_at:
                # Ensure both are naive datetimes by removing any timezone info
                started_str = execution.started_at.replace('Z', '+00:00') if 'Z' in execution.started_at else execution.started_at
                completed_str = execution.completed_at.replace('Z', '+00:00') if 'Z' in execution.completed_at else execution.completed_at
                
                start_time = datetime.fromisoformat(started_str)
                end_time = datetime.fromisoformat(completed_str)
                
                # Strip timezone info if present to ensure naive datetime subtraction
                if start_time.tzinfo is not None:
                    start_time = start_time.replace(tzinfo=None)
                if end_time.tzinfo is not None:
                    end_time = end_time.replace(tzinfo=None)
                
                execution.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Remove from active executions only if completed or cancelled (keep failed for review)
            if status in [ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED]:
                self.active_executions.pop(execution_id, None)

        # Update in database
        await self._update_execution(execution)

        # Broadcast update
        await self._broadcast_execution_update(execution)

        logger.info(f"Updated execution {execution_id} status to {status.value}")

    async def start_step_execution(self,
                                 execution_id: str,
                                 step_id: str,
                                 step_name: str,
                                 step_type: str,
                                 input_data: Optional[Dict[str, Any]] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start tracking a step execution"""

        step_execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        step_execution = StepExecutionRecord(
            step_execution_id=step_execution_id,
            execution_id=execution_id,
            step_id=step_id,
            step_name=step_name,
            step_type=step_type,
            status=StepStatus.RUNNING,
            started_at=now,
            input_data=input_data,
            metadata=metadata or {}
        )

        # Insert new step execution to database
        await self._insert_step_execution(step_execution)

        # Broadcast update
        await self._broadcast_step_update(step_execution)

        logger.info(f"Started step execution: {step_execution_id} for step {step_name}")
        return step_execution_id

    async def complete_step_execution(self,
                                    step_execution_id: str,
                                    status: StepStatus,
                                    output_data: Optional[Dict[str, Any]] = None,
                                    error_message: Optional[str] = None,
                                    retry_count: int = 0):
        """Complete a step execution"""

        # Get step execution from database
        step_execution = await self._get_step_execution(step_execution_id)
        if not step_execution:
            logger.warning(f"Step execution {step_execution_id} not found")
            return

        # Update status and completion time (use naive datetime for consistency)
        step_execution.status = status
        step_execution.completed_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        step_execution.retry_count = retry_count

        if output_data is not None:
            step_execution.output_data = output_data

        if error_message is not None:
            step_execution.error_message = error_message

        # Calculate execution time
        if step_execution.started_at and step_execution.completed_at:
            # Parse ISO strings to datetime objects for calculation
            # Ensure both are naive datetimes by removing any timezone info
            started_str = step_execution.started_at.replace('Z', '+00:00') if 'Z' in step_execution.started_at else step_execution.started_at
            completed_str = step_execution.completed_at.replace('Z', '+00:00') if 'Z' in step_execution.completed_at else step_execution.completed_at
            
            start_time = datetime.fromisoformat(started_str)
            end_time = datetime.fromisoformat(completed_str)
            
            # Strip timezone info if present to ensure naive datetime subtraction
            if start_time.tzinfo is not None:
                start_time = start_time.replace(tzinfo=None)
            if end_time.tzinfo is not None:
                end_time = end_time.replace(tzinfo=None)
            
            step_execution.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Update step execution in database
        await self._update_step_execution(step_execution)

        # Update execution step counts
        await self._update_execution_step_counts(step_execution.execution_id)

        # Broadcast update
        await self._broadcast_step_update(step_execution)

        logger.info(f"Completed step execution: {step_execution_id} with status {status.value}")

    async def get_execution(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Get execution record by ID"""

        # Check active executions first
        if execution_id in self.active_executions:
            return self.active_executions[execution_id]

        # Query database
        query = "SELECT * FROM pipeline_executions WHERE execution_id = :execution_id"
        row = self.db.fetch_one(query, {'execution_id': execution_id})

        if not row:
            return None

        # Normalize timestamps from database (PostgreSQL returns datetime, SQLite returns string)
        started_at = row['started_at']
        if isinstance(started_at, datetime):
            started_at = started_at.replace(tzinfo=None).isoformat()
        
        completed_at = row['completed_at']
        if completed_at and isinstance(completed_at, datetime):
            completed_at = completed_at.replace(tzinfo=None).isoformat()

        return ExecutionRecord(
            execution_id=row['execution_id'],
            pipeline_id=row['pipeline_id'],
            pipeline_name=row['pipeline_name'],
            status=ExecutionStatus(row['status']),
            started_at=started_at,
            completed_at=completed_at,
            total_steps=row.get('total_steps', 0),
            completed_steps=row.get('completed_steps', 0),
            failed_steps=row.get('failed_steps', 0),
            input_data=json.loads(row['input_data']) if row.get('input_data') else None,
            output_data=json.loads(row['output_data']) if row.get('output_data') else None,
            error_message=row['error_message'],
            execution_time_ms=row.get('execution_time_ms'),
            metadata=json.loads(row['metadata_json']) if row.get('metadata_json') else None
        )

    async def get_execution_steps(self, execution_id: str) -> List[StepExecutionRecord]:
        """Get all step executions for a pipeline execution"""

        query = """
            SELECT * FROM step_executions
            WHERE execution_id = :execution_id
            ORDER BY started_at ASC
        """

        rows = self.db.execute(query, {'execution_id': execution_id})

        steps = []
        for row in rows:
            step = StepExecutionRecord(
                step_execution_id=row['step_execution_id'],
                execution_id=row['execution_id'],
                step_id=row['step_id'],
                step_name=row['step_name'],
                step_type=row['step_type'],
                status=StepStatus(row['status']),
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                input_data=json.loads(row['input_data']) if row['input_data'] else None,
                output_data=json.loads(row['output_data']) if row['output_data'] else None,
                error_message=row['error_message'],
                execution_time_ms=row['execution_time_ms'],
                retry_count=row['retry_count'],
                metadata=json.loads(row['metadata_json']) if row['metadata_json'] else None
            )
            steps.append(step)

        return steps

    async def get_recent_executions(self, limit: int = 50, pipeline_id: Optional[str] = None) -> List[ExecutionRecord]:
        """Get recent pipeline executions"""
        logger.info(f"GET_RECENT: Querying executions (limit={limit}, pipeline_id={pipeline_id})")

        if pipeline_id:
            query = """
                SELECT * FROM pipeline_executions
                WHERE pipeline_id = :pipeline_id
                ORDER BY started_at DESC
                LIMIT :limit
            """
            params = {'pipeline_id': pipeline_id, 'limit': limit}
        else:
            query = """
                SELECT * FROM pipeline_executions
                ORDER BY started_at DESC
                LIMIT :limit
            """
            params = {'limit': limit}

        logger.info(f"GET_RECENT: Executing query with params={params}")
        rows = self.db.execute(query, params)
        logger.info(f"GET_RECENT: Retrieved {len(rows)} rows from database")

        executions = []
        for row in rows:
            # Normalize timestamps from database (PostgreSQL returns datetime, SQLite returns string)
            started_at = row['started_at']
            if isinstance(started_at, datetime):
                started_at = started_at.replace(tzinfo=None).isoformat()
            
            completed_at = row['completed_at']
            if completed_at and isinstance(completed_at, datetime):
                completed_at = completed_at.replace(tzinfo=None).isoformat()
            
            execution = ExecutionRecord(
                execution_id=row['execution_id'],
                pipeline_id=row['pipeline_id'],
                pipeline_name=row['pipeline_name'],
                status=ExecutionStatus(row['status']),
                started_at=started_at,
                completed_at=completed_at,
                total_steps=row.get('total_steps', 0),
                completed_steps=row.get('completed_steps', 0),
                failed_steps=row.get('failed_steps', 0),
                input_data=json.loads(row['input_data']) if row.get('input_data') else None,
                output_data=json.loads(row['output_data']) if row.get('output_data') else None,
                error_message=row['error_message'],
                execution_time_ms=row.get('execution_time_ms'),
                metadata=json.loads(row['metadata_json']) if row.get('metadata_json') else None
            )
            executions.append(execution)

        logger.info(f"GET_RECENT: Returning {len(executions)} execution records")
        return executions

    async def get_execution_by_id(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Get a single execution by ID"""
        logger.info(f"GET_EXECUTION: Querying execution_id={execution_id}")
        
        query = """
            SELECT * FROM pipeline_executions
            WHERE execution_id = :execution_id
        """
        params = {'execution_id': execution_id}
        
        row = self.db.fetch_one(query, params)
        logger.info(f"GET_EXECUTION: Found row={row is not None}")
        
        if not row:
            return None
        
        # Normalize timestamps from database (PostgreSQL returns datetime, SQLite returns string)
        started_at = row['started_at']
        if isinstance(started_at, datetime):
            started_at = started_at.replace(tzinfo=None).isoformat()
        
        completed_at = row['completed_at']
        if completed_at and isinstance(completed_at, datetime):
            completed_at = completed_at.replace(tzinfo=None).isoformat()
        
        execution = ExecutionRecord(
            execution_id=row['execution_id'],
            pipeline_id=row['pipeline_id'],
            pipeline_name=row['pipeline_name'],
            status=ExecutionStatus(row['status']),
            started_at=started_at,
            completed_at=completed_at,
            total_steps=row.get('total_steps', 0),
            completed_steps=row.get('completed_steps', 0),
            failed_steps=row.get('failed_steps', 0),
            input_data=json.loads(row['input_data']) if row.get('input_data') else None,
            output_data=json.loads(row['output_data']) if row.get('output_data') else None,
            error_message=row['error_message'],
            execution_time_ms=row.get('execution_time_ms'),
            metadata=json.loads(row['metadata_json']) if row.get('metadata_json') else None
        )
        
        logger.info("GET_EXECUTION: Returning execution record")
        return execution

    async def get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""

        stats = {}

        # Total executions
        total_result = self.db.fetch_one("SELECT COUNT(*) as count FROM pipeline_executions")
        stats['total_executions'] = total_result['count'] if total_result else 0

        # Executions by status
        status_query = """
            SELECT status, COUNT(*) as count
            FROM pipeline_executions
            GROUP BY status
        """
        status_rows = self.db.execute(status_query)
        stats['by_status'] = {row['status']: row['count'] for row in status_rows}

        # Active executions
        stats['active_executions'] = len(self.active_executions)

        # Recent execution times (last 10 completed)
        time_query = """
            SELECT execution_time_ms
            FROM pipeline_executions
            WHERE execution_time_ms IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 10
        """
        time_rows = self.db.execute(time_query)
        if time_rows:
            times = [row['execution_time_ms'] for row in time_rows]
            stats['avg_execution_time_ms'] = sum(times) / len(times)
            stats['min_execution_time_ms'] = min(times)
            stats['max_execution_time_ms'] = max(times)

        return stats

    def add_websocket_connection(self, websocket):
        """Add WebSocket connection for real-time updates"""
        self.websocket_connections.append(websocket)

    def remove_websocket_connection(self, websocket):
        """Remove WebSocket connection"""
        if websocket in self.websocket_connections:
            self.websocket_connections.remove(websocket)

    async def _insert_execution(self, execution: ExecutionRecord):
        """Insert new execution record to database"""

        query = """
            INSERT INTO pipeline_executions
            (execution_id, pipeline_id, pipeline_name, status, started_at, completed_at,
             total_steps, completed_steps, failed_steps, input_data, output_data,
             error_message, execution_time_ms, metadata_json)
            VALUES (:execution_id, :pipeline_id, :pipeline_name, :status, :started_at, :completed_at,
                    :total_steps, :completed_steps, :failed_steps, :input_data, :output_data,
                    :error_message, :execution_time_ms, :metadata_json)
        """

        params = {
            'execution_id': execution.execution_id,
            'pipeline_id': execution.pipeline_id,
            'pipeline_name': execution.pipeline_name,
            'status': execution.status.value,
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'total_steps': execution.total_steps,
            'completed_steps': execution.completed_steps,
            'failed_steps': execution.failed_steps,
            'input_data': self._safe_json_dumps(execution.input_data),
            'output_data': self._safe_json_dumps(execution.output_data),
            'error_message': execution.error_message,
            'execution_time_ms': execution.execution_time_ms,
            'metadata_json': json.dumps(execution.metadata) if execution.metadata else None
        }

        logger.info(f"Inserting execution {execution.execution_id} to database")
        result = self.db.execute(query, params)
        logger.info(f"Insert result: success={result.success if hasattr(result, 'success') else 'N/A'}")
        if hasattr(result, 'error') and result.error:
            logger.error(f"Insert error: {result.error}")

    async def _update_execution(self, execution: ExecutionRecord):
        """Update existing execution record in database"""

        query = """
            UPDATE pipeline_executions SET
                status = :status,
                completed_at = :completed_at,
                completed_steps = :completed_steps,
                failed_steps = :failed_steps,
                output_data = :output_data,
                error_message = :error_message,
                execution_time_ms = :execution_time_ms,
                metadata_json = :metadata_json
            WHERE execution_id = :execution_id
        """

        params = {
            'execution_id': execution.execution_id,
            'status': execution.status.value,
            'completed_at': execution.completed_at,
            'completed_steps': execution.completed_steps,
            'failed_steps': execution.failed_steps,
            'output_data': self._safe_json_dumps(execution.output_data),
            'error_message': execution.error_message,
            'execution_time_ms': execution.execution_time_ms,
            'metadata_json': json.dumps(execution.metadata) if execution.metadata else None
        }

        logger.info(f"Updating execution {execution.execution_id} in database")
        result = self.db.execute(query, params)
        logger.info(f"Update result: success={result.success if hasattr(result, 'success') else 'N/A'}")
        if hasattr(result, 'error') and result.error:
            logger.error(f"Update error: {result.error}")

    async def _insert_step_execution(self, step_execution: StepExecutionRecord):
        """Insert new step execution record to database"""

        query = """
            INSERT INTO step_executions
            (step_execution_id, execution_id, step_id, step_name, step_type, status,
             started_at, completed_at, input_data, output_data, error_message,
             execution_time_ms, retry_count, metadata_json)
            VALUES (:step_execution_id, :execution_id, :step_id, :step_name, :step_type, :status,
                    :started_at, :completed_at, :input_data, :output_data, :error_message,
                    :execution_time_ms, :retry_count, :metadata_json)
        """

        params = {
            'step_execution_id': step_execution.step_execution_id,
            'execution_id': step_execution.execution_id,
            'step_id': step_execution.step_id,
            'step_name': step_execution.step_name,
            'step_type': step_execution.step_type,
            'status': step_execution.status.value,
            'started_at': step_execution.started_at,
            'completed_at': step_execution.completed_at,
            'input_data': self._safe_json_dumps(step_execution.input_data),
            'output_data': self._safe_json_dumps(step_execution.output_data),
            'error_message': step_execution.error_message,
            'execution_time_ms': step_execution.execution_time_ms,
            'retry_count': step_execution.retry_count,
            'metadata_json': json.dumps(step_execution.metadata) if step_execution.metadata else None
        }

        await self.db.execute_async(query, params)

    async def _update_step_execution(self, step_execution: StepExecutionRecord):
        """Update existing step execution record in database"""

        query = """
            UPDATE step_executions SET
                status = :status,
                completed_at = :completed_at,
                output_data = :output_data,
                error_message = :error_message,
                execution_time_ms = :execution_time_ms,
                retry_count = :retry_count,
                metadata_json = :metadata_json
            WHERE step_execution_id = :step_execution_id
        """

        params = {
            'step_execution_id': step_execution.step_execution_id,
            'status': step_execution.status.value,
            'completed_at': step_execution.completed_at,
            'output_data': self._safe_json_dumps(step_execution.output_data),
            'error_message': step_execution.error_message,
            'execution_time_ms': step_execution.execution_time_ms,
            'retry_count': step_execution.retry_count,
            'metadata_json': json.dumps(step_execution.metadata) if step_execution.metadata else None
        }

        self.db.execute(query, params)

    async def _get_step_execution(self, step_execution_id: str) -> Optional[StepExecutionRecord]:
        """Get step execution from database"""

        query = "SELECT * FROM step_executions WHERE step_execution_id = :step_execution_id"
        row = self.db.fetch_one(query, {'step_execution_id': step_execution_id})

        if not row:
            return None

        # Normalize timestamps to naive ISO format strings
        # PostgreSQL returns datetime objects (timezone-aware)
        # SQLite returns ISO strings (may include 'Z' or '+00:00')
        def normalize_timestamp(value):
            """Convert any timestamp format to naive ISO string"""
            if value is None:
                return None
            if isinstance(value, datetime):
                # DateTime object - remove timezone and convert to ISO string
                return value.replace(tzinfo=None).isoformat()
            elif isinstance(value, str):
                # String - parse and convert to naive datetime, then back to ISO string
                # This handles strings like '2024-10-24T10:30:00+00:00' or '2024-10-24T10:30:00Z'
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.replace(tzinfo=None).isoformat()
                except Exception:
                    # If parsing fails, just remove timezone markers
                    return value.replace('Z', '').replace('+00:00', '').replace('-00:00', '')
            return value
        
        started_at = normalize_timestamp(row['started_at'])
        completed_at = normalize_timestamp(row['completed_at'])

        return StepExecutionRecord(
            step_execution_id=row['step_execution_id'],
            execution_id=row['execution_id'],
            step_id=row['step_id'],
            step_name=row['step_name'],
            step_type=row['step_type'],
            status=StepStatus(row['status']),
            started_at=started_at,
            completed_at=completed_at,
            input_data=json.loads(row['input_data']) if row['input_data'] else None,
            output_data=json.loads(row['output_data']) if row['output_data'] else None,
            error_message=row['error_message'],
            execution_time_ms=row['execution_time_ms'],
            retry_count=row['retry_count'],
            metadata=json.loads(row['metadata_json']) if row['metadata_json'] else None
        )

    async def _update_execution_step_counts(self, execution_id: str):
        """Update step counts for an execution"""

        # Count completed and failed steps
        count_query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM step_executions
            WHERE execution_id = :execution_id
        """

        result = self.db.fetch_one(count_query, {'execution_id': execution_id})

        if result and execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            execution.completed_steps = result['completed']
            execution.failed_steps = result['failed']

            # Update database
            await self._update_execution(execution)

    async def _broadcast_execution_update(self, execution: ExecutionRecord):
        """Broadcast execution update to WebSocket connections"""

        message = {
            "type": "execution_update",
            "data": execution.to_dict()
        }

        await self._broadcast_message(message)

    async def _broadcast_step_update(self, step_execution: StepExecutionRecord):
        """Broadcast step update to WebSocket connections"""

        message = {
            "type": "step_update",
            "data": step_execution.to_dict()
        }

        await self._broadcast_message(message)

    async def _broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message to all WebSocket connections"""

        if not self.websocket_connections:
            return

        message_json = json.dumps(message)
        disconnected = []

        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                disconnected.append(websocket)

        # Remove disconnected connections
        for websocket in disconnected:
            self.remove_websocket_connection(websocket)

    def _safe_json_dumps(self, data: Any) -> Optional[str]:
        """Safely serialize data to JSON"""
        if data is None:
            return None
        try:
            return json.dumps(data)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error: {e}. Data type: {type(data)}")
            # Return error info instead of crashing
            return json.dumps({"_serialization_error": str(e)[:500], "_data_type": str(type(data))})


# Global execution tracker instance
execution_tracker: Optional[ExecutionTracker] = None


def get_execution_tracker() -> ExecutionTracker:
    """Get the global execution tracker instance"""
    global execution_tracker
    if execution_tracker is None:
        raise RuntimeError("Execution tracker not initialized")
    return execution_tracker


async def initialize_execution_tracker(db_manager: DatabaseManager) -> ExecutionTracker:
    """Initialize the global execution tracker"""
    global execution_tracker
    execution_tracker = ExecutionTracker(db_manager)
    return execution_tracker