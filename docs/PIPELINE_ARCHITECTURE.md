# IA Modules - Pipeline System Architecture

## Overview

The IA Modules Pipeline System is a graph-based workflow execution framework designed for building intelligent, modular AI applications. It provides a declarative JSON configuration approach for defining complex workflows with conditional routing, service injection, and human-in-the-loop capabilities.

**ExecutionContext:** The system uses ExecutionContext (containing execution_id, pipeline_id, user_id, thread_id) as a required parameter to `Pipeline.run()`. This replaced the previous pattern of registering execution_id in services.

## Table of Contents

- [Core Architecture](#core-architecture)
- [Pipeline Components](#pipeline-components)
- [JSON Configuration Format](#json-configuration-format)
- [Execution Models](#execution-models)
- [Service Injection System](#service-injection-system)
- [Template Parameter Resolution](#template-parameter-resolution)
- [Conditional Flow Control](#conditional-flow-control)
- [Error Handling & Logging](#error-handling--logging)
- [Human-in-the-Loop Workflows](#human-in-the-loop-workflows)
- [Performance Considerations](#performance-considerations)
- [Best Practices](#best-practices)

## Core Architecture

### Design Principles

1. **Graph-First Design**: All pipelines are directed acyclic graphs (DAGs) ensuring predictable execution flow
2. **Declarative Configuration**: JSON-based pipeline definitions for language-agnostic workflow management
3. **Service Injection**: Clean dependency management through the ServiceRegistry pattern
4. **Template Resolution**: Dynamic parameter substitution using context-aware templating
5. **Conditional Routing**: Intelligent flow control based on step outputs and external conditions

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline System                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │   JSON      │  │  Template   │  │  Service        │   │
│  │ Definition  │→ │ Parameter   │→ │ Registry        │   │
│  │             │  │ Resolver    │  │                 │   │
│  └─────────────┘  └─────────────┘  └─────────────────┘   │
│                           │                              │
│  ┌─────────────────────────▼─────────────────────────┐   │
│  │            Pipeline Orchestrator                  │   │
│  │  ┌─────────────────────────────────────────────┐  │   │
│  │  │            Flow Controller                  │  │   │
│  │  │  ┌───────┐  ┌───────┐  ┌─────────────────┐  │  │   │
│  │  │  │ Step  │→ │ Step  │→ │ Conditional     │  │  │   │
│  │  │  │   A   │  │   B   │  │ Router          │  │  │   │
│  │  │  └───────┘  └───────┘  └─────────────────┘  │  │   │
│  │  └─────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
│                           │                              │
│  ┌─────────────────────────▼─────────────────────────┐   │
│  │              Execution Logger                     │   │
│  │  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │ Step Logger │  │ Database    │                │   │
│  │  │             │  │ Logger      │                │   │
│  │  └─────────────┘  └─────────────┘                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Pipeline Components

### Core Classes

#### Step

The fundamental execution unit in the pipeline system.

**Key Features:**
- Asynchronous execution with `async def run()`
- Service injection through `get_db()` and `get_http()`
- Comprehensive logging and error handling
- WebSocket integration for real-time updates

**Implementation:**

```python
class Step:
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.logger = None
        self.services = None

    async def run(self, data: Dict[str, Any]) -> Any:
        """Override this method in subclasses"""
        return f"result from {self.name}"

    def get_db(self):
        """Access database manager through service injection"""
        if self.services:
            db_service = self.services.get('database')
            return db_service.db_manager if hasattr(db_service, 'db_manager') else db_service
        return None
```

#### Pipeline

The orchestrator that manages step execution and flow control.

**Key Features:**
- Graph-based execution with conditional routing
- Template parameter resolution
- Service registry management
- Comprehensive execution logging

**Flow Execution Algorithm:**

```python
async def _execute_graph(self, data: Dict[str, Any]) -> Dict[str, Any]:
    steps_map = {step.name: step for step in self.steps}
    flow = self.structure.get('flow', {})

    current_step_id = flow.get('start_at')
    current_data = data.copy()
    step_results = {}

    while current_step_id and current_step_id not in ['end', 'end_with_success']:
        # Execute current step
        step = steps_map.get(current_step_id)
        step = self._resolve_step_templates(step, context)

        result_data = await step.run(current_data)
        step_results[current_step_id] = {
            'success': True,
            'result': result_data.get(step.name, {}),
            'output': result_data
        }

        # Find next step based on conditional routing
        current_step_id = self._find_next_step(current_step_id, paths, step_results[current_step_id])
        current_data = result_data

    return current_data
```

#### ServiceRegistry

Dependency injection container for managing shared services.

```python
class ServiceRegistry:
    def __init__(self, **services):
        self.services = services

    def register(self, name: str, service: Any):
        """Register a service"""
        self.services[name] = service

    def get(self, name: str) -> Any:
        """Get a service by name"""
        return self.services.get(name)
```

## JSON Configuration Format

### Pipeline Definition Structure

```json
{
  "name": "Example Pipeline",
  "version": "1.0",
  "description": "Pipeline description",
  "parameters": {
    "topic": "default_topic",
    "enable_processing": true
  },
  "steps": [
    {
      "id": "step_1",
      "name": "Data Processor",
      "step_class": "DataProcessorStep",
      "module": "processing_steps",
      "inputs": {
        "topic": "{{ parameters.topic }}",
        "data": "{{ pipeline_input.raw_data }}"
      },
      "config": {
        "processing_mode": "advanced",
        "timeout": 30
      },
      "outputs": ["processed_data", "metadata"]
    }
  ],
  "flow": {
    "start_at": "step_1",
    "paths": [
      {
        "from": "step_1",
        "to": "step_2",
        "condition": {
          "type": "expression",
          "config": {
            "source": "result.quality_score",
            "operator": "greater_than",
            "value": 0.8
          }
        }
      }
    ]
  },
  "outputs": {
    "final_result": "{{ step_2.processed_output }}",
    "pipeline_metadata": "{{ step_1.metadata }}"
  }
}
```

### Step Configuration

**Required Fields:**
- `id`: Unique step identifier
- `step_class`: Python class name
- `module`: Import path for the step class

**Optional Fields:**
- `name`: Human-readable step name
- `inputs`: Template-based input mapping
- `config`: Static configuration passed to step
- `outputs`: Expected output field names (documentation)

### Flow Definition

**start_at**: Initial step ID
**paths**: Array of transition definitions

**Path Structure:**
```json
{
  "from": "source_step_id",
  "to": "destination_step_id",
  "condition": {
    "type": "expression|always|parameter",
    "config": {
      "source": "result.field_name",
      "operator": "equals|greater_than|less_than",
      "value": "comparison_value"
    }
  }
}
```

## Execution Models

### Graph-Based Execution

The primary execution model uses directed acyclic graphs with conditional routing:

1. **Initialization**: Load JSON configuration and create step instances
2. **Service Injection**: Attach ServiceRegistry to all steps
3. **Template Resolution**: Resolve parameter templates using current context
4. **Step Execution**: Execute current step and capture results
5. **Flow Evaluation**: Determine next step based on conditional routing
6. **Iteration**: Continue until terminal state reached

### Execution Context

The execution context maintains state throughout pipeline execution:

```python
context = {
    'pipeline_input': original_input_data,
    'steps': {
        'step_id': {
            'success': True,
            'result': step_output,
            'output': merged_data
        }
    },
    'parameters': pipeline_parameters
}
```

## Service Injection System

### Database Service Integration

Steps can access database services through clean abstractions:

```python
class DatabaseProcessingStep(Step):
    async def run(self, data: Dict[str, Any]) -> Any:
        db = self.get_db()
        if db:
            # Execute database operations
            result = db.execute("SELECT * FROM my_table WHERE id = :id", {"id": data['id']})
            return {"database_result": result}
        return {"error": "No database service available"}
```

### HTTP Service Integration

HTTP clients are injected for external API calls:

```python
class APIStep(Step):
    async def run(self, data: Dict[str, Any]) -> Any:
        http = self.get_http()
        if http:
            response = await http.get(f"https://api.example.com/data/{data['id']}")
            return {"api_response": response.json()}
        return {"error": "No HTTP service available"}
```

### WebSocket Integration

Real-time updates through WebSocket services:

```python
# Automatic WebSocket notifications during step execution
# Note: execution_id comes from ExecutionContext parameter passed to Pipeline.run()
if self.services:
    websocket_manager = self.services.get('websocket_manager')
    user_id = self.services.get('websocket_user_id')
    # execution_id is from execution_context.execution_id

    if websocket_manager and user_id:
        await websocket_manager.send_processing_status(
            user_id=user_id,
            status="step_completed",
            execution_id=execution_context.execution_id,
            extra_data={"step_name": self.name, "result": result}
        )
```

## Template Parameter Resolution

### Template Syntax

The system supports flexible template parameter resolution:

- `{{ parameters.param_name }}`: Pipeline parameters
- `{{ pipeline_input.field_name }}`: Original input data
- `{{ steps.step_id.result.field }}`: Output from specific step
- `{{ steps.step_id.output.field }}`: Full output data from step

### Resolution Process

1. **Context Building**: Construct resolution context with all available data
2. **Pattern Matching**: Find template patterns using regex `\{([^}]+)\}`
3. **Value Extraction**: Extract values using dot notation path traversal
4. **Type Conversion**: Automatically convert strings to appropriate types
5. **Template Substitution**: Replace templates with resolved values

### Example Resolution

```python
# Configuration with templates
config = {
    "api_url": "https://api.example.com/{{ parameters.endpoint }}",
    "max_results": "{{ parameters.limit }}",
    "filter_score": "{{ steps.analyzer.result.threshold }}"
}

# Context data
context = {
    "parameters": {"endpoint": "search", "limit": "100"},
    "steps": {
        "analyzer": {"result": {"threshold": 0.85}}
    }
}

# Resolved configuration
resolved = {
    "api_url": "https://api.example.com/search",
    "max_results": 100,
    "filter_score": 0.85
}
```

## Conditional Flow Control

### Condition Types

#### Always Condition
```json
{"type": "always"}
```
Always proceeds to the next step.

#### Expression Condition
```json
{
  "type": "expression",
  "config": {
    "source": "result.quality_score",
    "operator": "greater_than",
    "value": 0.8
  }
}
```

**Supported Operators:**
- `equals` / `==`: Exact equality
- `greater_than`: Numeric greater than
- `greater_than_or_equal`: Numeric greater than or equal
- `less_than`: Numeric less than
- `equals_ignore_case`: Case-insensitive string comparison

#### Parameter Condition
```json
{"type": "parameter", "config": {"parameter": "enable_advanced_mode"}}
```
Proceeds if the specified parameter is truthy.

### Flow Evaluation Algorithm

```python
def _find_next_step(self, current_step_id: str, paths: List[Dict], step_output: Dict) -> Optional[str]:
    # Find all outgoing paths from current step
    outgoing_paths = [p for p in paths if p.get('from') == current_step_id]

    # Evaluate conditions in order of definition (priority)
    for path in outgoing_paths:
        condition = path.get('condition', {'type': 'always'})
        if self._evaluate_path_condition(condition, step_output):
            return path.get('to')

    return None  # No valid path found - pipeline ends
```

## Error Handling & Logging

### Multi-Level Logging

The system provides comprehensive logging at multiple levels:

1. **Step-Level Logging**: Individual step execution details
2. **Pipeline-Level Logging**: Overall pipeline execution flow
3. **Database Logging**: Persistent execution records
4. **WebSocket Logging**: Real-time status updates

### StepLogger Implementation

```python
class StepLogger:
    def __init__(self, step_name: str, step_number: int, job_id: str, db_manager=None):
        self.step_name = step_name
        self.step_number = step_number
        self.job_id = job_id
        self.db_manager = db_manager

    async def log_step_start(self, input_data: Dict[str, Any]):
        """Log step initiation with input data summary"""

    async def log_step_complete(self, result: Any):
        """Log successful step completion with results"""

    async def log_step_error(self, error: Exception):
        """Log step failure with error details"""
```

### Error Propagation

Steps can handle errors gracefully:

```python
async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = await self.work(data)
        # Log success and send WebSocket notification
        return merged_result
    except Exception as e:
        # Log error, send WebSocket notification, and re-raise
        if self.logger:
            await self.logger.log_step_error(e)
        raise
```

## Human-in-the-Loop Workflows

### HumanInputStep

Special step type for pausing execution and waiting for human interaction:

```python
class HumanInputStep(Step):
    async def run(self, data: Dict[str, Any]) -> Any:
        ui_schema = self.config.get('ui_schema', {})

        return {
            'human_input_required': True,
            'ui_schema': ui_schema,
            'message': f'Human input step {self.name}'
        }
```

### UI Schema Definition

```json
{
  "id": "human_approval",
  "step_class": "HumanInputStep",
  "config": {
    "ui_schema": {
      "title": "Review Content for Approval",
      "fields": [
        {
          "name": "decision",
          "type": "radio",
          "options": ["Approve", "Reject"]
        },
        {
          "name": "notes",
          "type": "textarea",
          "label": "Reasoning"
        }
      ]
    }
  }
}
```

### HITL Integration Pattern

1. **Step Execution**: Pipeline encounters HumanInputStep
2. **Pause & Persist**: Pipeline state saved to database
3. **UI Generation**: Frontend renders form based on ui_schema
4. **User Interaction**: Human provides required input
5. **Resume Execution**: Pipeline continues with user data

## Performance Considerations

### Async Execution

All step execution is asynchronous, allowing for:
- Concurrent I/O operations
- Non-blocking database queries
- Parallel API calls within steps

### Memory Management

- **Template Resolution**: Creates minimal object copies
- **Step Results**: Stored in efficient dictionaries
- **Context Management**: Cleaned up after pipeline completion

### Database Optimization

- **Connection Pooling**: Managed through ServiceRegistry
- **Batch Logging**: Multiple log entries in single transaction
- **Index Strategy**: Optimized for pipeline execution queries

### Scalability Patterns

**Horizontal Scaling:**
- Multiple pipeline runners on different servers
- Shared database for execution coordination
- WebSocket connection distribution

**Vertical Scaling:**
- Async execution prevents thread blocking
- Memory-efficient step result storage
- Database connection pooling

## Best Practices

### Pipeline Design

1. **Keep Steps Small**: Single responsibility principle
2. **Minimize State**: Steps should be as stateless as possible
3. **Handle Errors Gracefully**: Implement comprehensive error handling
4. **Use Template Parameters**: Dynamic configuration over hardcoding
5. **Document Flow Logic**: Clear condition documentation

### Step Implementation

```python
class WellDesignedStep(Step):
    async def run(self, data: Dict[str, Any]) -> Any:
        # 1. Validate inputs
        required_fields = ['input_field']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Required field missing: {field}")

        # 2. Get services with fallbacks
        db = self.get_db()
        if not db:
            return {"error": "Database service unavailable"}

        # 3. Perform work with error handling
        try:
            result = await self._process_data(data['input_field'])
            return {"processed_result": result, "status": "success"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def _process_data(self, input_field):
        """Private method for actual work"""
        # Implementation details
        pass
```

### Configuration Best Practices

1. **Use Descriptive IDs**: Step IDs should be meaningful
2. **Document Conditions**: Clear condition logic
3. **Provide Defaults**: Sensible default parameters
4. **Version Pipelines**: Use semantic versioning
5. **Test Configurations**: Validate JSON before deployment

### Service Registry Setup

```python
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR
from ia_modules.pipeline.services import ServiceRegistry

# Production setup
database_manager = DatabaseManager(database_url)
await database_manager.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])
services = ServiceRegistry()
services.register('database', database_manager)
services.register('http', http_client)
services.register('websocket_manager', websocket_manager)
services.register('central_logger', central_logger)
services.register('websocket_user_id', user_id)
# Note: execution_id is passed via ExecutionContext, not registered in services

# Development setup with mocks
services = ServiceRegistry()
services.register('database', mock_database)
services.register('http', mock_http_client)
```

This pipeline architecture provides a robust, scalable foundation for building complex AI workflows with intelligent routing, comprehensive logging, and real-time user interaction capabilities.