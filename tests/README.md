# IA Modules Test Suite

Comprehensive testing for the IA Modules pipeline system with multi-database backend support.

## Test Structure

```
tests/
├── unit/                           # Unit tests (fast, isolated)
│   ├── test_core.py               # Core pipeline logic
│   ├── test_database_coverage.py  # Database adapters
│   └── ...
├── integration/                    # Integration tests (real dependencies)
│   ├── test_redis_metric_storage.py
│   └── ...
├── e2e/                           # End-to-end tests (full pipeline)
│   ├── test_comprehensive_e2e.py
│   └── test_sql_pipeline_e2e.py   # See SQL_PIPELINE_E2E_TESTING.md
├── pipelines/                     # Example pipelines used by the tests
├── disaster_recovery/, security/, performance/, observability/
├── conftest.py                    # Shared fixtures
├── docker-compose.test.yml        # Test databases and observability stack
├── .env.example                   # Example environment config
└── README.md                      # This file
```

## Quick Start

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only
pytest tests/e2e/ -v
```

### Run with PostgreSQL, MySQL, Redis
```bash
# 1. Start the test services (PostgreSQL on 15432, MySQL on 13306, Redis on 16379, ...)
docker-compose -f tests/docker-compose.test.yml up -d

# 2. Run all tests
pytest tests/ -v
```

`conftest.py` defaults `TEST_POSTGRESQL_URL` to `postgresql://testuser:testpass@localhost:15432/ia_modules_test`
and `REDIS_URL` to `redis://localhost:16379` (the docker-compose ports) unless you set them yourself.

## Test Categories

### 1. Unit Tests - `tests/unit/`

**Purpose:** Test individual components in isolation

**Characteristics:**
- Fast (< 1 second each)
- No external dependencies
- Use in-memory SQLite
- Mock external services

**Examples:**
- `test_core.py` - Pipeline step execution
- `test_database_coverage.py` - Database operations

**Run:** `pytest tests/unit/ -v`

### 2. Integration Tests - `tests/integration/`

**Purpose:** Test component interactions with real dependencies

**Characteristics:**
- Medium speed (1-5 seconds each)
- May use real databases, file systems, etc.
- Test end-to-end flows within subsystems

**Examples:**
- `test_error_handling_integration.py` - Retry/fallback mechanisms
- `test_importer_integration.py` - Pipeline import system

**Run:** `pytest tests/integration/ -v`

### 3. E2E Tests - `tests/e2e/`

**Purpose:** Test complete pipeline execution from start to finish

**Characteristics:**
- Slower (5-30 seconds each)
- Full system integration
- Test real-world scenarios

**Examples:**
- `test_comprehensive_e2e.py` - Various pipeline types
- `test_parallel_e2e.py` - Parallel execution

**Run:** `pytest tests/e2e/ -v`

## Environment Configuration

### Option 1: Environment Variables

```bash
export TEST_POSTGRESQL_URL="postgresql://user:pass@localhost:5432/ia_modules_test"
export TEST_MYSQL_URL="mysql://user:pass@localhost:3306/ia_modules_test"
export TEST_MSSQL_URL="mssql://user:pass@localhost:1433/ia_modules_test"
export REDIS_URL="redis://localhost:6379"
```

### Option 2: .env File

```bash
cd tests/
cp .env.example .env
# Edit .env with your database URLs
```

`conftest.py` loads `tests/.env` when python-dotenv is installed.

## Test Fixtures

### Shared Fixtures (`conftest.py`)

`db_config` and `db_manager` are parameterized over SQLite (in-memory) plus every database whose
`TEST_*_URL` is set.

**`db_config`** - nexusql `ConnectionConfig` for each configured database
```python
from nexusql import DatabaseManager

def test_something(db_config):
    db = DatabaseManager(db_config)
    # Test runs for each configured database
```

**`db_manager`** - Connected nexusql `DatabaseManager` with test-table cleanup
```python
async def test_something(db_manager):
    # db_manager is already connected
    rows = db_manager.execute("SELECT 1 AS one")  # list of dicts
```

These managers start without ia_modules' tables. Tests that need them call
`await db_manager.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])` with
`from ia_modules.database import MIGRATIONS_DIR`.

## CI/CD Integration

CI runs `.github/workflows/test.yml`; see [docs/TESTING_GUIDE.md](../docs/TESTING_GUIDE.md#continuous-integration)
for its jobs.

## Test Coverage

```bash
# Run with coverage
pytest tests/ --cov=ia_modules --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Running Pipelines via CLI

Run the example pipelines with the `ia-modules` CLI from the repository root:

```bash
# Simple pipeline with topic
ia-modules run tests/pipelines/simple_pipeline/pipeline.json --input input.json --working-dir .

# Save the result instead of printing it
ia-modules run tests/pipelines/simple_pipeline/pipeline.json --input input.json --working-dir . --output result.json
```

`--input` takes a JSON file (for example `{"topic": "artificial intelligence"}`); `--working-dir .` makes the
`tests.pipelines...` step modules importable. See
[docs/CLI_TOOL_DOCUMENTATION.md](../docs/CLI_TOOL_DOCUMENTATION.md) for all options.

## Writing Tests

### Testing with Multiple Databases

Use the parameterized `db_manager` fixture:

```python
async def test_my_feature(db_manager):
    """This test runs on all configured databases"""
    db_manager.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
    # Test logic here
```

### Verifying Data Exists

Don't stop at the write; read the data back:

```python
db.execute("INSERT INTO users (name) VALUES (:name)", {"name": "Alice"})

row = db.fetch_one("SELECT * FROM users WHERE name = :name", {"name": "Alice"})
assert row is not None
assert row["name"] == "Alice"
```

## Common Issues

### PostgreSQL connection errors

`conftest.py` points `TEST_POSTGRESQL_URL` at the docker-compose database by default, so the PostgreSQL
variants of parameterized tests fail when it is not running. Start it with
`docker-compose -f tests/docker-compose.test.yml up -d postgres`, or set `TEST_POSTGRESQL_URL` to your own server.

### Redis errors

**Symptom:**
```
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:16379
```

**This is expected** if Redis is not running. Redis tests are optional.

**Solution (optional):**
```bash
docker-compose -f tests/docker-compose.test.yml up -d redis
```

## Documentation

- **[SQL_PIPELINE_E2E_TESTING.md](e2e/SQL_PIPELINE_E2E_TESTING.md)** - SQL pipeline tests across databases
- **[docs/TESTING_GUIDE.md](../docs/TESTING_GUIDE.md)** - Testing guide
- **[.env.example](.env.example)** - Example environment configuration

## Summary

- **Unit tests** - Fast, isolated, always run
- **Integration tests** - Component interactions
- **E2E tests** - Full pipeline execution

**For development:** Run unit tests
**Before commit:** Run all tests
**Before merge:** Run all tests with the docker-compose databases up
