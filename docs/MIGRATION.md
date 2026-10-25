# Migration Guide: Database Integration

This guide explains the database architecture and how to migrate from direct nexusql usage to the pluggable database system.

## Overview

IA Modules uses a pluggable database architecture with two adapters:
- **nexusql** (default): External SQLAlchemy adapter package
- **sqlalchemy**: Direct SQLAlchemy integration with connection pooling

Both adapters implement the `DatabaseInterface` abstract class, providing a consistent API regardless of backend.

## Database Architecture

### DatabaseInterface (Abstract Class)

All database adapters implement this interface:

```python
from ia_modules.database.interfaces import DatabaseInterface

class DatabaseInterface(ABC):
    def connect() -> bool
    def disconnect()
    async def close()
    def execute(query, params) -> List[Dict]
    async def execute_async(query, params)
    def fetch_one(query, params) -> Optional[Dict]
    def fetch_all(query, params) -> List[Dict]
    def table_exists(table_name) -> bool
    async def execute_script(script) -> QueryResult
    async def initialize(apply_schema=True, app_migration_paths=None) -> bool
```

### Available Adapters

1. **NexuSQLAdapter** (default)
   - Wraps the external `nexusql` package
   - Lightweight, simple API
   - Good for basic use cases

2. **SQLAlchemyAdapter**
   - Direct SQLAlchemy integration
   - Connection pooling support
   - Advanced features (pool_size, max_overflow, etc.)

## Key Changes

### Before: Direct nexusql Import

```python
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR

db = DatabaseManager('sqlite:///app.db')
# nexusql 0.2.0+ no longer creates ia_modules' tables, and has no fetch_all()
await db.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])
```

### After: Using Database Factory

```python
from ia_modules.database import get_database

# Default (nexusql)
db = get_database('sqlite:///app.db')

# Explicit nexusql
db = get_database('sqlite:///app.db', backend='nexusql')

# SQLAlchemy with pooling
db = get_database(
    'postgresql://user:pass@localhost/db',
    backend='sqlalchemy',
    pool_size=10,
    max_overflow=20
)
```

## Choosing a Backend

### When to Use NexusQL (Default)

Use nexusql when:
- You need a simple, straightforward database adapter
- Connection pooling is not critical
- You're already using the nexusql package elsewhere
- You want minimal dependencies

**Example:**
```python
from ia_modules.database import get_database

db = get_database('sqlite:///app.db')
# or
db = get_database('postgresql://localhost/db', backend='nexusql')
```

### When to Use SQLAlchemy

Use SQLAlchemy when:
- You need connection pooling for high-traffic applications
- You want fine-grained control over database connections
- You're using advanced SQLAlchemy features
- You need performance optimization for production

**Example:**
```python
from ia_modules.database import get_database

db = get_database(
    'postgresql://user:pass@localhost/production_db',
    backend='sqlalchemy',
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600
)
```

## Setting Default Backend

### Using Environment Variable

```bash
export IA_DATABASE_BACKEND=sqlalchemy
```

Then in code:
```python
from ia_modules.database import get_database

# Uses sqlalchemy backend from environment
db = get_database('postgresql://localhost/db')
```

### Using set_default_backend()

```python
from ia_modules.database import set_default_backend, DatabaseBackend

# Set globally for your application
set_default_backend(DatabaseBackend.SQLALCHEMY)

# All future get_database() calls use SQLAlchemy
db = get_database('postgresql://localhost/db')
```

## Migration Examples

### Migrating Pipeline Steps

**Before:**
```python
from nexusql import DatabaseManager

class MyStep(Step):
    async def run(self, data):
        db = DatabaseManager('sqlite:///app.db')
        result = db.fetch_one("SELECT * FROM users WHERE id = ?", (1,))
        return {"user": result}
```

**After:**
```python
from ia_modules.database import get_database

class MyStep(Step):
    async def run(self, data):
        # Get from services (preferred)
        db = self.services.get('database')
        # or create inline
        db = get_database('sqlite:///app.db')

        result = db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
        return {"user": result}
```

### Migrating Service Registration

