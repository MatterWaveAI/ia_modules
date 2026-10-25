"""
In-Memory Execution Tracker

Provides execution tracking capabilities for tests without requiring database persistence.
Implements the same interface as database-backed execution tracker.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class InMemoryExecutionTracker:
    """
    In-memory implementation of execution tracker for testing.
    
    Stores execution and step tracking data in memory instead of database.
    Implements the same interface as DatabaseExecutionTracker for compatibility.
    """
    
    def __init__(self):
        """Initialize in-memory storage"""
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.steps: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = []
        self.current_execution_id: Optional[str] = None
    
    def set_execution_id(self, execution_id: str):
        """Set the current execution ID"""
        self.current_execution_id = execution_id
    
    async def start_execution(
        self,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None
    ) -> str:
        """
        Start tracking a new pipeline execution
        
        Args:
            pipeline_name: Name of the pipeline being executed
            pipeline_version: Optional version of the pipeline
            input_data: Optional input data for the execution
            execution_id: Optional custom execution ID
            
        Returns:
            Execution ID string
        """
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        self.current_execution_id = execution_id
        
        self.executions[execution_id] = {
            'execution_id': execution_id,
            'pipeline_name': pipeline_name,
            'pipeline_version': pipeline_version,
            'input_data': input_data,
            'status': 'running',
            'start_time': datetime.now(),
            'end_time': None,
            'error': None
        }
        
        return execution_id
    
    async def start_step_execution(
        self,
        execution_id: str,
        step_name: str,
        step_id: str,
        step_type: str = "task",
        input_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start tracking a step execution
        
        Args:
            execution_id: Parent execution ID
            step_name: Name of the step
            step_id: Unique identifier for the step
            input_data: Optional input data for the step
            
        Returns:
            Step execution ID string
        """
        step_execution_id = f"{execution_id}_{step_id}_{uuid.uuid4().hex[:8]}"
        
        self.steps[step_execution_id] = {
            'step_execution_id': step_execution_id,
            'execution_id': execution_id,
            'step_name': step_name,
            'step_id': step_id,
            'step_type': step_type,
            'input_data': input_data,
            'output_data': None,
            'status': 'running',
            'start_time': datetime.now(),
            'end_time': None,
            'error': None
        }
        
        return step_execution_id
    
    async def complete_step_execution(
        self,
        step_execution_id: str,
        output_data: Optional[Dict[str, Any]] = None,
        status: str = 'completed',
        error: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        Complete a step execution
        
        Args:
            step_execution_id: ID of the step execution to complete
            output_data: Optional output data from the step
            status: Final status (completed, failed, etc.)
            error: Optional error message if step failed
            error_message: Alias for error (for compatibility)
        """
        # The runner passes StepStatus members as well as plain strings
        status = getattr(status, 'value', status)
        if step_execution_id in self.steps:
            # Use error_message if provided, otherwise use error
            final_error = error_message if error_message is not None else error
            
            self.steps[step_execution_id].update({
                'output_data': output_data,
                'status': status,
                'end_time': datetime.now(),
                'error': final_error
            })
    
    async def update_execution_status(
        self,
        execution_id: str,
        status: str,
        error: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        Update the status of a pipeline execution

        Args:
            execution_id: ID of the execution to update
            status: New status (running, completed, failed, etc.)
            error: Optional error message if execution failed
            error_message: Alias for error (for compatibility)
        """
        # The runner passes ExecutionStatus members as well as plain strings
        status = getattr(status, 'value', status)
        if execution_id in self.executions:
            final_error = error_message if error_message is not None else error
            self.executions[execution_id]['status'] = status
            if final_error:
                self.executions[execution_id]['error'] = final_error
            if status in ['completed', 'failed']:
                self.executions[execution_id]['end_time'] = datetime.now()
    
    def end_execution(
        self,
        execution_id: str,
        success: bool,
        error: Optional[str] = None
    ):
        """
        End a pipeline execution
        
        Args:
            execution_id: ID of the execution to end
            success: Whether execution was successful
            error: Optional error message if execution failed
        """
        if execution_id in self.executions:
            status = 'completed' if success else 'failed'
            self.executions[execution_id].update({
                'status': status,
                'end_time': datetime.now(),
                'error': error
            })
    
    async def log_message(
        self,
        execution_id: str,
        level: str,
        message: str,
        step_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Log a message for an execution
        
        Args:
            execution_id: ID of the execution
            level: Log level (INFO, ERROR, WARNING, etc.)
            message: Log message
            step_name: Optional step name
            data: Optional additional data
        """
        log_entry = {
            'execution_id': execution_id,
            'level': level,
            'message': message,
            'step_name': step_name,
            'data': data,
            'timestamp': datetime.now()
        }
        self.logs.append(log_entry)
    
    # Query methods for tests
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution data by ID"""
        return self.executions.get(execution_id)
    
    def get_step_executions(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all step executions for a given execution"""
        return [
            step for step in self.steps.values()
            if step['execution_id'] == execution_id
        ]
    
    def get_logs(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all logs for a given execution"""
        return [
            log for log in self.logs
            if log['execution_id'] == execution_id
        ]
    
    def get_all_executions(self) -> List[Dict[str, Any]]:
        """Get all executions"""
        return list(self.executions.values())
    
    def get_all_steps(self) -> List[Dict[str, Any]]:
        """Get all step executions"""
        return list(self.steps.values())
    
    def clear(self):
        """Clear all stored data (useful for test cleanup)"""
        self.executions.clear()
        self.steps.clear()
        self.logs.clear()
        self.current_execution_id = None
