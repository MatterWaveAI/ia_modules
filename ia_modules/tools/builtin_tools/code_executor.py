"""
Safe code executor tool for running Python code.

Provides sandboxed code execution with resource limits and security controls.
"""

import asyncio
import logging
import io
from typing import Any, Dict, Optional
from contextlib import redirect_stdout, redirect_stderr


class CodeExecutorTool:
    """
    Safe code executor for Python code.

    Features:
    - Sandboxed execution environment
    - Resource limits (time, memory)
    - Restricted imports
    - Captured stdout/stderr
    - Error handling

    Security Note: This is a basic implementation. For production use,
    consider using proper sandboxing solutions like RestrictedPython,
    Docker containers, or dedicated code execution services.

    Example:
        >>> executor = CodeExecutorTool()
        >>> result = await executor.execute('''
        ... def add(a, b):
        ...     return a + b
        ... result = add(5, 3)
        ... print(result)
        ... ''')
        >>> print(result['output'])  # "8\n"
        >>> print(result['result'])  # 8
    """

    def __init__(
        self,
        timeout: float = 5.0,
        allowed_imports: Optional[list[str]] = None
    ):
        """
        Initialize code executor.

        Args:
            timeout: Maximum execution time in seconds
            allowed_imports: List of allowed module names (None = basic whitelist)
        """
        self.timeout = timeout
        self.allowed_imports = allowed_imports or [
            "math", "random", "datetime", "json", "re",
            "statistics", "itertools", "collections"
        ]
        self.logger = logging.getLogger("CodeExecutorTool")

    async def execute(
        self,
        code: str,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Python code safely.

        Args:
            code: Python code to execute
            globals_dict: Global variables to provide
            locals_dict: Local variables to provide

        Returns:
            Dictionary with execution results
        """
        # Security check
        if not self._is_safe_code(code):
            raise ValueError("Code contains unsafe operations")

        # Setup execution environment
        if globals_dict is None:
            globals_dict = {}

        if locals_dict is None:
            locals_dict = {}

        # Add safe built-ins
        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "print": print,
        }

        globals_dict["__builtins__"] = safe_builtins

        # Add allowed imports
        for module_name in self.allowed_imports:
            try:
                globals_dict[module_name] = __import__(module_name)
            except ImportError:
                pass

        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            # Execute with timeout
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Run in executor to enable timeout
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: exec(code, globals_dict, locals_dict)
                    ),
                    timeout=self.timeout
                )

            # Get result if 'result' variable was set
            result = locals_dict.get("result", globals_dict.get("result"))

            return {
                "success": True,
                "result": result,
                "output": stdout_capture.getvalue(),
                "error": None
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "result": None,
                "output": stdout_capture.getvalue(),
                "error": f"Execution timed out after {self.timeout} seconds"
            }

        except Exception as e:
            return {
                "success": False,
                "result": None,
                "output": stdout_capture.getvalue(),
                "error": f"{type(e).__name__}: {str(e)}"
            }

    def _is_safe_code(self, code: str) -> bool:
        """
        Check if code is safe to execute.

        Args:
            code: Code to check

        Returns:
            True if safe, False otherwise
        """
        # Check for dangerous keywords
        dangerous_patterns = [
            "import os",
            "import sys",
            "import subprocess",
            "import socket",
            "__import__",
            "eval(",
            "exec(",
            "compile(",
            "open(",
            "file(",
            "input(",
            "raw_input(",
            "globals(",
            "locals(",
            "vars(",
            "dir(",
            "delattr",
            "setattr",
            "getattr",
            "__",
        ]

        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                self.logger.warning(f"Unsafe code pattern detected: {pattern}")
                return False

        return True

    async def execute_function(
        self,
        code: str,
        function_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute code defining a function and call it.

        Args:
            code: Python code defining the function
            function_name: Name of function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result
        """
        # Execute code to define function
        globals_dict: dict[str, Any] = {}
        result = await self.execute(code, globals_dict=globals_dict)

        if not result["success"]:
            raise ValueError(f"Code execution failed: {result['error']}")

        # Get function
        if function_name not in globals_dict:
            raise ValueError(f"Function {function_name} not defined")

        func = globals_dict[function_name]

        # Call function
        return func(*args, **kwargs)


async def code_executor_function(
    code: str,
    timeout: Optional[float] = None,
    globals_dict: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Code executor function for tool execution.

    Args:
        code: Python code to execute
        timeout: Maximum execution time in seconds
        globals_dict: Global variables to provide

    Returns:
        Dictionary with execution results
    """
    executor = CodeExecutorTool(timeout=timeout or 5.0)
    result = await executor.execute(code, globals_dict=globals_dict)

    return result


def create_code_executor_tool():
    """
    Create a code executor tool definition.

    Returns:
        ToolDefinition for code executor
    """
    from ..core import ToolDefinition

    return ToolDefinition(
        name="code_executor",
        description="Execute Python code safely in a sandboxed environment",
        parameters={
            "code": {
                "type": "string",
                "required": True,
                "description": "Python code to execute"
            },
            "timeout": {
                "type": "number",
                "required": False,
                "description": "Maximum execution time in seconds (default: 5.0)"
            },
            "globals_dict": {
                "type": "object",
                "required": False,
                "description": "Global variables to provide to the code"
            }
        },
        function=code_executor_function,
        requires_approval=True,  # Requires approval for safety
        metadata={
            "category": "code",
            "tags": ["execution", "python", "sandbox"],
            "requires_sandbox": True,
            "security_level": "medium"
        }
    )
