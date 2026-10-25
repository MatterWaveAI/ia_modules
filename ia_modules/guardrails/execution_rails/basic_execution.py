"""Basic execution safety rails for tool and code execution."""
from typing import Any, Dict, Optional, List
import re
from ..base import BaseGuardrail
from ..models import RailResult, RailAction, RailType


class ToolValidationRail(BaseGuardrail):
    """
    Validate tool/function calls before execution.

    Ensures only allowed tools are called with valid parameters.
    """

    def __init__(self, config, allowed_tools: Optional[List[str]] = None,
                 blocked_tools: Optional[List[str]] = None,
                 require_confirmation: Optional[List[str]] = None):
        """
        Initialize tool validation rail.

        Args:
            config: Rail configuration
            allowed_tools: Whitelist of allowed tool names (None = all allowed)
            blocked_tools: Blacklist of blocked tool names
            require_confirmation: Tools requiring human confirmation before execution
        """
        super().__init__(config)
        self.allowed_tools = allowed_tools
        self.blocked_tools = blocked_tools or []
        self.require_confirmation = require_confirmation or []

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Validate tool call."""
        context = context or {}

        # Extract tool name from content or context
        tool_name = None
        if isinstance(content, dict):
            tool_name = content.get("tool_name", content.get("function_name"))
        else:
            tool_name = context.get("tool_name", context.get("function_name"))

        if not tool_name:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason="No tool name found in request",
                confidence=1.0
            )

        # Check blocked tools
        if tool_name in self.blocked_tools:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason=f"Tool '{tool_name}' is blocked",
                confidence=1.0,
                metadata={"tool_name": tool_name, "reason": "blocked_tool"}
            )

        # Check allowed tools
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason=f"Tool '{tool_name}' not in allowed list",
                confidence=1.0,
                metadata={
                    "tool_name": tool_name,
                    "allowed_tools": self.allowed_tools
                }
            )

        # Check if confirmation required
        if tool_name in self.require_confirmation:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.REDIRECT,
                original_content=content,
                triggered=True,
                reason=f"Tool '{tool_name}' requires human confirmation",
                confidence=1.0,
                metadata={
                    "tool_name": tool_name,
                    "action_required": "human_confirmation"
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.EXECUTION,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"tool_name": tool_name}
        )


class CodeExecutionSafetyRail(BaseGuardrail):
    """
    Validate code before execution.

    Detects dangerous operations in code snippets.
    """

    DANGEROUS_PATTERNS = [
        # System operations
        r"\bos\.system\b",
        r"\bsubprocess\.(call|run|Popen)\b",
        r"\beval\b",
        r"\bexec\b",
        r"\b__import__\b",

        # File operations
        r"\bopen\s*\([^)]*['\"]w['\"]",  # Write mode
        r"\bos\.remove\b",
        r"\bos\.unlink\b",
        r"\bshutil\.rmtree\b",

        # Network operations
        r"\bsocket\.",
        r"\brequests\.(post|put|delete)\b",
        r"\burllib\.request\b",

        # Database operations
        r"\bDROP\s+TABLE\b",
        r"\bDELETE\s+FROM\b",
        r"\bTRUNCATE\b",
    ]

    SAFE_IMPORTS = {
        "math", "random", "datetime", "json", "re", "collections",
        "itertools", "functools", "typing", "dataclasses"
    }

    def __init__(self, config, allow_file_read: bool = True,
                 allow_network: bool = False,
                 custom_patterns: Optional[List[str]] = None):
        """
        Initialize code execution safety rail.

        Args:
            config: Rail configuration
            allow_file_read: Allow file read operations
            allow_network: Allow network operations
            custom_patterns: Additional dangerous patterns
        """
        super().__init__(config)
        self.allow_file_read = allow_file_read
        self.allow_network = allow_network

        # Build pattern list based on permissions
        self.patterns = []
        for pattern in self.DANGEROUS_PATTERNS:
            if not allow_network and ("socket" in pattern or "requests" in pattern or "urllib" in pattern):
                self.patterns.append(pattern)
            elif "open\\s*\\(" not in pattern and "os\\.remove" not in pattern:
                self.patterns.append(pattern)

        if custom_patterns:
            self.patterns.extend(custom_patterns)

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Validate code for dangerous operations."""
        if not isinstance(content, str):
            content = str(content)

        matched_patterns = []
        for pattern in self.patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matched_patterns.append(pattern)

        if matched_patterns:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason=f"Dangerous code patterns detected: {len(matched_patterns)} matches",
                confidence=0.9,
                metadata={
                    "matched_patterns": matched_patterns[:3],
                    "total_matches": len(matched_patterns),
                    "recommendation": "Review code for security issues"
                }
            )

        # Check imports
        import_pattern = r"^\s*(?:from|import)\s+(\w+)"
        imports = re.findall(import_pattern, content, re.MULTILINE)
        unsafe_imports = [imp for imp in imports if imp not in self.SAFE_IMPORTS]

        if unsafe_imports:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason=f"Potentially unsafe imports: {', '.join(unsafe_imports)}",
                confidence=0.6,
                metadata={
                    "unsafe_imports": unsafe_imports,
                    "safe_imports": list(self.SAFE_IMPORTS)
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.EXECUTION,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"imports": imports}
        )


