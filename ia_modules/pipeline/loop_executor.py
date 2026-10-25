"""
Loop execution with iteration tracking and safety limits.

Provides runtime support for executing cyclic pipelines with safeguards
against infinite loops and excessive resource consumption.
"""
from typing import Dict, Any, Optional, Tuple, List
import asyncio
import logging
from datetime import datetime
from .loop_detector import LoopDetector

logger = logging.getLogger(__name__)


class LoopExecutionContext:
    """
    Tracks state during loop execution.

    Maintains iteration counts, timing information, and execution history
    to enforce safety limits and provide debugging information.
    """

    def __init__(self, loop_config: Optional[Dict] = None):
        """
        Initialize loop execution context.

        Args:
            loop_config: Configuration dict with keys:
                - max_iterations: Maximum iterations per step (default: 100)
                - max_loop_time_seconds: Maximum time in loop (default: 3600)
                - iteration_delay_seconds: Delay between iterations (default: 0)
        """
        config = loop_config or {}

        self.max_iterations = config.get('max_iterations', 100)
        self.max_loop_time = config.get('max_loop_time_seconds', 3600)  # 1 hour
        self.iteration_delay = config.get('iteration_delay_seconds', 0)

        # Runtime state
        self.iteration_count: Dict[str, int] = {}  # step -> iteration count
        self.loop_start_time: Dict[str, datetime] = {}  # loop_id -> start time
        self.loop_history: List[Dict] = []  # List of executed steps
        self.total_iterations = 0

    def increment_iteration(self, step_id: str) -> int:
        """
        Increment and return iteration count for step.

        Args:
            step_id: Step identifier

        Returns:
            New iteration count
        """
        self.iteration_count[step_id] = self.iteration_count.get(step_id, 0) + 1
        self.total_iterations += 1
        return self.iteration_count[step_id]

    def get_iteration(self, step_id: str) -> int:
        """
        Get current iteration count for step.

        Args:
            step_id: Step identifier

        Returns:
            Current iteration count (0 if step not executed yet)
        """
        return self.iteration_count.get(step_id, 0)

    def should_stop_loop(self, loop_id: str, step_id: str) -> Tuple[bool, str]:
        """
        Check if loop should stop due to safety limits.

        Args:
            loop_id: Loop identifier
            step_id: Current step ID

        Returns:
            (should_stop, reason) tuple
        """
        # Check iteration limit for this specific step
        iterations = self.get_iteration(step_id)
        if iterations >= self.max_iterations:
            return True, (
                f"Step '{step_id}' reached max iterations ({self.max_iterations})"
            )

        # Check time limit for the loop
        if loop_id in self.loop_start_time:
            elapsed = datetime.now() - self.loop_start_time[loop_id]
            if elapsed.total_seconds() >= self.max_loop_time:
                return True, (
                    f"Loop '{loop_id}' exceeded max time "
                    f"({self.max_loop_time}s)"
                )

        return False, ""

    def start_loop(self, loop_id: str):
        """
        Mark loop as started.

        Args:
            loop_id: Loop identifier
        """
        if loop_id not in self.loop_start_time:
            self.loop_start_time[loop_id] = datetime.now()
            logger.debug(f"Started tracking loop '{loop_id}'")

    def record_step(self, step_id: str, iteration: int, result: Optional[Any] = None):
        """
        Record step execution in history.

        Args:
            step_id: Step identifier
            iteration: Iteration number
            result: Step result (optional, for debugging)
        """
        self.loop_history.append({
            'step': step_id,
            'iteration': iteration,
            'timestamp': datetime.now(),
            'total_iterations': self.total_iterations
        })

    async def delay_if_needed(self):
        """Add delay between iterations if configured."""
        if self.iteration_delay > 0:
            logger.debug(f"Delaying {self.iteration_delay}s between iterations")
            await asyncio.sleep(self.iteration_delay)

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get summary of loop execution.

        Returns:
            Dict with execution statistics
        """
        return {
            'total_iterations': self.total_iterations,
            'steps_executed': len(self.iteration_count),
            'iteration_breakdown': dict(self.iteration_count),
            'loops_tracked': len(self.loop_start_time),
            'execution_count': len(self.loop_history)
        }

    def get_loop_duration(self, loop_id: str) -> Optional[float]:
        """
        Get duration of loop execution in seconds.

        Args:
            loop_id: Loop identifier

        Returns:
            Duration in seconds, or None if loop not started
        """
        if loop_id in self.loop_start_time:
            elapsed = datetime.now() - self.loop_start_time[loop_id]
            return elapsed.total_seconds()
        return None


class LoopAwareExecutor:
    """
    Pipeline executor with loop support.

    Extends standard pipeline execution to handle cyclic graphs with
    proper iteration tracking and safety limits.
    """

    def __init__(self, flow: Dict, loop_config: Optional[Dict] = None):
        """
        Initialize loop-aware executor.

        Args:
            flow: Pipeline flow definition
            loop_config: Loop configuration (passed to LoopExecutionContext)
        """
        self.flow = flow
        self.loop_config = loop_config or {}
        self.loop_detector = LoopDetector(flow)
        self.loop_context = LoopExecutionContext(loop_config)

        # Detect and validate loops upfront
        self.loops = self.loop_detector.detect_loops()
        self.validation_errors = self.loop_detector.validate_loops()

        if self.loops:
            logger.info(f"Detected {len(self.loops)} loop(s) in pipeline")
            for loop in self.loops:
                logger.info(f"  {loop}")

        if self.validation_errors:
            logger.warning("Loop validation warnings:")
            for error in self.validation_errors:
                logger.warning(f"  {error}")

    def has_loops(self) -> bool:
        """Check if pipeline contains any loops."""
        return len(self.loops) > 0

    def is_step_in_loop(self, step_id: str) -> bool:
        """Check if step is part of a loop."""
        return self.loop_detector.is_in_loop(step_id)

    def get_loop_id_for_step(self, step_id: str) -> Optional[str]:
        """Get loop ID for a step."""
        return self.loop_detector.get_loop_id(step_id)

    async def check_loop_safety(
        self,
        step_id: str,
        loop_id: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Check if it's safe to execute step (loop limits).

        Args:
            step_id: Step to check
            loop_id: Loop ID (if step is in loop)

        Returns:
            (is_safe, error_message) tuple
        """
        if not loop_id:
            return True, ""

        # Start tracking loop if first time
        self.loop_context.start_loop(loop_id)

        # Check safety limits
        should_stop, reason = self.loop_context.should_stop_loop(loop_id, step_id)

        if should_stop:
            logger.error(f"Loop safety limit reached: {reason}")
            return False, reason

        return True, ""

    def record_step_execution(
        self,
        step_id: str,
        iteration: int,
        loop_id: Optional[str],
        result: Optional[Any] = None
    ):
        """
        Record that a step was executed.

        Args:
            step_id: Step identifier
            iteration: Iteration number
            loop_id: Loop ID (if in loop)
            result: Step result (optional)
        """
        self.loop_context.record_step(step_id, iteration, result)

        # Log execution
        if loop_id:
            logger.info(
                f"Executed step '{step_id}' "
                f"(iteration {iteration}, loop '{loop_id}')"
            )
        else:
            logger.info(f"Executed step '{step_id}'")

    async def add_iteration_delay(self, step_id: str):
        """
        Add delay between loop iterations if configured.

        Args:
            step_id: Step that just executed
        """
        if self.is_step_in_loop(step_id):
            await self.loop_context.delay_if_needed()

    def get_execution_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about loop execution.

        Returns:
            Dict with:
                - has_loops: bool
                - loop_count: int
                - execution_summary: Dict
                - validation_errors: List[str]
        """
        return {
            'has_loops': self.has_loops(),
            'loop_count': len(self.loops),
            'execution_summary': self.loop_context.get_execution_summary(),
            'validation_errors': self.validation_errors,
            'loops': [
                {
                    'steps': loop.steps,
                    'entry_point': loop.entry_point,
                    'exit_conditions': len(loop.exit_conditions)
                }
                for loop in self.loops
            ]
        }

    def format_execution_report(self) -> str:
        """
        Format a human-readable execution report.

        Returns:
            Multi-line string with execution statistics
        """
        lines = ["Loop Execution Report", "=" * 50]

        summary = self.loop_context.get_execution_summary()
        lines.append(f"Total iterations: {summary['total_iterations']}")
        lines.append(f"Steps executed: {summary['steps_executed']}")

        lines.append("\nIteration breakdown:")
        for step_id, count in summary['iteration_breakdown'].items():
            loop_id = self.get_loop_id_for_step(step_id)
            if loop_id:
                lines.append(f"  {step_id}: {count} iterations (in {loop_id})")
            else:
                lines.append(f"  {step_id}: {count} iteration(s)")

        if self.loops:
            lines.append(f"\nLoops detected: {len(self.loops)}")
            for i, loop in enumerate(self.loops, 1):
                duration = self.loop_context.get_loop_duration(
                    f"loop_{loop.entry_point}"
                )
                lines.append(f"  Loop {i}: {loop}")
                if duration:
                    lines.append(f"    Duration: {duration:.2f}s")

        return '\n'.join(lines)
