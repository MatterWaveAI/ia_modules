# IA Modules - Testing Guide

Comprehensive guide for testing pipelines, steps, and database integrations.

## Table of Contents

- [Running Tests](#running-tests)
- [Test Organization](#test-organization)
- [Unit Testing](#unit-testing)
- [Integration Testing](#integration-testing)
- [Database Testing](#database-testing)
- [Pipeline Testing](#pipeline-testing)
- [Test Examples](#test-examples)
- [Best Practices](#best-practices)

## Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_core.py

# Run tests matching pattern
pytest -k "test_pipeline"

# Run with coverage
pytest --cov=ia_modules --cov-report=html
```

### Test Collection

```bash
# Show all collected tests
pytest --collect-only

# Count tests
pytest --collect-only -q | tail -1
```

## Test Organization

```
tests/
├── unit/                       # Unit tests for components
│   ├── test_core.py           # Pipeline core tests
│   ├── test_services.py       # Service registry tests
│   ├── test_database_coverage.py  # Database interface tests
│   └── test_cli_*.py          # CLI command tests
├── integration/                # Integration tests
│   ├── test_pipeline_integration.py
│   └── test_importer_integration.py
├── pipelines/                  # Test pipeline configurations
│   ├── simple_pipeline/
│   ├── conditional_pipeline/
│   ├── parallel_pipeline/
│   └── loop_pipeline/
└── conftest.py                # Shared fixtures

## Unit Testing

### Testing Steps

```python
import pytest
from ia_modules.pipeline.core import Step

class TestGreetingStep(Step):
    async def run(self, data):
        name = data.get('name', 'World')
        return {'message': f'Hello, {name}!'}

@pytest.mark.asyncio
async def test_greeting_step():
    step = TestGreetingStep('greet', {})
    result = await step.execute({'name': 'Alice'})

    assert result['message'] == 'Hello, Alice!'

@pytest.mark.asyncio
async def test_greeting_step_default():
    step = TestGreetingStep('greet', {})
    result = await step.execute({})

    assert result['message'] == 'Hello, World!'
```

### Testing Service Registry

```python
from ia_modules.pipeline.services import ServiceRegistry

def test_service_registration():
    services = ServiceRegistry()

    # Register service
    db_mock = {'type': 'mock_db'}
    services.register('database', db_mock)

    # Retrieve service
    assert services.get('database') == db_mock
    assert services.has('database') is True

def test_service_not_found():
    services = ServiceRegistry()

    assert services.get('nonexistent') is None
    assert services.has('nonexistent') is False
```

### Testing ExecutionContext

```python
from ia_modules.pipeline.core import ExecutionContext

def test_execution_context():
    ctx = ExecutionContext(
        execution_id='exec-123',
        pipeline_id='pipeline-456',
        user_id='user-789'
    )

    assert ctx.execution_id == 'exec-123'
    assert ctx.pipeline_id == 'pipeline-456'
    assert ctx.user_id == 'user-789'
```

## Integration Testing

### Testing Pipeline Execution

```python
import pytest
import json
import tempfile
from pathlib import Path

from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.core import ExecutionContext

@pytest.mark.asyncio
async def test_simple_pipeline_execution():
    # Create pipeline config
    pipeline_config = {
        "name": "test_pipeline",
        "steps": [
            {
                "id": "greet",
                "module": "tests.fixtures.test_steps",
                "step_class": "GreetingStep"
            }
        ],
        "flow": {
            "start_at": "greet",
            "paths": []
        }
    }

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(pipeline_config, f)
        pipeline_file = f.name

    try:
        # Execute pipeline
        services = ServiceRegistry()
        ctx = ExecutionContext(
            execution_id='test-001',
            pipeline_id='test-pipeline',
            user_id='test-user'
        )

        result = await run_pipeline_from_json(
            pipeline_file,
            input_data={'name': 'Test'},
            services=services,
            execution_context=ctx
        )

        # Verify result
        assert 'greet' in result
        assert result['greet']['message'] == 'Hello, Test!'

    finally:
        Path(pipeline_file).unlink()
```

### Testing Conditional Flow

```python
@pytest.mark.asyncio
async def test_conditional_flow():
    pipeline_config = {
        "name": "conditional_test",
        "steps": [
            {
                "id": "validator",
                "module": "tests.fixtures.test_steps",
                "step_class": "ValidationStep"
            },
            {
                "id": "process_valid",
                "module": "tests.fixtures.test_steps",
                "step_class": "ValidProcessorStep"
            },
            {
                "id": "process_invalid",
                "module": "tests.fixtures.test_steps",
                "step_class": "InvalidProcessorStep"
            }
        ],
        "flow": {
            "start_at": "validator",
            "paths": [
                {
                    "from": "validator",
                    "to": "process_valid",
                    "condition": {
                        "type": "expression",
                        "config": {"source": "valid", "operator": "equals", "value": True}
                    }
                },
                {
                    "from": "validator",
                    "to": "process_invalid",
                    "condition": {
                        "type": "expression",
                        "config": {"source": "valid", "operator": "equals", "value": False}
                    }
                }
            ]
        }
    }

    # Test valid path
    result_valid = await execute_pipeline(pipeline_config, {'score': 0.9})
    assert 'process_valid' in result_valid

    # Test invalid path
    result_invalid = await execute_pipeline(pipeline_config, {'score': 0.3})
    assert 'process_invalid' in result_invalid
```

## Database Testing

### Testing with NexusQL

```python
import pytest
from ia_modules.database import get_database

@pytest.fixture
def test_db():
    """Create temporary in-memory database"""
    db = get_database('sqlite:///:memory:', backend='nexusql')
    db.connect()

    # Create test table
    db.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        )
    """, {})

    yield db

    db.disconnect()

def test_database_insert(test_db):
    # Insert data
    test_db.execute(
        "INSERT INTO users (id, name, email) VALUES (:id, :name, :email)",
        {"id": 1, "name": "Alice", "email": "alice@example.com"}
    )

    # Query data
    result = test_db.fetch_one(
        "SELECT * FROM users WHERE id = :id",
        {"id": 1}
    )

    assert result['name'] == 'Alice'
    assert result['email'] == 'alice@example.com'

def test_database_fetch_all(test_db):
    # Insert multiple rows
    for i in range(3):
        test_db.execute(
            "INSERT INTO users (id, name, email) VALUES (:id, :name, :email)",
            {"id": i+1, "name": f"User{i+1}", "email": f"user{i+1}@example.com"}
        )

    # Fetch all
    results = test_db.fetch_all("SELECT * FROM users ORDER BY id", {})

    assert len(results) == 3
    assert results[0]['name'] == 'User1'
    assert results[2]['name'] == 'User3'
```

### Testing with SQLAlchemy Backend

```python
@pytest.fixture
def sqlalchemy_db():
    """Create database with SQLAlchemy backend"""
    db = get_database(
        'sqlite:///:memory:',
        backend='sqlalchemy',
        pool_size=5
    )
    db.connect()

    db.execute("""
        CREATE TABLE test_data (
            id INTEGER PRIMARY KEY,
            value TEXT
        )
    """, {})

    yield db

    db.disconnect()

def test_sqlalchemy_backend(sqlalchemy_db):
    # Test insert
    sqlalchemy_db.execute(
        "INSERT INTO test_data (id, value) VALUES (:id, :value)",
        {"id": 1, "value": "test"}
    )

    # Test fetch
    result = sqlalchemy_db.fetch_one(
        "SELECT * FROM test_data WHERE id = :id",
        {"id": 1}
    )

    assert result['value'] == 'test'
```

### Testing Steps with Database

```python
from ia_modules.pipeline.core import Step
from ia_modules.database import get_database

class DatabaseStep(Step):
    async def run(self, data):
        db = self.services.get('database')
        user_id = data.get('user_id')

        result = db.fetch_one(
            "SELECT * FROM users WHERE id = :id",
            {"id": user_id}
        )

        return {"user": result}

@pytest.mark.asyncio
async def test_database_step(test_db):
    # Insert test data
    test_db.execute(
        "INSERT INTO users (id, name, email) VALUES (:id, :name, :email)",
        {"id": 1, "name": "Bob", "email": "bob@example.com"}
    )

    # Setup services
    from ia_modules.pipeline.services import ServiceRegistry
    services = ServiceRegistry()
    services.register('database', test_db)

    # Create and run step
    step = DatabaseStep('db_step', {})
    step.set_services(services)

    result = await step.execute({'user_id': 1})

    assert result['user']['name'] == 'Bob'
```

## Pipeline Testing

### Test Pipeline Examples

The `tests/pipelines/` directory contains working pipeline examples:

- **simple_pipeline**: Basic linear flow
- **conditional_pipeline**: Conditional routing based on data
- **parallel_pipeline**: Concurrent execution of multiple branches
- **loop_pipeline**: Iterative processing with loops
- **multi_agent_collaboration**: Multi-agent workflows

### Testing Existing Pipelines

```python
import pytest
from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.core import ExecutionContext
from ia_modules.pipeline.services import ServiceRegistry

@pytest.mark.asyncio
async def test_simple_pipeline():
    """Test existing simple pipeline"""
    services = ServiceRegistry()
    ctx = ExecutionContext(
        execution_id='test-simple',
        pipeline_id='simple',
        user_id='tester'
    )

    result = await run_pipeline_from_json(
        'tests/pipelines/simple_pipeline/pipeline.json',
        input_data={'test': 'data'},
        services=services,
        execution_context=ctx
    )

    assert result is not None
```

### Creating Custom Test Pipelines

**tests/my_test/pipeline.json:**
```json
{
  "name": "my_test_pipeline",
  "steps": [
    {
      "id": "step1",
      "module": "tests.my_test.steps",
      "step_class": "Step1"
    },
    {
      "id": "step2",
      "module": "tests.my_test.steps",
      "step_class": "Step2"
    }
  ],
  "flow": {
    "start_at": "step1",
    "paths": [
      {"from": "step1", "to": "step2"}
    ]
  }
}
```

**tests/my_test/steps.py:**
```python
from ia_modules.pipeline.core import Step

class Step1(Step):
    async def run(self, data):
        return {"result": "step1_done", "data": data}

class Step2(Step):
    async def run(self, data):
        prev_result = data.get('result')
        return {"result": "step2_done", "previous": prev_result}
```

## Test Examples

### Pytest Fixtures

```python
# conftest.py
import pytest
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.core import ExecutionContext
from ia_modules.database import get_database

@pytest.fixture
def services():
    """Provide clean ServiceRegistry"""
    return ServiceRegistry()

@pytest.fixture
def execution_context():
    """Provide ExecutionContext"""
    return ExecutionContext(
        execution_id='test-exec',
        pipeline_id='test-pipeline',
        user_id='test-user'
    )

@pytest.fixture
def test_database():
    """Provide in-memory test database"""
    db = get_database('sqlite:///:memory:')
    db.connect()
    yield db
    db.disconnect()

@pytest.fixture
def services_with_db(services, test_database):
    """Provide ServiceRegistry with database"""
    services.register('database', test_database)
    return services
```

### Using Fixtures

```python
def test_with_fixtures(services_with_db, execution_context):
    """Test using pytest fixtures"""
    # Services already has database registered
    db = services_with_db.get('database')
    assert db is not None

    # ExecutionContext is ready
    assert execution_context.execution_id == 'test-exec'
```

## Best Practices

### 1. Use Fixtures for Common Setup

Create reusable fixtures in `conftest.py` for databases, services, and execution contexts.

### 2. Use In-Memory Databases for Speed

```python
db = get_database('sqlite:///:memory:')  # Fast, isolated
```

### 3. Test Isolation

Each test should be independent and not rely on other tests' side effects.

### 4. Use Async Tests Properly

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### 5. Test Both Success and Failure Paths

```python
@pytest.mark.asyncio
async def test_step_success():
    step = MyStep('test', {})
    result = await step.execute({'valid': True})
    assert result['success'] is True

@pytest.mark.asyncio
async def test_step_failure():
    step = MyStep('test', {})
    with pytest.raises(ValueError):
        await step.execute({'valid': False})
```

### 6. Test with Different Backends

```python
@pytest.mark.parametrize("backend", ["nexusql", "sqlalchemy"])
def test_database_backends(backend):
    db = get_database('sqlite:///:memory:', backend=backend)
    db.connect()

    # Test should work with both backends
    db.execute("CREATE TABLE test (id INTEGER)", {})
    db.execute("INSERT INTO test VALUES (:id)", {"id": 1})
    result = db.fetch_one("SELECT * FROM test WHERE id = :id", {"id": 1})

    assert result['id'] == 1
    db.disconnect()
```

### 7. Clean Up Resources

```python
@pytest.fixture
def resource():
    res = create_resource()
    yield res
    res.cleanup()  # Always cleanup
```

### 8. Use Descriptive Test Names

```python
# Good
def test_database_insert_with_duplicate_key_raises_error():
    ...

# Bad
def test_db_error():
    ...
```

## Running Specific Test Categories

```bash
# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run only database tests
pytest -k "database" -v

# Run only async tests
pytest -k "asyncio" -v
```

## Continuous Integration

CI runs in `.github/workflows/test.yml` with the following jobs:

| Job | What it runs | Services |
|-----|-------------|----------|
| **test** | Unit tests (`tests/unit/`) with coverage | Redis |
| **lint** | `ruff check` + `mypy` | — |
| **integration** | PostgreSQL, Redis, SQLite, observability tests | Postgres, MySQL, Redis, Prometheus, OTel Collector, Grafana, Jaeger |
| **showcase-tests** | Showcase app Python tests (`showcase_app/tests/`) | Postgres, Redis |
| **showcase-e2e** | Playwright browser tests (Chromium) | Postgres, Redis |
| **build** | Package build + `twine check` | — |

All jobs use **Python 3.14** on `ubuntu-latest`.

## Documentation

- [Developer Guide](DEVELOPER_GUIDE.md) - API reference and patterns
- [Getting Started](GETTING_STARTED.md) - Quick start guide
- [Migration Guide](MIGRATION.md) - Database migration guide
- [Pipeline Architecture](PIPELINE_ARCHITECTURE.md) - Pipeline design patterns