class ParameterValidationRail(BaseGuardrail):
    """
    Validate function/tool parameters.

    Ensures parameters meet type, range, and format requirements.
    """

    def __init__(self, config, parameter_schemas: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize parameter validation rail.

        Args:
            config: Rail configuration
            parameter_schemas: Dict mapping tool names to parameter schemas
                Example: {
                    "send_email": {
                        "to": {"type": "email", "required": True},
                        "amount": {"type": "number", "min": 0, "max": 1000}
                    }
                }
        """
        super().__init__(config)
        self.parameter_schemas = parameter_schemas or {}

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Validate function parameters."""
        context = context or {}

        # Extract tool name and parameters
        tool_name = context.get("tool_name")
        parameters = content if isinstance(content, dict) else {}

        if not tool_name or tool_name not in self.parameter_schemas:
            # No schema to validate against
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.ALLOW,
                original_content=content,
                triggered=False
            )

        schema = self.parameter_schemas[tool_name]
        errors = []

        # Validate each parameter
        for param_name, param_schema in schema.items():
            # Check required
            if param_schema.get("required", False) and param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
                continue

            if param_name not in parameters:
                continue

            value = parameters[param_name]

            # Type validation
            param_type = param_schema.get("type")
            if param_type == "email":
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', str(value)):
                    errors.append(f"Invalid email format: {param_name}")
            elif param_type == "number":
                if not isinstance(value, (int, float)):
                    errors.append(f"Parameter {param_name} must be a number")
                else:
                    # Range validation
                    if "min" in param_schema and value < param_schema["min"]:
                        errors.append(f"{param_name} below minimum: {param_schema['min']}")
                    if "max" in param_schema and value > param_schema["max"]:
                        errors.append(f"{param_name} above maximum: {param_schema['max']}")
            elif param_type == "string":
                if not isinstance(value, str):
                    errors.append(f"Parameter {param_name} must be a string")
                else:
                    if "max_length" in param_schema and len(value) > param_schema["max_length"]:
                        errors.append(f"{param_name} exceeds max length: {param_schema['max_length']}")

        if errors:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason=f"Parameter validation failed: {len(errors)} errors",
                confidence=1.0,
                metadata={
                    "errors": errors,
                    "tool_name": tool_name
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.EXECUTION,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"tool_name": tool_name, "validated_params": list(parameters.keys())}
        )


class ResourceLimitRail(BaseGuardrail):
    """
    Enforce resource limits on execution.

    Prevents resource exhaustion attacks.
    """

    def __init__(self, config, max_execution_time: Optional[float] = None,
                 max_memory_mb: Optional[int] = None,
                 max_iterations: Optional[int] = None):
        """
        Initialize resource limit rail.

        Args:
            config: Rail configuration
            max_execution_time: Maximum execution time in seconds
            max_memory_mb: Maximum memory usage in MB
            max_iterations: Maximum loop iterations
        """
        super().__init__(config)
        self.max_execution_time = max_execution_time
        self.max_memory_mb = max_memory_mb
        self.max_iterations = max_iterations

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check resource limits."""
        context = context or {}
        warnings = []

        # Check for infinite loops in code
        if isinstance(content, str):
            # Detect while True without break
            if re.search(r'\bwhile\s+True\s*:', content):
                if not re.search(r'\bbreak\b', content):
                    warnings.append("Potential infinite loop detected (while True without break)")

            # Detect large range iterations
            range_match = re.search(r'range\s*\(\s*(\d+)\s*\)', content)
            if range_match and self.max_iterations:
                iterations = int(range_match.group(1))
                if iterations > self.max_iterations:
                    warnings.append(f"Loop iterations ({iterations}) exceed limit ({self.max_iterations})")

        # Check execution time from context
        execution_time = context.get("execution_time")
        if execution_time and self.max_execution_time:
            if execution_time > self.max_execution_time:
                return RailResult(
                    rail_id=self.config.id,
                    rail_type=RailType.EXECUTION,
                    action=RailAction.BLOCK,
                    original_content=content,
                    triggered=True,
                    reason=f"Execution time ({execution_time}s) exceeds limit ({self.max_execution_time}s)",
                    confidence=1.0,
                    metadata={"execution_time": execution_time}
                )

        if warnings:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.EXECUTION,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason="; ".join(warnings),
                confidence=0.7,
                metadata={"warnings": warnings}
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.EXECUTION,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False
        )
