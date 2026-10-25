"""
Test configuration and fixtures
"""

import os
from pathlib import Path
import pytest
from nexusql import DatabaseManager, ConnectionConfig, DatabaseType

# Note: sys.path manipulation removed - rely on proper package installation
# Install with: pip install -e .

# Load .env file if available (for LLM API keys and other test config)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, use system environment variables

# Force in-memory database for tests so the showcase app's file-based DB is never touched
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Default env vars for docker-compose.test.yml (only set if not already provided)
_DOCKER_COMPOSE_DEFAULTS = {
    "TEST_POSTGRESQL_URL": "postgresql://testuser:testpass@localhost:15432/ia_modules_test",
    "REDIS_URL": "redis://localhost:16379",
    "PROMETHEUS_URL": "http://localhost:19090",
    "GRAFANA_URL": "http://localhost:13001",
    "OTEL_COLLECTOR_URL": "http://localhost:14318",
    "OTEL_COLLECTOR_ENDPOINT": "http://localhost:14318",
    "JAEGER_URL": "http://localhost:16686",
}
for _key, _val in _DOCKER_COMPOSE_DEFAULTS.items():
    os.environ.setdefault(_key, _val)


# This file can be used to define pytest fixtures that are shared across all tests

# Configure asyncio for pytest
pytest_plugins = [
    "pytest_asyncio",
]

# Database connection configurations for testing
def get_database_configs():
    """
    Get database configurations for testing.

    Environment variables:
    - TEST_POSTGRESQL_URL: PostgreSQL connection URL (e.g., postgresql://user:pass@localhost:5432/testdb)
    - TEST_MYSQL_URL: MySQL connection URL (e.g., mysql://user:pass@localhost:3306/testdb)
    - TEST_MSSQL_URL: MSSQL connection URL (e.g., mssql://user:pass@localhost:1433/testdb)

    If not set, those database types will be skipped in parameterized tests.
    """
    configs = [
        ("sqlite", ConnectionConfig(
            database_type=DatabaseType.SQLITE,
            database_url="sqlite://:memory:"
        ))
    ]

    # PostgreSQL
    postgresql_url = os.environ.get("TEST_POSTGRESQL_URL")
    if postgresql_url:
        configs.append(("postgresql", ConnectionConfig(
            database_type=DatabaseType.POSTGRESQL,
            database_url=postgresql_url
        )))

    # MySQL
    mysql_url = os.environ.get("TEST_MYSQL_URL")
    if mysql_url:
        configs.append(("mysql", ConnectionConfig(
            database_type=DatabaseType.MYSQL,
            database_url=mysql_url
        )))

    # MSSQL
    mssql_url = os.environ.get("TEST_MSSQL_URL")
    if mssql_url:
        configs.append(("mssql", ConnectionConfig(
            database_type=DatabaseType.MSSQL,
            database_url=mssql_url
        )))

    return configs


@pytest.fixture(params=get_database_configs(), ids=lambda x: x[0])
def db_config(request):
    """Parameterized fixture that provides database configs for all available databases"""
    return request.param[1]


@pytest.fixture(params=get_database_configs(), ids=lambda x: x[0])
async def db_manager(request):
    """Parameterized fixture that provides DatabaseManager instances for all available databases"""
    config = request.param[1]
    db = DatabaseManager(config)
    db.connect()

    # Clean up any test tables from previous runs
    test_tables = [
        'test_users', 'test_products', 'test_data', 'test_table', 'test_items', 'test_async',
        'test_booleans', 'test_json', 'test_varchar', 'test_uuid', 'test_timestamps',
        'test_existence', 'test_script', 'test_script1', 'test_script2'
    ]
    for table in test_tables:
        try:
            # CASCADE only works in PostgreSQL
            if config.database_type == DatabaseType.POSTGRESQL:
                db.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
            else:
                db.execute(f'DROP TABLE IF EXISTS {table}')
        except Exception:
            pass

    yield db

    # Cleanup
    db.disconnect()
