"""
Pipeline Validation

Comprehensive validation for pipeline definitions including:
- JSON schema validation
- Step import checking
- Flow validation (reachability, cycles)
- Template validation
- Loop detection and analysis
"""

import importlib
import re
from typing import Dict, Any, List, Set, Tuple
from dataclasses import dataclass, field

# Import loop detection
try:
    from ia_modules.pipeline.loop_detector import LoopDetector
    HAS_LOOP_DETECTOR = True
except ImportError:
    HAS_LOOP_DETECTOR = False


@dataclass
class ValidationResult:
    """Result of pipeline validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message"""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Add an info message"""
        self.info.append(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output"""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }


class PipelineValidator:
    """Validates pipeline definitions"""

    def __init__(self, pipeline_data: Dict[str, Any], strict: bool = False):
        self.pipeline_data = pipeline_data
        self.strict = strict
        self.result = ValidationResult(is_valid=True)

    def validate(self) -> ValidationResult:
        """Run all validation checks"""
        self._validate_structure()
        self._validate_steps()
        self._validate_flow()
        self._validate_templates()

        # In strict mode, warnings become errors
        if self.strict and self.result.warnings:
            for warning in self.result.warnings:
                self.result.add_error(f"[STRICT] {warning}")
            self.result.warnings.clear()

        return self.result

    def _validate_structure(self) -> None:
        """Validate basic pipeline structure"""
        # Check required top-level fields
        required_fields = ['name', 'steps', 'flow']
        for req_field in required_fields:
            if req_field not in self.pipeline_data:
                self.result.add_error(f"Missing required field: '{req_field}'")

        # Validate name
        if 'name' in self.pipeline_data:
            name = self.pipeline_data['name']
            if not isinstance(name, str):
                self.result.add_error(f"Pipeline 'name' must be a string, got {type(name).__name__}")
            elif not name.strip():
                self.result.add_error("Pipeline 'name' cannot be empty")

        # Validate steps is a list
        if 'steps' in self.pipeline_data:
            steps = self.pipeline_data['steps']
            if not isinstance(steps, list):
                self.result.add_error(f"'steps' must be a list, got {type(steps).__name__}")
            elif len(steps) == 0:
                self.result.add_warning("Pipeline has no steps defined")

        # Validate flow is a dict
        if 'flow' in self.pipeline_data:
            flow = self.pipeline_data['flow']
            if not isinstance(flow, dict):
                self.result.add_error(f"'flow' must be an object, got {type(flow).__name__}")

    def _validate_steps(self) -> None:
        """Validate step definitions"""
        if 'steps' not in self.pipeline_data or not isinstance(self.pipeline_data['steps'], list):
            return

        step_names = set()
        for i, step in enumerate(self.pipeline_data['steps']):
            if not isinstance(step, dict):
                self.result.add_error(f"Step at index {i} must be an object")
                continue

            # Check required step fields
            if 'name' not in step:
                self.result.add_error(f"Step at index {i} is missing 'name' field")
                continue

            # The flow refers to a step by its 'id'; 'name' is a display label.
            # A step without an 'id' is referred to by its name.
            step_name = _step_identity(step)

            # Check for duplicate step names
            if step_name in step_names:
                self.result.add_error(f"Duplicate step name: '{step_name}'")
            step_names.add(step_name)

            # Validate step name format
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', step_name):
                self.result.add_warning(
                    f"Step name '{step_name}' should follow Python identifier naming convention"
                )

            # Check module field
            if 'module' not in step:
                self.result.add_error(f"Step '{step_name}' is missing 'module' field")
            else:
                self._validate_step_import(step_name, step['module'])

            # The runner reads 'step_class'; 'class' is the older spelling
            if 'step_class' not in step and 'class' not in step:
                self.result.add_error(f"Step '{step_name}' is missing 'class' field ('step_class')")

            # Validate config
            if 'config' in step and not isinstance(step['config'], dict):
                self.result.add_error(f"Step '{step_name}' config must be an object")

            # Validate inputs
            if 'inputs' in step:
                self._validate_step_inputs(step_name, step['inputs'])

    def _validate_step_import(self, step_name: str, module_path: str) -> None:
        """Check if step module can be imported"""
        try:
            importlib.import_module(module_path)
            self.result.add_info(f"Step '{step_name}' module '{module_path}' is importable")
        except ImportError as e:
            self.result.add_error(
                f"Step '{step_name}' module '{module_path}' cannot be imported: {e}"
            )
        except Exception as e:
            self.result.add_warning(
                f"Step '{step_name}' module '{module_path}' import check failed: {e}"
            )

    def _validate_step_inputs(self, step_name: str, inputs: Any) -> None:
        """Validate step input definitions"""
        if not isinstance(inputs, list):
            # The runner does not read step inputs, so an odd shape cannot break a
            # run; the documented form is a list of {"name", "source"} entries.
            self.result.add_warning(
                f"Step '{step_name}' inputs should be a list of {{name, source}} entries, "
                f"got {type(inputs).__name__}"
            )
            return

        for i, inp in enumerate(inputs):
            if not isinstance(inp, dict):
                self.result.add_error(f"Step '{step_name}' input at index {i} must be an object")
                continue

            if 'name' not in inp:
                self.result.add_error(f"Step '{step_name}' input at index {i} is missing 'name'")

            if 'source' not in inp:
                self.result.add_error(f"Step '{step_name}' input at index {i} is missing 'source'")

    def _validate_flow(self) -> None:
        """Validate flow definition and check for issues"""
        if 'flow' not in self.pipeline_data or not isinstance(self.pipeline_data['flow'], dict):
            return

        flow = self.pipeline_data['flow']

        # Check for start_at
        if 'start_at' not in flow:
            self.result.add_error("Flow is missing 'start_at' field")
            return

        start_step = flow['start_at']

        # Validate start step exists
        step_names = self._get_step_names()
        if start_step not in step_names:
            self.result.add_error(f"Start step '{start_step}' is not defined in steps")

        # Validate paths/transitions
        if 'paths' in flow:
            self._validate_paths(flow['paths'], step_names)
        elif 'transitions' in flow:
            self._validate_transitions(flow['transitions'], step_names)
        else:
            self.result.add_warning("Flow has no 'paths' or 'transitions' defined")

        # Check for unreachable steps
        reachable = self._find_reachable_steps(start_step, flow)
        unreachable = step_names - reachable
        if unreachable:
            self.result.add_warning(
                f"Unreachable steps: {', '.join(sorted(unreachable))}"
            )

        # Check for cycles using new LoopDetector if available
        if HAS_LOOP_DETECTOR and 'transitions' in flow:
            self._validate_loops_advanced(flow)
        else:
            # Fallback to simple cycle detection
            cycles = self._find_cycles(flow)
            if cycles:
                self.result.add_warning(
                    f"Flow contains cycles: {' -> '.join(cycles)}"
                )

    def _validate_paths(self, paths: Any, step_names: Set[str]) -> None:
        """Validate flow paths"""
        if not isinstance(paths, list):
            self.result.add_error("Flow 'paths' must be a list")
            return

        for i, path in enumerate(paths):
            if not isinstance(path, dict):
                self.result.add_error(f"Path at index {i} must be an object")
                continue

            # A path may spell its ends from/to (the documented form) or
            # from_step/to_step; the runner accepts both, so validate both.
            for key in ('from', 'from_step'):
                if key in path:
                    from_step = path[key]
                    if from_step not in step_names and not from_step.startswith('end_'):
                        self.result.add_error(
                            f"Path {i}: '{key}' '{from_step}' is not defined"
                        )

            for key in ('to', 'to_step'):
                if key in path:
                    to_step = path[key]
                    if to_step not in step_names and not to_step.startswith('end_'):
                        self.result.add_error(
                            f"Path {i}: '{key}' '{to_step}' is not defined"
                        )

            # Validate condition if present
            if 'condition' in path:
                self._validate_condition(path['condition'], f"Path {i}")

    def _validate_transitions(self, transitions: Any, step_names: Set[str]) -> None:
        """Validate flow transitions (graph-based flow)"""
        if not isinstance(transitions, list):
            self.result.add_error("Flow 'transitions' must be a list")
            return

        for i, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                self.result.add_error(f"Transition at index {i} must be an object")
                continue

            # Validate from
            if 'from' in transition:
                from_step = transition['from']
                if from_step not in step_names:
                    self.result.add_error(
                        f"Transition {i}: 'from' step '{from_step}' is not defined"
                    )

            # Validate to
            if 'to' in transition:
                to_step = transition['to']
                if to_step not in step_names and not to_step.startswith('end_'):
                    self.result.add_error(
                        f"Transition {i}: 'to' step '{to_step}' is not defined"
                    )

            # Validate condition if present
            if 'condition' in transition:
                self._validate_condition(transition['condition'], f"Transition {i}")

    def _validate_condition(self, condition: Any, context: str) -> None:
        """Validate condition definition"""
        if not isinstance(condition, dict):
            self.result.add_error(f"{context}: condition must be an object")
            return

        if 'type' not in condition:
            self.result.add_error(f"{context}: condition is missing 'type' field")
            return

        condition_type = condition['type']

        # The runner evaluates exactly two kinds; a path with any other type
        # never matches, a silent dead branch rather than an error.
        if condition_type == 'always':
            return
        if condition_type != 'expression':
            self.result.add_warning(
                f"{context}: unknown condition type '{condition_type}'; the runner evaluates "
                f"'always' and 'expression' only, so this path can never be taken"
            )
            return

        config = condition.get('config')
        if not isinstance(config, dict):
            self.result.add_error(f"{context}: an 'expression' condition needs a 'config' object")
            return
        if not isinstance(config.get('source'), str) or not config['source']:
            self.result.add_error(
                f"{context}: expression config is missing 'source' (a dotted path into the step data)"
            )
        operator = config.get('operator', 'equals')
        if operator not in EXPRESSION_OPERATORS:
            self.result.add_error(
                f"{context}: unknown expression operator '{operator}'. "
                f"Known operators: {', '.join(EXPRESSION_OPERATORS)}"
            )
        if 'value' not in config:
            self.result.add_warning(f"{context}: expression config has no 'value'; it compares against None")

    def _validate_templates(self) -> None:
        """Validate template references"""
        # Check parameters section
        # The runner accepts parameters as a mapping of values or as a list of
        # schemas ({"name": ..., "schema": ...}); either defines the names.
        defined_params: Set[str] = set()
        if 'parameters' in self.pipeline_data:
            params = self.pipeline_data['parameters']
            if isinstance(params, dict):
                defined_params = set(params.keys())
            elif isinstance(params, list) and all(isinstance(p, dict) and 'name' in p for p in params):
                defined_params = {p['name'] for p in params}
            else:
                self.result.add_error("'parameters' must be an object or a list of parameter schemas")
                # Can't validate template refs if parameters is invalid
                return

        # Find all template references in the pipeline
        template_refs = self._find_template_references(self.pipeline_data)

        # Check if referenced parameters exist
        step_names = self._get_step_names()

        for ref_type, ref_name in template_refs:
            if ref_type == 'parameter' and ref_name not in defined_params:
                self.result.add_warning(
                    f"Template references undefined parameter: '{ref_name}'"
                )
            elif ref_type == 'step' and ref_name not in step_names:
                self.result.add_error(
                    f"Template references undefined step: '{ref_name}'"
                )

    def _find_template_references(self, obj: Any) -> List[Tuple[str, str]]:
        """Find all template references like {{ parameters.x }} or {{ steps.y.output }}"""
        refs = []

        if isinstance(obj, dict):
            for value in obj.values():
                refs.extend(self._find_template_references(value))
        elif isinstance(obj, list):
            for item in obj:
                refs.extend(self._find_template_references(item))
        elif isinstance(obj, str):
            # Find {{ ... }} patterns
            matches = re.findall(r'\{\{\s*([^}]+)\s*\}\}', obj)
            for match in matches:
                parts = match.strip().split('.')
                if len(parts) >= 2:
                    if parts[0] == 'parameters':
                        refs.append(('parameter', parts[1]))
                    elif parts[0] == 'steps':
                        refs.append(('step', parts[1]))

        return refs

    def _get_step_names(self) -> Set[str]:
        """Get all defined step names"""
        if 'steps' not in self.pipeline_data or not isinstance(self.pipeline_data['steps'], list):
            return set()

        return {
            _step_identity(step)
            for step in self.pipeline_data['steps']
            if isinstance(step, dict) and ('id' in step or 'name' in step)
        }

    def _find_reachable_steps(self, start: str, flow: Dict[str, Any]) -> Set[str]:
        """Find all steps reachable from start step"""
        reachable = {start}
        to_visit = [start]

        # Build adjacency list
        adjacency: dict[str, list[str]] = {}
        if 'paths' in flow:
            for path in flow.get('paths', []):
                from_step = path.get('from', path.get('from_step'))
                to_step = path.get('to', path.get('to_step'))
                if from_step and to_step and not to_step.startswith('end_'):
                    if from_step not in adjacency:
                        adjacency[from_step] = []
                    adjacency[from_step].append(to_step)
        elif 'transitions' in flow:
            for transition in flow.get('transitions', []):
                from_step = transition.get('from')
                to_step = transition.get('to')
                if from_step and to_step and not to_step.startswith('end_'):
                    if from_step not in adjacency:
                        adjacency[from_step] = []
                    adjacency[from_step].append(to_step)

        # BFS to find reachable steps
        while to_visit:
            current = to_visit.pop(0)
            for next_step in adjacency.get(current, []):
                if next_step not in reachable:
                    reachable.add(next_step)
                    to_visit.append(next_step)

        return reachable

    def _find_cycles(self, flow: Dict[str, Any]) -> List[str]:
        """Detect cycles in flow graph"""
        # Build adjacency list
        adjacency: dict[str, list[str]] = {}
        if 'paths' in flow:
            for path in flow.get('paths', []):
                from_step = path.get('from', path.get('from_step'))
                to_step = path.get('to', path.get('to_step'))
                if from_step and to_step and not to_step.startswith('end_'):
                    if from_step not in adjacency:
                        adjacency[from_step] = []
                    adjacency[from_step].append(to_step)
        elif 'transitions' in flow:
            for transition in flow.get('transitions', []):
                from_step = transition.get('from')
                to_step = transition.get('to')
                if from_step and to_step and not to_step.startswith('end_'):
                    if from_step not in adjacency:
                        adjacency[from_step] = []
                    adjacency[from_step].append(to_step)

        # DFS to detect cycles
        visited = set()
        rec_stack = set()
        cycle_path = []

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle_path.extend(path[cycle_start:] + [neighbor])
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        # Check all nodes for cycles
        for node in adjacency.keys():
            if node not in visited:
                if dfs(node, []):
                    return cycle_path

        return []

    def _validate_loops_advanced(self, flow: Dict[str, Any]) -> None:
        """Validate loops using advanced LoopDetector"""
        try:
            detector = LoopDetector(flow)
            loops = detector.detect_loops()

            if loops:
                # Inform about detected loops
                self.result.add_info(
                    f"Detected {len(loops)} loop(s) in pipeline (cyclic execution)"
                )

                # Validate loops for safety
                loop_errors = detector.validate_loops()

                if loop_errors:
                    for error in loop_errors:
                        # Critical errors about infinite loops
                        if 'infinite loop' in error.lower():
                            self.result.add_error(f"Loop validation: {error}")
                        else:
                            self.result.add_warning(f"Loop validation: {error}")

                # Add details about each loop
                for i, loop in enumerate(loops, 1):
                    loop_desc = ' -> '.join(loop.steps) + f' -> {loop.steps[0]}'
                    self.result.add_info(f"Loop {i}: {loop_desc}")

                    if loop.exit_conditions:
                        self.result.add_info(
                            f"  Exit conditions: {len(loop.exit_conditions)}"
                        )
                    else:
                        self.result.add_warning(
                            f"  Loop {i} has no exit conditions - check 'loop_config'"
                        )

                # Suggest loop_config
                if 'loop_config' not in self.pipeline_data:
                    self.result.add_info(
                        "Consider adding 'loop_config' to set max_iterations and timeout"
                    )

        except Exception as e:
            # Fallback to simple cycle detection if advanced fails
            self.result.add_warning(f"Advanced loop detection failed: {e}")


# The operators Pipeline._evaluate_condition implements for 'expression' conditions
EXPRESSION_OPERATORS = (
    'equals', 'not_equals', 'greater_than', 'greater_than_or_equals', 'less_than', 'less_than_or_equals'
)


def _step_identity(step: Dict[str, Any]) -> str:
    """The name the flow refers to a step by: its 'id', or its 'name' when it has no id."""
    return step.get('id') or step.get('name')


def validate_pipeline(
    pipeline_data: Dict[str, Any],
    strict: bool = False
) -> ValidationResult:
    """
    Validate a pipeline definition

    Args:
        pipeline_data: Pipeline JSON data
        strict: If True, warnings are treated as errors

    Returns:
        ValidationResult with validation status and messages
    """
    validator = PipelineValidator(pipeline_data, strict=strict)
    return validator.validate()
