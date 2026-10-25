"""
Test utilities for pipeline testing.

Provides helper functions to simplify test setup and execution.
"""

import uuid
from typing import Optional
from .core import ExecutionContext


def create_test_execution_context(
    execution_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    **kwargs
) -> ExecutionContext:
    """
    Create an ExecutionContext for testing.

    Args:
        execution_id: Execution ID (auto-generated if None)
        pipeline_id: Pipeline ID (optional)
        **kwargs: Additional metadata

    Returns:
        ExecutionContext instance

    Example:
        >>> ctx = create_test_execution_context()
        >>> result = await pipeline.run(input_data, ctx)
    """
    return ExecutionContext(
        execution_id=execution_id or str(uuid.uuid4()),
        pipeline_id=pipeline_id,
        metadata=kwargs
    )
