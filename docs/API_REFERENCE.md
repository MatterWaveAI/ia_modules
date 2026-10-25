# IA Modules - API Reference

Quick reference for core classes, functions, and patterns in IA Modules.

## Table of Contents

- [Pipeline System](#pipeline-system)
- [Database System](#database-system)
- [Service Registry](#service-registry)
- [Reliability System](#reliability-system)
- [Plugin System](#plugin-system)

## Pipeline System

### Step

Base class for all pipeline steps.

```python
from ia_modules.pipeline.core import Step

class MyStep(Step):
    def __init__(self, name: str, config: dict = None):
        super().__init__(name, config)

    async def run(self, data: dict) -> dict:
        """
        Execute step logic.

        Args:
            data: Input data from previous steps

        Returns:
            dict: Step output data
        """
        # Access config
        value = self.config.get('key', 'default')

        # Access services
        db = self.services.get('database')

        # Process and return
        return {"result": "value"}
```

**Attributes:**
- `name: str` - Step identifier
- `config: dict` - Step configuration
- `services: ServiceRegistry` - Injected services
- `logger: logging.Logger` - Step logger

**Methods:**
- `async execute(data: dict) -> dict` - Main execution method (override this)
- `set_services(services: ServiceRegistry)` - Inject service registry

### ExecutionContext

Tracks pipeline execution metadata.

```python
from ia_modules.pipeline.core import ExecutionContext

ctx = ExecutionContext(
    execution_id='job-123',
    pipeline_id='my-pipeline',
    user_id='user-456',
    thread_id='thread-789'  # optional
)
```

**Attributes:**
- `execution_id: str` - Unique execution ID
- `pipeline_id: str` - Pipeline identifier
- `user_id: str` - User identifier
- `thread_id: str` - Optional thread/conversation ID

### Pipeline

Graph-based pipeline executor.

```python
from ia_modules.pipeline.core import Pipeline

pipeline = Pipeline(
    steps=[step1, step2, step3],
    services=services,
    structure=pipeline_structure
)

result = await pipeline.run(
    input_data={'key': 'value'},
    execution_context=ctx
)
```

**Methods:**
- `async run(input_data: dict, execution_context: ExecutionContext = None) -> dict`
- `has_flow_definition() -> bool`

### run_pipeline_from_json

Execute pipeline from JSON configuration.

```python
from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.core import ExecutionContext

services = ServiceRegistry()
ctx = ExecutionContext(
    execution_id='job-001',
    pipeline_id='my-pipeline',
    user_id='user-123'
)

result = await run_pipeline_from_json(
    pipeline_file='pipeline.json',
    input_data={'input': 'data'},
    services=services,
    execution_context=ctx,
    working_directory='./steps'  # optional
)
```

**Parameters:**
- `pipeline_file: str` - Path to JSON config
- `input_data: dict` - Initial data
- `services: ServiceRegistry` - Service registry
- `execution_context: ExecutionContext` - Execution context
- `working_directory: str` - Module import directory (optional)
- `websocket_manager` - WebSocket manager (optional, legacy)
- `user_id: int` - User ID (optional, legacy)
- `execution_id: str` - Execution ID (optional, legacy)

**Returns:** `dict` - Pipeline execution result

### Pipeline JSON Structure

```json
{
  "name": "my_pipeline",
  "steps": [
    {
      "id": "step1",
      "module": "my_module.steps",
      "step_class": "MyStep",
      "config": {
        "param": "value"
      }
    }
  ],
  "flow": {
    "start_at": "step1",
    "paths": [
      {
        "from": "step1",
        "to": "step2",
        "condition": {
          "type": "expression",
          "config": {"source": "status", "operator": "equals", "value": "success"}
        }
      }
    ]
  }
}
```

## Database System

### get_database

Factory function for database connections.

```python
from ia_modules.database import get_database

# SQLite (nexusql backend)
db = get_database('sqlite:///app.db')

# PostgreSQL (nexusql backend)
db = get_database('postgresql://user:pass@localhost/db')

# SQLAlchemy backend with pooling
db = get_database(
    'postgresql://user:pass@localhost/db',
    backend='sqlalchemy',
    pool_size=10,
    max_overflow=20
)
```

**Parameters:**
- `database_url: str` - Connection URL
- `backend: str` - 'nexusql' or 'sqlalchemy' (default: 'nexusql')
- `**kwargs` - Backend-specific options (pool_size, etc.)

**Returns:** `DatabaseInterface` - Database adapter

### DatabaseInterface

Abstract interface for database operations.

```python
# Connect only
db.connect()

# Or connect and apply ia_modules' migrations (ia_modules.database.MIGRATIONS_DIR)
await db.initialize()

# Execute query
db.execute("INSERT INTO users VALUES (:id, :name)", {"id": 1, "name": "Alice"})

# Fetch single row
user = db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})

# Fetch all rows
users = db.fetch_all("SELECT * FROM users ORDER BY name", {})

# Disconnect
db.disconnect()
```

**Methods:**
- `connect() -> bool` - Establish connection
- `disconnect()` - Close connection
- `execute(query: str, params: dict) -> list[dict]` - Execute query, returning any rows
- `fetch_one(query: str, params: dict) -> dict` - Get single row
- `fetch_all(query: str, params: dict) -> list[dict]` - Get all rows
- `table_exists(table_name: str) -> bool` - Check for a table
- `async initialize(apply_schema=True, app_migration_paths=None) -> bool` - Connect and run migrations

`fetch_all()` is part of ia_modules' adapters. nexusql's own `DatabaseManager` (0.2.0+) has no `fetch_all()`;
its `execute()` returns the rows as a list of dicts.

### Using Database in Steps

```python
from ia_modules.pipeline.core import Step
from ia_modules.database import get_database

class DatabaseStep(Step):
    async def run(self, data: dict) -> dict:
        # Get from services
        db = self.services.get('database')

        # Query database
        user = db.fetch_one(
            "SELECT * FROM users WHERE id = :id",
            {"id": data.get('user_id')}
        )

        return {"user": user}
```

### Registering Database

```python
from ia_modules.database import get_database
from ia_modules.pipeline.services import ServiceRegistry

db = get_database('sqlite:///app.db')
await db.initialize()  # connects and creates ia_modules' tables

services = ServiceRegistry()
services.register('database', db)
```

## Service Registry

Dependency injection container.

```python
from ia_modules.pipeline.services import ServiceRegistry

services = ServiceRegistry()

# Register services
services.register('database', db_instance)
services.register('http', http_client)
services.register('cache', redis_client)

# Retrieve services
db = services.get('database')
http = services.get('http')

# Check existence
if services.has('database'):
    db = services.get('database')
```

**Methods:**
- `register(name: str, service: Any)` - Register service
- `get(name: str) -> Any` - Get service (returns None if not found)
- `has(name: str) -> bool` - Check if service exists
- `async initialize_all()` - Initialize all services
- `async cleanup_all()` - Cleanup all services

## Reliability System

### ReliabilityMetrics

Track reliability metrics.

```python
from reliability import ReliabilityMetrics

metrics = ReliabilityMetrics()

# Record step
await metrics.record_step(
    agent="processor",
    success=True,
    required_compensation=False,
    required_human=False,
    mode="execute",
    declared_mode="execute"
)

# Record workflow
await metrics.record_workflow(
    workflow_id="wf-001",
    total_steps=10,
    total_retries=2,
    required_compensation=False,
    required_human=False,
    agents_involved=["processor", "validator"]
)

# Get report
report = await metrics.get_report()
print(f"SVR: {report.svr:.2%}")
print(f"CR: {report.cr:.2%}")
print(f"Healthy: {report.is_healthy()}")
```

### CircuitBreaker

Protect against failures.

```python
from reliability import CircuitBreaker, CircuitBreakerConfig

breaker = CircuitBreaker(
    name="api",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout_seconds=60
    )
)

if breaker.can_execute():
    try:
        result = call_api()
        breaker.record_success()
    except Exception:
        breaker.record_failure()
```

### CostTracker

Monitor costs.

```python
from reliability import CostTracker, CostBudget

tracker = CostTracker()
tracker.set_budget(CostBudget("daily", 100.0, 24))

# Record LLM cost
tracker.record_llm_cost(
    agent="assistant",
    prompt_tokens=1000,
    completion_tokens=500,
    model="gpt-4"
)

# Check budget
if tracker.is_within_budget():
    # Proceed
    pass
```

### AnomalyDetector

Detect anomalies.

```python
from reliability import AnomalyDetector, AnomalyThreshold, Severity

detector = AnomalyDetector()
detector.add_threshold(AnomalyThreshold(
    metric_name="error_rate",
    max_value=0.10,
    severity=Severity.HIGH
))

detector.record_value("error_rate", 0.05)

anomalies = detector.detect_anomalies()
```

### ModeEnforcer

Enforce agent modes.

```python
from reliability import ModeEnforcer, AgentMode

enforcer = ModeEnforcer()

# Set modes
enforcer.set_mode("researcher", AgentMode.EXPLORE)  # Read-only
enforcer.set_mode("executor", AgentMode.EXECUTE)    # Can modify
enforcer.set_mode("reviewer", AgentMode.ESCALATE)   # Needs approval

# Check permission
if enforcer.can_execute("researcher", "database_write"):
    # Execute
    pass
```

## Plugin System

### Creating Plugins

```python
from ia_modules.plugins.base import ConditionPlugin, PluginMetadata, PluginType

class MyCondition(ConditionPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_condition",
            version="1.0.0",
            plugin_type=PluginType.CONDITION
        )

    async def evaluate(self, data: dict) -> bool:
        return data.get('value', 0) > 10
```

### Using Plugin Registry

```python
from ia_modules.plugins import get_registry

registry = get_registry()

# Register
registry.register(MyCondition)

# Use
plugin = registry.get("my_condition")
result = await plugin.evaluate({'value': 15})
```

### Plugin Types

- **ConditionPlugin**: `async evaluate(data: dict) -> bool`
- **StepPlugin**: `async execute(data: dict) -> dict`
- **ValidatorPlugin**: `async validate(data: dict) -> tuple[bool, str]`
- **TransformPlugin**: `async transform(data: dict) -> dict`
- **HookPlugin**: Lifecycle event handlers

## Common Patterns

### Complete Pipeline Setup

```python
import asyncio
from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.core import ExecutionContext
from ia_modules.database import get_database

async def main():
    # Setup database
    db = get_database('sqlite:///app.db')
    db.connect()

    # Setup services
    services = ServiceRegistry()
    services.register('database', db)

    # Create execution context
    ctx = ExecutionContext(
        execution_id='job-001',
        pipeline_id='processor',
        user_id='user-123'
    )

    # Run pipeline
    result = await run_pipeline_from_json(
        'pipeline.json',
        input_data={'key': 'value'},
        services=services,
        execution_context=ctx
    )

    print(f"Result: {result}")

    # Cleanup
    db.disconnect()

asyncio.run(main())
```

### Step with Database and Config

```python
from ia_modules.pipeline.core import Step

class ProcessorStep(Step):
    async def run(self, data: dict) -> dict:
        # Get config
        threshold = self.config.get('threshold', 0.5)

        # Get database
        db = self.services.get('database')

        # Process
        value = data.get('input_value')

        if value > threshold:
            # Store result
            db.execute(
                "INSERT INTO results (value, timestamp) VALUES (:val, :ts)",
                {"val": value, "ts": datetime.now()}
            )

            return {"status": "processed", "value": value}
        else:
            return {"status": "skipped", "reason": "below_threshold"}
```

### Error Handling

```python
class SafeStep(Step):
    async def run(self, data: dict) -> dict:
        try:
            result = await self.process(data)
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Step failed: {e}")
            return {"success": False, "error": str(e)}
```

## Documentation

For detailed guides, see:
- [Getting Started](GETTING_STARTED.md) - Quick start
- [Developer Guide](DEVELOPER_GUIDE.md) - In-depth guide
- [Testing Guide](TESTING_GUIDE.md) - Testing patterns
- [Pipeline Architecture](PIPELINE_ARCHITECTURE.md) - Architecture overview
- [Plugin System](PLUGIN_SYSTEM_DOCUMENTATION.md) - Plugin development
- [Reliability Guide](RELIABILITY_USAGE_GUIDE.md) - Reliability features
