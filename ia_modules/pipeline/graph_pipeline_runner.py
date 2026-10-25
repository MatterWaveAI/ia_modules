"""
Generic Graph-Based Pipeline Runner

A comprehensive runner for executing graph-based pipelines with conditional flows,
parallel execution, and advanced routing capabilities.
"""

import asyncio
import json
import sys
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, ConfigDict

from ia_modules.pipeline.core import Pipeline, Step, ExecutionContext
from ia_modules.pipeline.runner import create_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.in_memory_tracker import InMemoryExecutionTracker


class AgentStepWrapper(Step):
    """Wrapper to make agent-style classes compatible with Step interface"""

    def __init__(self, name: str, agent_instance: Any, config: Dict[str, Any]):
        super().__init__(name, config)
        self.agent_instance = agent_instance

    async def run(self, data: Dict[str, Any]) -> Any:
        """Execute the agent and return results in Step-compatible format"""
        # Call the agent's process method
        result = await self.agent_instance.process(data)

        if result.get('success', False):
            return result.get('data', {})
        else:
            raise Exception(f"Agent {self.name} failed: {result.get('error', 'Unknown error')}")


class PipelineStep(BaseModel):
    """Pydantic model for pipeline step configuration"""
    id: str = Field(..., description="Unique identifier for the step")
    name: str = Field(..., description="Display name for the step")
    type: str = Field(default="task", description="Step type")
    step_class: str = Field(..., description="Python class name to instantiate")
    module: str = Field(..., description="Module path containing the step class")
    config: Dict[str, Any] = Field(default_factory=dict, description="Step configuration")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Input validation schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Output validation schema")


class FlowCondition(BaseModel):
    """Pydantic model for flow condition"""
    type: str = Field(default="always", description="Condition type")
    config: Dict[str, Any] = Field(default_factory=dict, description="Condition configuration")


class FlowPath(BaseModel):
    """Pydantic model for flow path"""
    model_config = ConfigDict(populate_by_name=True)
    
    from_step: str = Field(..., alias="from", description="Source step ID")
    to_step: str = Field(..., alias="to", description="Target step ID")
    condition: FlowCondition = Field(default_factory=lambda: FlowCondition(), description="Path condition")


class PipelineFlow(BaseModel):
    """Pydantic model for pipeline flow definition"""
    start_at: str = Field(..., description="Starting step ID")
    paths: List[FlowPath] = Field(default_factory=list, description="Flow paths")