**Before:**
```python
from nexusql import DatabaseManager
from ia_modules.pipeline.services import ServiceRegistry

db = DatabaseManager('sqlite:///app.db')
services = ServiceRegistry()
services.register('database', db)
```

**After:**
```python
from ia_modules.database import get_database
from ia_modules.pipeline.services import ServiceRegistry

db = get_database('sqlite:///app.db')
services = ServiceRegistry()
services.register('database', db)
```

Both adapters implement `DatabaseInterface`, so services work identically.

## Supported Databases

Both adapters support the same database types:
- **SQLite**: `sqlite:///path/to/db.sqlite` or `sqlite:///:memory:`
- **PostgreSQL**: `postgresql://user:pass@host:port/database`
- **MySQL**: `mysql://user:pass@host:port/database`
- **DuckDB**: `duckdb:///path/to/db.duckdb` (via nexusql)

## Parameter Binding Differences

### NexusQL: Positional Parameters

```python
db = get_database('sqlite:///app.db', backend='nexusql')

# Uses ? placeholders
result = db.fetch_one("SELECT * FROM users WHERE id = ?", (1,))

# Or dictionary (converted internally)
result = db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
```

### SQLAlchemy: Named Parameters

```python
db = get_database('sqlite:///app.db', backend='sqlalchemy')

# Uses :name placeholders (preferred)
result = db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
```

**Recommendation:** Use named parameters (`:name`) for compatibility with both backends.

## Testing Your Setup

### Test NexusQL Backend

```python
from ia_modules.database import get_database

db = get_database('sqlite:///:memory:', backend='nexusql')
db.connect()

# Create table
db.execute("CREATE TABLE test (id INTEGER, name TEXT)", {})

# Insert data
db.execute("INSERT INTO test VALUES (:id, :name)", {"id": 1, "name": "Test"})

# Query data
result = db.fetch_one("SELECT * FROM test WHERE id = :id", {"id": 1})
print(f"Result: {result}")  # {'id': 1, 'name': 'Test'}

db.disconnect()
```

### Test SQLAlchemy Backend

```python
from ia_modules.database import get_database

db = get_database(
    'sqlite:///:memory:',
    backend='sqlalchemy',
    pool_size=5
)
db.connect()

# Same API as nexusql
db.execute("CREATE TABLE test (id INTEGER, name TEXT)", {})
db.execute("INSERT INTO test VALUES (:id, :name)", {"id": 1, "name": "Test"})
result = db.fetch_one("SELECT * FROM test WHERE id = :id", {"id": 1})
print(f"Result: {result}")

db.disconnect()
```

## Common Migration Issues

### Issue: Import Error

**Problem:**
```python
ModuleNotFoundError: No module named 'nexusql'
```

**Solution:**
```bash
pip install "nexusql>=0.4.0"
```

### Issue: Parameter Binding Error

**Problem:**
```python
# This fails with SQLAlchemy
db.fetch_one("SELECT * FROM users WHERE id = ?", (1,))
```

**Solution:**
Use named parameters:
```python
db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
```

### Issue: Connection Pooling Not Working

**Problem:**
Connection pooling features not available with nexusql.

**Solution:**
Switch to SQLAlchemy backend:
```python
db = get_database(
    'postgresql://localhost/db',
    backend='sqlalchemy',
    pool_size=10
)
```

## Summary

**Key Points:**
- ✅ Pluggable architecture with `DatabaseInterface`
- ✅ Two backends: nexusql (simple) and sqlalchemy (advanced)
- ✅ Consistent API regardless of backend
- ✅ Use named parameters for compatibility
- ✅ Switch backends via environment variable or function parameter

**Recommended Actions:**
1. Use `get_database()` instead of direct imports
2. Use named parameters (`:name`) in all SQL queries
3. Choose nexusql for simplicity, SQLAlchemy for production with pooling
4. Register database in ServiceRegistry for pipeline steps

**Documentation:**
- [Developer Guide](DEVELOPER_GUIDE.md) - Full API reference
- [Getting Started](GETTING_STARTED.md) - Quick start examples
- [Testing Guide](TESTING_GUIDE.md) - Testing with databases
