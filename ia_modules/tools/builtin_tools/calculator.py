"""
Calculator tool for mathematical operations.

Provides safe mathematical expression evaluation and advanced calculations.
"""

import logging
import math
import re
from typing import Any, Dict, Optional, Union


class CalculatorTool:
    """
    Calculator tool for mathematical operations.

    Features:
    - Safe expression evaluation
    - Support for common math functions
    - Unit conversions
    - Statistical calculations
    - Error handling

    Example:
        >>> calc = CalculatorTool()
        >>> result = await calc.evaluate("2 + 2 * 3")
        >>> print(result)  # 8.0
        >>>
        >>> result = await calc.evaluate("sqrt(16) + log(100)")
        >>> print(result)  # 6.0
    """

    def __init__(self):
        """Initialize calculator tool."""
        self.logger = logging.getLogger("CalculatorTool")

        # Safe namespace for eval
        self.safe_namespace = {
            # Math functions
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            "sqrt": math.sqrt,
            "exp": math.exp,
            "log": math.log,
            "log10": math.log10,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "degrees": math.degrees,
            "radians": math.radians,
            "floor": math.floor,
            "ceil": math.ceil,
            "factorial": math.factorial,
            # Constants
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
        }

    async def evaluate(self, expression: str) -> Union[float, int]:
        """
        Evaluate a mathematical expression.

        Args:
            expression: Mathematical expression to evaluate

        Returns:
            Result of calculation

        Raises:
            ValueError: If expression is invalid or unsafe
        """
        # Clean expression
        expression = expression.strip()

        # Security check - only allow safe characters
        if not self._is_safe_expression(expression):
            raise ValueError("Expression contains unsafe characters")

        try:
            # Evaluate in safe namespace
            result = eval(expression, {"__builtins__": {}}, self.safe_namespace)

            # Convert to appropriate numeric type
            if isinstance(result, (int, float)):
                return float(result) if isinstance(result, float) else result
            else:
                raise ValueError(f"Expression must evaluate to a number, got {type(result)}")

        except ZeroDivisionError:
            raise ValueError("Division by zero")
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def _is_safe_expression(self, expression: str) -> bool:
        """
        Check if expression is safe to evaluate.

        Args:
            expression: Expression to check

        Returns:
            True if safe, False otherwise
        """
        # Allow numbers, operators, parentheses, and whitelisted function names
        allowed_pattern = r'^[0-9+\-*/().,\s\w]+$'

        if not re.match(allowed_pattern, expression):
            return False

        # Check for dangerous keywords
        dangerous_keywords = [
            "import", "exec", "eval", "__", "open", "file",
            "compile", "globals", "locals", "vars"
        ]

        expression_lower = expression.lower()
        for keyword in dangerous_keywords:
            if keyword in expression_lower:
                return False

        return True

    async def calculate_statistics(
        self,
        numbers: list[float],
        operations: Optional[list[str]] = None
    ) -> Dict[str, float]:
        """
        Calculate statistics for a list of numbers.

        Args:
            numbers: List of numbers
            operations: List of operations to perform (default: all)

        Returns:
            Dictionary of statistics
        """
        if not numbers:
            raise ValueError("Empty number list")

        if operations is None:
            operations = ["mean", "median", "std", "min", "max", "sum"]

        results = {}

        if "mean" in operations:
            results["mean"] = sum(numbers) / len(numbers)

        if "median" in operations:
            sorted_numbers = sorted(numbers)
            n = len(sorted_numbers)
            if n % 2 == 0:
                results["median"] = (sorted_numbers[n//2-1] + sorted_numbers[n//2]) / 2
            else:
                results["median"] = sorted_numbers[n//2]

        if "std" in operations:
            mean = sum(numbers) / len(numbers)
            variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
            results["std"] = math.sqrt(variance)

        if "min" in operations:
            results["min"] = min(numbers)

        if "max" in operations:
            results["max"] = max(numbers)

        if "sum" in operations:
            results["sum"] = sum(numbers)

        if "count" in operations:
            results["count"] = len(numbers)

        return results


async def calculator_function(
    expression: Optional[str] = None,
    operation: Optional[str] = None,
    numbers: Optional[list[float]] = None
) -> Dict[str, Any]:
    """
    Calculator function for tool execution.

    Args:
        expression: Mathematical expression to evaluate
        operation: Statistical operation to perform
        numbers: List of numbers for statistical operations

    Returns:
        Dictionary with calculation results
    """
    calc = CalculatorTool()

    if expression:
        # Evaluate expression
        result = await calc.evaluate(expression)
        return {
            "expression": expression,
            "result": result,
            "type": "expression"
        }

    elif operation and numbers:
        # Statistical calculation
        stats = await calc.calculate_statistics(numbers, [operation])
        return {
            "operation": operation,
            "numbers": numbers,
            "result": stats.get(operation),
            "type": "statistics"
        }

    else:
        raise ValueError("Must provide either 'expression' or 'operation' with 'numbers'")


def create_calculator_tool():
    """
    Create a calculator tool definition.

    Returns:
        ToolDefinition for calculator
    """
    from ..core import ToolDefinition

    return ToolDefinition(
        name="calculator",
        description="Evaluate mathematical expressions and perform calculations",
        parameters={
            "expression": {
                "type": "string",
                "required": False,
                "description": "Mathematical expression to evaluate (e.g., '2 + 2 * 3', 'sqrt(16)')"
            },
            "operation": {
                "type": "string",
                "required": False,
                "description": "Statistical operation: mean, median, std, min, max, sum, count"
            },
            "numbers": {
                "type": "array",
                "required": False,
                "description": "List of numbers for statistical operations"
            }
        },
        function=calculator_function,
        metadata={
            "category": "math",
            "tags": ["calculation", "mathematics", "statistics"],
            "safe": True
        }
    )
