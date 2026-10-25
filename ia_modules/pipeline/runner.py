"""
Pipeline Execution Engine

Production-ready pipeline runner with JSON configuration support.
Clean implementation without POC dependencies.
"""

import json
import importlib
from typing import Dict, Any, Optional
from pathlib import Path

from .core import Step, Pipeline, TemplateParameterResolver
from .services import ServiceRegistry


def load_step_class(module_path: str, class_name: str):
    """Dynamically import step class from filesystem (synchronous)"""
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except ImportError as e:
        raise ImportError(f"Cannot import module '{module_path}': {e}")
    except AttributeError as e:
        raise AttributeError(f"Module '{module_path}' has no class '{class_name}': {e}")


async def load_step_class_async(
    module_path: str,
    class_name: str,
    db_provider=None,
    pipeline_id: Optional[str] = None
):
    """Async version that tries database first, then falls back to filesystem

    Args:
        module_path: Python module path (e.g., "tests.pipelines.simple_pipeline.steps.step1")
        class_name: Name of the step class (e.g., "Step1")
        db_provider: Optional database provider for loading from database
        pipeline_id: Optional pipeline ID for loading pipeline-specific version

    Returns:
        Step class ready to be instantiated
    """
    if db_provider:
        from .db_step_loader import DatabaseStepLoader
        loader = DatabaseStepLoader(db_provider)
        return await loader.load_step_class(module_path, class_name, pipeline_id)

    # Fallback to sync filesystem loading
    return load_step_class(module_path, class_name)


def create_step_from_json(step_def: Dict[str, Any], context: Dict[str, Any] = None) -> Step:
    """Create step instance from JSON definition (synchronous, filesystem only)"""
    # Resolve template parameters in step configuration
    resolved_config = step_def.get('config', {})
    if context:
        resolved_config = TemplateParameterResolver.resolve_parameters(resolved_config, context)

    step_class = load_step_class(step_def['module'], step_def.get('step_class', step_def.get('class', '')))
    step_name = step_def.get('id', step_def.get('name', 'Unknown'))
    return step_class(step_name, resolved_config)


async def create_step_from_json_async(
    step_def: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    db_provider=None,
    pipeline_id: Optional[str] = None
) -> Step:
    """Async version of create_step_from_json with database support

    Args:
        step_def: Step definition from pipeline JSON
        context: Context for template parameter resolution
        db_provider: Optional database provider for loading from database
        pipeline_id: Optional pipeline ID for loading pipeline-specific version

    Returns:
        Instantiated Step object
    """
    # Resolve template parameters in step configuration
    resolved_config = step_def.get('config', {})
    if context:
        resolved_config = TemplateParameterResolver.resolve_parameters(resolved_config, context)

    # Use async loader if db_provider available
    step_class = await load_step_class_async(
        step_def['module'],
        step_def.get('step_class', step_def.get('class', '')),
        db_provider,
        pipeline_id
    )

    step_name = step_def.get('id', step_def.get('name', 'Unknown'))
    return step_class(step_name, resolved_config)