class PipelineConfig(BaseModel):
    """Pydantic model for complete pipeline configuration"""
    name: str = Field(..., description="Pipeline name")
    description: Optional[str] = Field(None, description="Pipeline description")
    version: Optional[str] = Field(None, description="Pipeline version")
    parameters: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(default_factory=list, description="Pipeline parameter schemas")
    steps: List[PipelineStep] = Field(..., description="Pipeline steps")
    flow: PipelineFlow = Field(..., description="Pipeline flow definition")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Input validation schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Output validation schema")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    loop_config: Optional[Dict[str, Any]] = Field(None, description="Loop configuration for iterative pipelines")
    outputs: Optional[Dict[str, Any]] = Field(None, description="Output mappings")

    @field_validator('parameters', mode='before')
    @classmethod
    def normalize_parameters(cls, v):
        """Normalize parameters - accept both list (schema format) and dict (value format)"""
        if isinstance(v, list):
            # A list of parameter schemas ({"name", "schema", "required", "default"})
            # is kept: create_pipeline_from_json reads defaults and required-ness
            # from it. The values still come from input_data at runtime.
            return v
        if isinstance(v, dict):
            # Dict format is already fine
            return v
        return {}

    @field_validator('steps')
    @classmethod
    def validate_step_ids_unique(cls, v):
        """Validate that all step IDs are unique"""
        ids = [step.id for step in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique")
        return v

    @field_validator('flow')
    @classmethod
    def validate_flow_references(cls, v, info):
        """Validate that flow references exist in steps"""
        # Get the steps from the model data using the info parameter
        if info.data and 'steps' in info.data:
            step_ids = {step.id for step in info.data['steps']}
            step_ids.update(['end', 'end_with_success', 'end_with_failure'])

            for path in v.paths:
                if path.from_step not in step_ids:
                    raise ValueError(f"Flow path references unknown step: {path.from_step}")
                if path.to_step not in step_ids:
                    raise ValueError(f"Flow path references unknown step: {path.to_step}")

        return v


class GraphPipelineRunner:
    """Generic runner for graph-based pipelines with advanced features"""

    def __init__(self, services: Optional[ServiceRegistry] = None):
        # Create default in-memory services if none provided
        if services is None:
            services = ServiceRegistry()
            # Register in-memory execution tracker for tests
            services.register('execution_tracker', InMemoryExecutionTracker())
        
        self.services = services
        self.execution_stats = {
            'start_time': None,
            'end_time': None,
            'steps_executed': 0,
            'parallel_executions': 0,
            'routing_decisions': 0
        }

    def _get_central_logger(self):
        """Get the central logging service"""
        if self.services:
            return self.services.get('central_logger')
        return None

    def _log_to_central_service(self, level: str, message: str, step_name: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        """Log a message to the central logging service"""
        logger = self._get_central_logger()
        if logger:
            logger.log(level, message, step_name, data)

    def _log_step_data(self, step_name: str, step_id: str, data_type: str, data: Any):
        """Log step data with selective information to avoid overwhelming logs"""
        if data is None:
            self._log_to_central_service("INFO", f"{step_name} {data_type}: None", step_name=step_id)
            return

        if isinstance(data, dict):
            # Log dictionary keys and types, but not full content for large data
            data_info = {}
            for key, value in data.items():
                if isinstance(value, (list, tuple)) and len(value) > 10:
                    # For large arrays, just log length and type
                    data_info[key] = f"array[{len(value)}] of {type(value[0]).__name__ if value else 'unknown'}"
                elif isinstance(value, (int, float, str, bool)):
                    data_info[key] = value
                else:
                    data_info[key] = f"{type(value).__name__}"

            self._log_to_central_service("INFO", f"{step_name} {data_type}: {data_info}", step_name=step_id, data=data_info)

        elif isinstance(data, (list, tuple)):
            if len(data) > 10:
                self._log_to_central_service("INFO", f"{step_name} {data_type}: array[{len(data)}] of {type(data[0]).__name__ if data else 'unknown'}", step_name=step_id)
            else:
                self._log_to_central_service("INFO", f"{step_name} {data_type}: {data}", step_name=step_id)

        else:
            self._log_to_central_service("INFO", f"{step_name} {data_type}: {data} ({type(data).__name__})", step_name=step_id)

    async def run_pipeline_from_json(
        self,
        pipeline_config: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
        execution_context: Optional[ExecutionContext] = None,
        use_enhanced_features: bool = True
    ) -> Dict[str, Any]:
        """
        Run a graph-based pipeline from JSON configuration dictionary

        Args:
            pipeline_config: Pipeline configuration as dictionary
            input_data: Initial input data for the pipeline
            execution_context: Execution context with execution_id and metadata
            use_enhanced_features: Whether to use enhanced pipeline features

        Returns:
            Pipeline execution results
        """
        # Validate and parse pipeline configuration with Pydantic
        try:
            config = PipelineConfig(**pipeline_config)
        except Exception as e:
            raise ValueError(f"Invalid pipeline configuration: {e}")

        # Validate pipeline structure
        self._validate_pipeline_config(config)

        # Prepare input data
        input_data = input_data or {}

        # Get execution_id from context, or create in-memory one for tests
        if execution_context:
            execution_id = execution_context.execution_id
        else:
            execution_id = str(uuid.uuid4())

        # Log execution start to central service and tracker
        await self._start_execution_logging(config, input_data, execution_id)

        # Create and run pipeline
        try:
            self.execution_stats['start_time'] = datetime.now()

            result = await self._run_standard_pipeline(config, input_data, execution_id, execution_context)

            self.execution_stats['end_time'] = datetime.now()

            # Check if pipeline is waiting for human input (HITL pause)
            if isinstance(result, dict) and result.get('status') == 'waiting_for_human':
                # Don't log as completed - execution is paused
                # Write central logs to database
                await self._write_central_logs_to_database()

                self._log_to_central_service("INFO", "Pipeline paused for human input", data={
                    "execution_stats": self.execution_stats,
                    "interaction_id": result.get('interaction_id'),
                    "waiting_step": result.get('waiting_step')
                })

                return result

            # Log successful execution end to database
            await self._log_execution_end_to_database(execution_id, success=True)

            # Write central logs to database
            await self._write_central_logs_to_database()

            # Log successful execution end
            self._log_to_central_service("SUCCESS", "Pipeline execution completed successfully", data={"execution_stats": self.execution_stats})

            return result

        except Exception as e:
            # Log failed execution end to database
            await self._log_execution_end_to_database(execution_id, success=False, error=str(e))

            # Write central logs to database even on failure
            await self._write_central_logs_to_database()

            # Log failed execution end
            self._log_to_central_service("ERROR", f"Pipeline execution failed: {str(e)}")

            raise

    async def _start_execution_logging(self, config: PipelineConfig, input_data: Dict[str, Any], execution_id: str):
        """Start execution logging with provided execution ID"""
        # Start execution in tracker
        if self.services:
            execution_tracker = self.services.get('execution_tracker')
            if execution_tracker and hasattr(execution_tracker, 'start_execution'):
                try:
                    await execution_tracker.start_execution(
                        pipeline_name=config.name,
                        pipeline_version=config.version,
                        input_data=input_data,
                        execution_id=execution_id
                    )
                except Exception:
                    pass  # If tracker doesn't support it, continue

        # Set execution ID in central logger
        logger = self._get_central_logger()
        if logger and hasattr(logger, 'set_execution_id'):
            logger.set_execution_id(execution_id)

        # Log execution start
        self._log_to_central_service("INFO", f"Starting pipeline execution: {config.name}", data={
            "pipeline_name": config.name,
            "pipeline_version": config.version,
            "step_count": len(config.steps)
        })

    async def _log_execution_end_to_database(self, execution_id: str, success: bool, error: Optional[str] = None):
        """Log pipeline execution end to execution tracker and reliability metrics."""
        if not self.services:
            return

        execution_tracker = self.services.get('execution_tracker')
        if execution_tracker:
            from .execution_tracker import ExecutionStatus
            await execution_tracker.update_execution_status(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
                error_message=error,
            )

        reliability = self.services.get('reliability_metrics')
        if reliability and execution_tracker:
            step_records = await execution_tracker.get_execution_steps(execution_id)
            await reliability.record_workflow(
                workflow_id=execution_id,
                steps=len(step_records),
                retries=sum(s.retry_count for s in step_records),
                success=success,
            )

    async def _write_central_logs_to_database(self):
        """Write central logger logs to database via execution tracker"""
        if self.services:
            execution_tracker = self.services.get('execution_tracker')
            central_logger = self.services.get('central_logger')
            if execution_tracker and central_logger and hasattr(central_logger, 'write_to_database'):
                await central_logger.write_to_database(execution_tracker)

    def _validate_pipeline_config(self, config: PipelineConfig):
        """Validate pipeline configuration structure (already done by Pydantic)"""
        pass

    async def _run_standard_pipeline(self, config: PipelineConfig, input_data: Dict[str, Any], execution_id: str, execution_context: ExecutionContext = None) -> Dict[str, Any]:
        """Run pipeline with execution context"""
        from .core import ExecutionContext

        config_dict = config.model_dump(by_alias=True) if hasattr(config, 'model_dump') else config.dict(by_alias=True)
        pipeline = create_pipeline_from_json(config_dict, self.services, input_data=input_data)

        self._log_to_central_service("INFO", f"Executing pipeline with {len(config.steps)} steps")

        for step in config.steps:
            self._log_to_central_service("INFO", f"Step configured: {step.name} ({step.id})", step_name=step.id, data={
                "step_class": step.step_class,
                "module": step.module,
                "config": step.config
            })

        # Create execution context if not provided, otherwise use provided one
        if not execution_context:
            execution_context = ExecutionContext(
                execution_id=execution_id,
                pipeline_id=getattr(config, 'id', None),
                metadata={"pipeline_version": config.version}
            )

        start_time = datetime.now()
        try:
            result = await pipeline.run(input_data, execution_context)
            end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            # Check if pipeline is waiting for human input (HITL pause)
            if isinstance(result, dict) and result.get('status') == 'waiting_for_human':
                self._log_to_central_service("INFO", f"Pipeline paused for human input at step: {result.get('waiting_step')}", data={
                    "duration_seconds": duration,
                    "steps_executed": len(result.get('steps', [])),
                    "interaction_id": result.get('interaction_id')
                })
                self.execution_stats['steps_executed'] = len(result.get('steps', []))
                return result

            # Normal completion
            self._log_to_central_service("SUCCESS", f"Pipeline completed in {duration:.2f} seconds", data={
                "duration_seconds": duration,
                "steps_executed": len(config.steps)
            })

            self.execution_stats['steps_executed'] = len(config.steps)
            return result

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self._log_to_central_service("ERROR", f"Pipeline failed after {duration:.2f} seconds: {str(e)}")
            raise

    async def run_pipeline_with_real_classes(
        self,
        pipeline_config: Dict[str, Any],
        input_data: Dict[str, Any],
        real_classes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run pipeline with real agent class implementations

        Args:
            pipeline_config: Pipeline configuration as dictionary
            input_data: Initial input data for the pipeline
            real_classes: Dictionary mapping step class names to actual implementations

        Returns:
            Pipeline execution results with real agent processing
        """
        # Validate and parse pipeline configuration
        try:
            config = PipelineConfig(**pipeline_config)
        except Exception as e:
            raise ValueError(f"Invalid pipeline configuration: {e}")

        # Generate execution ID and log execution start
        import uuid
        execution_id = str(uuid.uuid4())
        await self._start_execution_logging(config, input_data, execution_id)

        try:
            self.execution_stats['start_time'] = datetime.now()

            # Create pipeline with real agents
            result = await self._run_pipeline_with_real_agents(config, input_data, real_classes)

            self.execution_stats['end_time'] = datetime.now()

            # Log successful execution
            await self._log_execution_end_to_database(execution_id, success=True)
            await self._write_central_logs_to_database()
            self._log_to_central_service("SUCCESS", "Real agent pipeline execution completed successfully",
                                       data={"execution_stats": self.execution_stats})

            return result

        except Exception as e:
            # Log failed execution
            await self._log_execution_end_to_database(execution_id, success=False, error=str(e))
            await self._write_central_logs_to_database()
            self._log_to_central_service("ERROR", f"Real agent pipeline execution failed: {str(e)}")
            raise

    async def _run_pipeline_with_real_agents(self, config: PipelineConfig, input_data: Dict[str, Any], real_classes: Dict[str, Any]) -> Dict[str, Any]:
        """Execute pipeline with real agent implementations"""

        # Create custom pipeline runner that uses real agents

        # Convert config to format suitable for direct agent execution
        steps = []

        for step_config in config.steps:
            step_class_name = step_config.step_class

            if step_class_name in real_classes:
                # Get the real agent class
                AgentClass = real_classes[step_class_name]

                # Create agent instance based on type
                if hasattr(AgentClass, 'process'):
                    # This is an agent-style class (like DestinationAnalysisAgent)
                    agent_instance = AgentClass(step_config.config)
                    # Wrap it in a Step-compatible interface
                    step = AgentStepWrapper(step_config.id, agent_instance, step_config.config)
                else:
                    # This is a step-style class (like HotelScraperStep)
                    step = AgentClass(step_config.id, step_config.config)

                steps.append(step)

                # Log step creation
                self._log_to_central_service("INFO", f"Created real agent: {step_config.name} ({step_class_name})",
                                           step_name=step_config.id)
            else:
                raise ValueError(f"Real agent class not found: {step_class_name}")

        # Create pipeline with real agents
        # Pipeline expects: (name, steps, flow, services, ...)
        # Use by_alias=True to get "from"/"to" keys instead of "from_step"/"to_step"
        pipeline_structure = config.model_dump(by_alias=True) if hasattr(config, 'model_dump') else config.dict(by_alias=True)
        
        # Get telemetry and checkpointer from services if available
        telemetry = self.services.get('telemetry') if self.services else None
        tracer = self.services.get('tracer') if self.services else None
        checkpointer = self.services.get('checkpointer') if self.services else None
        
        pipeline = Pipeline(
            name=config.name,
            steps=steps,
            flow=pipeline_structure.get('flow', {}),
            services=self.services,
            enable_telemetry=telemetry is not None,
            checkpointer=checkpointer
        )
        
        # Override the pipeline's telemetry with the one from services
        if telemetry:
            pipeline.telemetry = telemetry
        if tracer and hasattr(pipeline, 'tracer'):
            pipeline.tracer = tracer

        # Execute pipeline
        self._log_to_central_service("INFO", f"Executing pipeline with {len(steps)} real agents")

        from ia_modules.pipeline.test_utils import create_test_execution_context
        start_time = datetime.now()
        result = await pipeline.run(input_data, create_test_execution_context())
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        self.execution_stats['steps_executed'] = len(steps)

        self._log_to_central_service("SUCCESS", f"Real agent pipeline completed in {duration:.2f} seconds",
                                   data={"duration_seconds": duration, "steps_executed": len(steps)})

        return result

    async def run_pipeline(
        self,
        name: str,
        steps: List[Step],
        flow: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
        execution_context: Optional[ExecutionContext] = None,
        loop_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a pipeline from pre-built Step instances.

        This is the programmatic equivalent of run_pipeline_from_json —
        same logging, tracking, and stats, but accepts already-instantiated
        steps instead of JSON config.

        Args:
            name: Pipeline name.
            steps: List of Step (or AgentStep) instances.
            flow: Flow dict with ``start_at`` and ``paths``.
            input_data: Initial input data for the pipeline.
            execution_context: Execution context with execution_id etc.
            loop_config: Optional loop configuration for iterative pipelines.

        Returns:
            Pipeline execution results.
        """
        input_data = input_data or {}

        if execution_context:
            execution_id = execution_context.execution_id
        else:
            execution_id = str(uuid.uuid4())
            execution_context = ExecutionContext(
                execution_id=execution_id,
                pipeline_id=name,
            )

        # Minimal PipelineConfig for logging (no module/step_class needed)
        pseudo_steps = [
            PipelineStep(
                id=s.name, name=s.name,
                step_class=type(s).__name__,
                module=type(s).__module__,
                config=getattr(s, "config", {}),
            )
            for s in steps
        ]
        pseudo_config = PipelineConfig(
            name=name,
            steps=pseudo_steps,
            flow=PipelineFlow(
                start_at=flow["start_at"],
                paths=[FlowPath(**p) for p in flow.get("paths", [])],
            ),
        )

        await self._start_execution_logging(pseudo_config, input_data, execution_id)

        try:
            self.execution_stats["start_time"] = datetime.now()

            pipeline = Pipeline(
                name=name,
                steps=steps,
                flow=flow,
                services=self.services,
                loop_config=loop_config,
            )

            start_time = datetime.now()
            result = await pipeline.run(input_data, execution_context)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self.execution_stats["end_time"] = end_time
            self.execution_stats["steps_executed"] = len(steps)

            # HITL pause
            if isinstance(result, dict) and result.get("status") == "waiting_for_human":
                await self._write_central_logs_to_database()
                return result

            await self._log_execution_end_to_database(execution_id, success=True)
            await self._write_central_logs_to_database()
            self._log_to_central_service(
                "SUCCESS",
                f"Pipeline completed in {duration:.2f} seconds",
                data={"duration_seconds": duration, "steps_executed": len(steps)},
            )
            return result

        except Exception as e:
            await self._log_execution_end_to_database(execution_id, success=False, error=str(e))
            await self._write_central_logs_to_database()
            self._log_to_central_service("ERROR", f"Pipeline execution failed: {str(e)}")
            raise

    async def run_with_different_scenarios(
        self,
        pipeline_config: Dict[str, Any],
        scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Run the same pipeline with different input scenarios

        Args:
            pipeline_config: Pipeline configuration as dictionary
            scenarios: List of scenario dictionaries with 'name', 'input_data', and optional 'description'

        Returns:
            List of execution results for each scenario
        """
        results = []

        for scenario in scenarios:
            try:
                result = await self.run_pipeline_from_json(
                    pipeline_config=pipeline_config,
                    input_data=scenario['input_data'],
                    use_enhanced_features=False  # Keep it simple for scenarios
                )

                scenario_result = {
                    'scenario_name': scenario['name'],
                    'success': True,
                    'result': result,
                    'execution_stats': self.execution_stats.copy()
                }

            except Exception as e:
                scenario_result = {
                    'scenario_name': scenario['name'],
                    'success': False,
                    'error': str(e),
                    'execution_stats': self.execution_stats.copy()
                }

            results.append(scenario_result)

        return results


async def run_graph_pipeline(
    pipeline_config: Dict[str, Any],
    input_data: Optional[Dict[str, Any]] = None,
    services: Optional[ServiceRegistry] = None
) -> Dict[str, Any]:
    """
    Convenience function to run a graph-based pipeline

    Args:
        pipeline_config: Pipeline configuration as dictionary
        input_data: Input data for the pipeline
        services: Service registry for dependency injection

    Returns:
        Pipeline execution results
    """
    runner = GraphPipelineRunner(services)
    return await runner.run_pipeline_from_json(pipeline_config, input_data)


async def run_graph_pipeline_from_file(
    pipeline_file: str,
    input_data: Optional[Dict[str, Any]] = None,
    services: Optional[ServiceRegistry] = None
) -> Dict[str, Any]:
    """
    Convenience function to run a graph-based pipeline from file

    Args:
        pipeline_file: Path to JSON pipeline configuration file
        input_data: Input data for the pipeline
        services: Service registry for dependency injection

    Returns:
        Pipeline execution results
    """
    # Load pipeline configuration from file
    json_path = Path(pipeline_file)
    if not json_path.exists():
        raise FileNotFoundError(f"Pipeline configuration file not found: {pipeline_file}")

    with open(json_path, 'r', encoding='utf-8') as f:
        pipeline_config = json.load(f)

    return await run_graph_pipeline(pipeline_config, input_data, services)


# Example usage
async def example_usage():
    """Example of how to use the generic pipeline runner"""

    # Sample pipeline configuration
    pipeline_config = {
        "name": "Example Pipeline",
        "description": "A simple example pipeline",
        "steps": [
            {
                "id": "step1",
                "name": "First Step",
                "step_class": "ExampleStep",
                "module": "my_module.steps",
                "config": {"param": "value"}
            }
        ],
        "flow": {
            "start_at": "step1",
            "paths": [
                {
                    "from": "step1",
                    "to": "end_with_success",
                    "condition": {"type": "always"}
                }
            ]
        }
    }

    # Basic usage with JSON config
    result = await run_graph_pipeline(
        pipeline_config=pipeline_config,
        input_data={"key": "value"}
    )

    # With custom services
    services = ServiceRegistry()
    # Add your services here...

    result = await run_graph_pipeline(
        pipeline_config=pipeline_config,
        input_data={"key": "value"},
        services=services
    )

    return result


if __name__ == "__main__":
    # CLI usage example
    if len(sys.argv) < 2:
        print("Usage: python graph_pipeline_runner.py <pipeline_file> [input_json]")
        print("Example: python graph_pipeline_runner.py pipeline.json '{\"key\": \"value\"}'")
        sys.exit(1)

    pipeline_file = sys.argv[1]
    input_data = {}

    if len(sys.argv) > 2:
        try:
            input_data = json.loads(sys.argv[2])
        except json.JSONDecodeError as e:
            print(f"Error parsing input JSON: {e}")
            sys.exit(1)

    asyncio.run(run_graph_pipeline_from_file(pipeline_file, input_data))