def _parameter_values(pipeline_config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """The values templates resolve against: the input, plus schema defaults
    for anything missing. A required parameter with neither is an error here,
    rather than a literal '{{ parameters.x }}' failing deep inside a step."""
    values = dict(input_data)
    schemas = pipeline_config.get('parameters')
    if not isinstance(schemas, list):
        return values

    missing = []
    for schema in schemas:
        if not isinstance(schema, dict) or 'name' not in schema:
            continue
        name = schema['name']
        if name in values:
            continue
        if 'default' in schema:
            values[name] = schema['default']
        elif schema.get('required'):
            missing.append(name)

    if missing:
        raise ValueError(
            f"Pipeline '{pipeline_config.get('name', 'Unknown')}' requires parameters it was not given: "
            + ", ".join(missing)
        )
    return values


def create_pipeline_from_json(pipeline_config: Dict[str, Any], services: Optional[ServiceRegistry] = None, input_data: Optional[Dict[str, Any]] = None) -> Pipeline:
    """Create pipeline from JSON configuration with graph-based execution support"""

    # Prepare context for template resolution. input_data provides the
    # parameter values; pipeline_config['parameters'] may list their schemas,
    # which supply defaults and say which are required.
    context = {
        'parameters': _parameter_values(pipeline_config, input_data or {}),
        'pipeline_input': input_data or {}
    }

    # Create steps with template resolution
    steps = []
    for step_def in pipeline_config['steps']:
        step = create_step_from_json(step_def, context)
        steps.append(step)

    # Extract structure for graph-based execution (if present)
    if 'flow' in pipeline_config:
        {
            'steps': pipeline_config.get('steps', []),
            'flow': pipeline_config['flow'],
            'parameters': pipeline_config.get('parameters', {})
        }

    # Create pipeline
    pipeline_name = pipeline_config.get('name', 'Unknown')
    # Pre-resolve {{ parameters.* }} templates in flow conditions so the runner's
    # _evaluate_condition sees real values (e.g. 0.8) instead of literal strings.
    # Step configs are already resolved above via create_step_from_json(context).
    flow = TemplateParameterResolver.resolve_parameters(
        pipeline_config.get('flow', {}), context
    )
    loop_config = pipeline_config.get('loop_config', None)

    # Require explicit ServiceRegistry - no silent fallback
    if not services:
        raise ValueError("ServiceRegistry is required for pipeline execution. Pass a ServiceRegistry instance to create_pipeline_from_json().")

    # Get checkpointer from services if available
    checkpointer = services.get('checkpointer')

    return Pipeline(
        pipeline_name,
        steps,
        flow,
        services,
        loop_config=loop_config,
        checkpointer=checkpointer
    )


async def run_pipeline_from_json(
    pipeline_file: str,
    input_data: Dict[str, Any] = None,
    services: Optional[ServiceRegistry] = None,
    working_directory: Optional[str] = None,
    execution_context=None,
    # Legacy parameters for backward compatibility
    websocket_manager=None,
    user_id: Optional[int] = None,
    execution_id: str = None
) -> Dict[str, Any]:
    """Main runner function - execute pipeline from JSON configuration

    Args:
        pipeline_file: Path to pipeline JSON file
        input_data: Input data dict for pipeline
        services: ServiceRegistry instance (optional)
        working_directory: Working directory for module imports
        execution_context: ExecutionContext instance (preferred)
        websocket_manager: Legacy websocket manager (deprecated)
        user_id: Legacy user ID (deprecated)
        execution_id: Legacy execution ID (deprecated)

    Returns:
        Pipeline execution result dict
    """
    from .core import ExecutionContext

    # Set working directory for relative module imports
    if working_directory:
        import sys
        if working_directory not in sys.path:
            sys.path.insert(0, working_directory)

    # Load JSON configuration
    json_path = Path(pipeline_file)
    if not json_path.exists():
        raise FileNotFoundError(f"Pipeline configuration file not found: {pipeline_file}")

    with open(json_path, 'r', encoding='utf-8') as f:
        pipeline_config = json.load(f)

    # Ensure input data exists
    if input_data is None:
        input_data = {}

    # Inject WebSocket service if provided
    if services is None:
        services = ServiceRegistry()

    if websocket_manager and user_id and execution_id:
        services.register('websocket_manager', websocket_manager)
        services.register('websocket_user_id', user_id)
        services.register('websocket_execution_id', execution_id)

    # Create execution context if not provided (for backward compatibility)
    if execution_context is None and execution_id:
        execution_context = ExecutionContext(
            execution_id=execution_id,
            pipeline_id=json_path.stem,
            user_id=str(user_id) if user_id else 'unknown'
        )

    # Create and run pipeline with injected services
    pipeline = create_pipeline_from_json(pipeline_config, services, input_data=input_data)
    result = await pipeline.run(input_data, execution_context=execution_context)

    return result
