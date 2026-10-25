# SQL Pipeline End-to-End Testing Guide

## Overview

The `test_sql_pipeline_e2e.py` file contains comprehensive end-to-end tests that verify data persistence and retrieval across all supported database backends. These tests ensure that the entire pipeline system works correctly with real database operations, not just in-memory mocks.

## Supported Databases

All tests run against **4 database backends**:
- **SQLite** - In-memory and file-based
- **PostgreSQL** - Production-grade RDBMS
- **MySQL** - Popular open-source database
- **MSSQL** - Microsoft SQL Server

Each test is parameterized to run on all 4 databases, ensuring cross-database compatibility.

## Test Architecture

### Database Initialization

```python
@pytest.fixture
async def initialized_db(db_config):
    """Fixture that provides an initialized database with schema"""
    db = DatabaseManager(db_config)
    
    # Initialize with migrations
    await db.initialize(apply_schema=True, app_migration_paths=None)
    
    yield db
    
    # Cleanup
    db.disconnect()
```

**How it works:**
1. Creates a `DatabaseManager` instance for each database type
2. Runs all migrations to set up the complete schema
3. Provides the initialized database to each test
4. Automatically cleans up after the test completes

### Test Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Test starts with initialized_db fixture                 │
│     - Database schema is created via migrations             │
│     - Connection is established                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Test creates and inserts test data                      │
│     - Uses real SQL INSERT statements                       │
│     - Data is committed to the database                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Test queries the database                               │
│     - Uses real SQL SELECT statements                       │
│     - Verifies data was saved correctly                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Test performs assertions                                │
│     - Verifies correct data retrieval                       │
│     - Checks data integrity                                 │
│     - Validates business logic                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Test cleanup (finally block)                            │
│     - Deletes test data                                     │
│     - Leaves database in clean state                        │
└─────────────────────────────────────────────────────────────┘
```

## Test Suites

### 1. TestPipelineLifecycle

**Purpose:** Test complete pipeline execution from creation to completion.

**What it tests:**
- Creating a pipeline record in the database
- Starting a pipeline execution
- Recording multiple step executions
- Updating execution status
- Adding execution logs
- Querying execution history

**Real-world scenario:**
```
User creates pipeline → Executes it → Steps run → Logs recorded → Completion tracked
```

**Database tables used:**
- `pipelines`
- `pipeline_executions`
- `step_executions`
- `execution_logs`

**Key assertions:**
- Pipeline is created with correct metadata
- Execution status transitions properly (running → completed)
- All steps are recorded in order
- Logs are associated with correct execution

**Database-specific handling:**
- Boolean values converted to integers for PostgreSQL compatibility
- Timestamps handled with proper timezone awareness

---

### 2. TestCheckpointSystem

**Purpose:** Verify checkpoint creation and retrieval for pipeline state management.

**What it tests:**
- Creating parent checkpoints
- Creating child checkpoints with parent references
- Retrieving checkpoints by thread_id
- Retrieving checkpoints by pipeline_id
- Parent-child relationships via foreign keys

**Real-world scenario:**
```
Pipeline runs → Creates checkpoint at step 1 → Continues to step 2 → Creates checkpoint with reference to step 1
```

**Database tables used:**
- `pipeline_checkpoints`

**Key assertions:**
- Checkpoints are created with correct step information
- Parent-child relationships are maintained
- Checkpoints can be queried by thread or pipeline
- State data is stored correctly (as JSON/TEXT)

**Database-specific handling:**
- PostgreSQL generates UUIDs automatically
- MySQL/SQLite/MSSQL require explicit UUID generation
- Parent checkpoint ID retrieved after insert for PostgreSQL

---

### 3. TestConversationMemory

**Purpose:** Test conversation message storage and retrieval.

**What it tests:**
- Storing multi-turn conversations
- Maintaining message order by timestamp
- Querying conversations by thread_id
- Counting messages by role (user/assistant)

**Real-world scenario:**
```
User: "Hello, I need help"
Assistant: "I'd be happy to help!"
User: "It's failing at step 3"
Assistant: "Let me check the logs"
```

**Database tables used:**
- `conversation_messages`

**Key assertions:**
- Messages are stored in correct order
- Message roles are preserved
- Thread isolation works correctly
- Message counts are accurate

**Database-specific handling:**
- Incrementing timestamps ensure proper ordering
- PostgreSQL auto-generates message_id
- Other databases require explicit UUID

---

### 4. TestReliabilityMetrics

**Purpose:** Verify reliability tracking for agents, workflows, and SLOs.

#### 4a. test_step_metrics_recording

**What it tests:**
- Recording successful agent steps
- Recording failed steps
- Querying by agent name
- Calculating success rates
- Tracking compensation requirements

**Real-world scenario:**
```
Agent runs 7 times → 5 succeed, 2 fail → Calculate 71% success rate
```

**Database tables used:**
- `reliability_steps`

**Key assertions:**
- All step executions are recorded
- Success/failure counts are accurate
- Compensation tracking works
- Agent-specific filtering works

#### 4b. test_workflow_metrics

**What it tests:**
- Recording workflow executions
- Tracking retry counts
- Recording workflow success/failure

**Database tables used:**
- `reliability_workflows`

**Key assertions:**
- Workflow metadata is stored correctly
- Retry counts are accurate
- Success status is preserved

#### 4c. test_slo_measurements

**What it tests:**
- Recording MTTE (Mean Time To Execute) measurements
- Recording RSR (Replay Success Rate) measurements
- Querying by measurement type
- Calculating averages

**Database tables used:**
- `reliability_slo_measurements`

**Key assertions:**
- MTTE duration is recorded correctly
- RSR replay mode is stored
- Measurements can be filtered by type
- Averages can be calculated

---

### 5. TestComplexQueries

**Purpose:** Test advanced SQL queries involving JOINs and aggregations.

#### 5a. test_pipeline_execution_with_logs

**What it tests:**
- LEFT JOIN between executions and logs
- COUNT aggregation
- GROUP BY clause

**SQL executed:**
```sql
SELECT e.execution_id, e.status, COUNT(l.id) as log_count
FROM pipeline_executions e
LEFT JOIN execution_logs l ON e.execution_id = l.execution_id
WHERE e.execution_id = :id
GROUP BY e.execution_id, e.status
```

**Key assertions:**
- JOIN returns correct results
- Log count matches inserted logs
- Execution status is preserved

#### 5b. test_time_range_queries

**What it tests:**
- Timestamp comparisons
- Range queries (>=)
- Time-based filtering

**Real-world scenario:**
```
Query: "Show me all steps from the last hour"
Result: 2-3 steps depending on database timestamp precision
```

**Key assertions:**
- Time range filtering works
- Results are within expected range
- All-time queries return complete dataset

**Database-specific handling:**
- MySQL has lower timestamp precision (seconds vs microseconds)
- Test accommodates 2-3 results instead of exact 3

---

### 6. TestTransactionBehavior

**Purpose:** Verify transaction rollback on errors.

**What it tests:**
- Successful inserts are committed
- Duplicate key errors cause rollback
- Original data remains intact after error

**Real-world scenario:**
```
Insert pipeline → Verify it exists → Try to insert duplicate → Error occurs → Original still exists
```

**Key assertions:**
- Data persists after successful insert
- Failed operations don't corrupt data
- Transaction isolation works

---

### 7. TestDataIntegrity

**Purpose:** Verify database constraints and referential integrity.

#### 7a. test_foreign_key_integrity

**What it tests:**
- Foreign key constraints are enforced
- Child records reference valid parent records
- Proper cleanup order (child before parent)

**Database tables used:**
- `pipeline_executions` (parent)
- `step_executions` (child)

**Key assertions:**
- Child record can be created with valid FK
- Child record links to correct parent
- Cleanup respects FK constraints

#### 7b. test_unique_constraints

**What it tests:**
- UNIQUE constraints on slug fields
- Duplicate prevention
- Error handling for constraint violations

**Key assertions:**
- First insert succeeds
- Duplicate insert fails
- Only one record with unique value exists

---

## Running the Tests

### Basic Usage

```bash
# Set environment variables for database connections
export TEST_POSTGRESQL_URL="postgresql://testuser:testpass@localhost:15432/ia_modules_test"
export TEST_MYSQL_URL="mysql://testuser:testpass@localhost:13306/ia_modules_test"
export TEST_MSSQL_URL="mssql://sa:TestPass123!@localhost:11433/master"

# Run all tests
python -m pytest tests/e2e/test_sql_pipeline_e2e.py -v
```

### PowerShell (Windows)

```powershell
$env:TEST_POSTGRESQL_URL="postgresql://testuser:testpass@localhost:15432/ia_modules_test"
$env:TEST_MYSQL_URL="mysql://testuser:testpass@localhost:13306/ia_modules_test"
$env:TEST_MSSQL_URL="mssql://sa:TestPass123!@localhost:11433/master"
python -m pytest tests/e2e/test_sql_pipeline_e2e.py -v
```

### Running Specific Tests

```bash
# Run only pipeline lifecycle tests
pytest tests/e2e/test_sql_pipeline_e2e.py::TestPipelineLifecycle -v

# Run only on PostgreSQL
pytest tests/e2e/test_sql_pipeline_e2e.py -k postgresql -v

# Run specific test on all databases
pytest tests/e2e/test_sql_pipeline_e2e.py::TestReliabilityMetrics::test_step_metrics_recording -v
```

## Test Results

All **44 tests** pass across all 4 databases:

```
✓ TestPipelineLifecycle::test_create_and_execute_pipeline × 4 databases
✓ TestCheckpointSystem::test_checkpoint_creation_and_retrieval × 4 databases
✓ TestConversationMemory::test_conversation_flow × 4 databases
✓ TestReliabilityMetrics::test_step_metrics_recording × 4 databases
✓ TestReliabilityMetrics::test_workflow_metrics × 4 databases
✓ TestReliabilityMetrics::test_slo_measurements × 4 databases
✓ TestComplexQueries::test_pipeline_execution_with_logs × 4 databases
✓ TestComplexQueries::test_time_range_queries × 4 databases
✓ TestTransactionBehavior::test_rollback_on_error × 4 databases
✓ TestDataIntegrity::test_foreign_key_integrity × 4 databases
✓ TestDataIntegrity::test_unique_constraints × 4 databases

Total: 11 test scenarios × 4 databases = 44 tests
```

## Database Schema

The tests rely on the complete schema defined in:
```
ia_modules/database/migrations/V001__complete_schema.sql
```

**Key tables tested:**

| Table | Purpose | Test Coverage |
|-------|---------|---------------|
| `pipelines` | Pipeline definitions | TestPipelineLifecycle |
| `pipeline_executions` | Execution tracking | TestPipelineLifecycle, TestComplexQueries |
| `step_executions` | Individual step runs | TestPipelineLifecycle, TestDataIntegrity |
| `execution_logs` | Execution logging | TestPipelineLifecycle, TestComplexQueries |
| `pipeline_checkpoints` | State management | TestCheckpointSystem |
| `conversation_messages` | Chat history | TestConversationMemory |
| `reliability_steps` | Agent metrics | TestReliabilityMetrics |
| `reliability_workflows` | Workflow metrics | TestReliabilityMetrics |
| `reliability_slo_measurements` | SLO tracking | TestReliabilityMetrics |

## Database-Specific Considerations

### PostgreSQL
- **UUIDs**: Auto-generated via `gen_random_uuid()`
- **Booleans**: Native BOOLEAN type supported
- **JSONB**: Used for structured metadata
- **Transactions**: Full ACID compliance

### MySQL
- **UUIDs**: Must be provided as CHAR(36)
- **Booleans**: Stored as TINYINT(1)
- **JSON**: Native JSON type (not JSONB)
- **Timestamps**: Second-level precision (no microseconds)

### MSSQL
- **UUIDs**: Stored as UNIQUEIDENTIFIER
- **Booleans**: Stored as BIT
- **JSON**: Stored as NVARCHAR(MAX)
- **Timestamps**: DATETIME2 type

### SQLite
- **UUIDs**: Stored as TEXT
- **Booleans**: Stored as INTEGER (0/1)
- **JSON**: Stored as TEXT
- **Timestamps**: Stored as TEXT (ISO format)

## Key Testing Patterns

### 1. Parameterized Fixtures
```python
@pytest.fixture
async def initialized_db(db_config):
    # Automatically runs for each database type
```

### 2. Proper Cleanup
```python
try:
    # Test code
finally:
    # Always cleanup, even if test fails
    db.execute("DELETE FROM ...")
```

### 3. Database-Agnostic SQL
```python
# Works on all databases
db.execute("INSERT INTO table (col) VALUES (:val)", {"val": value})
```

### 4. Type Handling
```python
# Convert booleans to integers for compatibility
"is_active": 1  # instead of True
```

### 5. Timestamp Precision
```python
# Use incrementing timestamps for ordering
msg_timestamp = base_time + timedelta(seconds=idx)
```

## Benefits of E2E Database Testing

1. **Real Data Persistence**: Tests actual database I/O, not mocks
2. **Cross-Database Validation**: Ensures SQL works on all backends
3. **Schema Verification**: Confirms migrations create correct tables
4. **Data Integrity**: Validates constraints and relationships
5. **Performance Insights**: Shows real query performance
6. **Production Confidence**: Tests match production behavior

## Common Issues and Solutions

### Issue: Test fails on one database but passes on others
**Solution**: Check for database-specific SQL syntax or data type differences. Use the `db.config.database_type` check for conditional logic.

### Issue: Foreign key constraint errors
**Solution**: Ensure proper cleanup order - delete child records before parent records.

### Issue: Timestamp ordering issues
**Solution**: Use incrementing timestamps rather than `datetime.now()` for each insert.

### Issue: UUID generation differences
**Solution**: Check database type and generate UUIDs accordingly (auto-generated for PostgreSQL, explicit for others).

## Future Enhancements

Potential additions to the test suite:

- **Concurrent Access**: Test multiple simultaneous executions
- **Large Dataset Tests**: Test with thousands of records
- **Migration Testing**: Test schema upgrades
- **Backup/Restore**: Test data durability
- **Performance Benchmarks**: Compare query speeds across databases
- **Index Effectiveness**: Verify indexes improve performance
- **Full-Text Search**: Test search capabilities
- **Stored Procedures**: Test database functions (where supported)

## Conclusion

The `test_sql_pipeline_e2e.py` suite provides comprehensive coverage of the pipeline system's data layer across all supported databases. With 44 passing tests, it ensures that:

- ✅ Data is correctly saved and retrieved
- ✅ All database backends work identically
- ✅ Complex queries (JOINs, aggregations) work correctly
- ✅ Data integrity constraints are enforced
- ✅ Transactions handle errors properly
- ✅ The database layer is validated and reliable

These tests serve as both verification and documentation of the system's database capabilities.

---

## What "Production-Ready" Would Require

While this test suite validates the database layer thoroughly, **additional validation is needed** before production deployment:

### 1. Performance Testing (NOT COVERED)

**Current Status:** No performance benchmarks exist

**Needed:**
```python
# tests/performance/test_database_performance.py
@pytest.mark.performance
async def test_1000_concurrent_inserts():
    """Verify database handles 1000 concurrent writes"""
    tasks = [insert_execution(i) for i in range(1000)]
    start = time.time()
    await asyncio.gather(*tasks)
    duration = time.time() - start
    
    assert duration < 10.0  # Should complete in <10s
    assert error_rate < 0.01  # <1% errors
```

**Why It Matters:**
- E2E tests use single-threaded sequential operations
- Production will have 10+ concurrent requests
- Need to verify connection pooling works
- Need to measure query performance at scale

### 2. Data Migration Testing (NOT COVERED)

**Current Status:** Tests create fresh databases each time

**Needed:**
```python
# tests/migration/test_schema_upgrades.py
async def test_v001_to_v002_migration():
    """Verify data survives schema upgrade"""
    # 1. Apply V001 schema
    # 2. Insert test data
    # 3. Apply V002 schema
    # 4. Verify data still intact
    # 5. Verify new columns exist
```

**Why It Matters:**
- Production databases will be migrated, not recreated
- Need to verify no data loss during upgrades
- Need to test rollback procedures

### 3. Disaster Recovery (NOT COVERED)

**Current Status:** No backup/restore testing

**Needed:**
```bash
# tests/disaster_recovery/test_backup_restore.sh
# 1. Take full database backup
# 2. Corrupt/delete database
# 3. Restore from backup
# 4. Verify all data intact
# 5. Measure restore time
```

**Why It Matters:**
- Production needs recovery procedures
- Need to verify backups are restorable
- Need to measure RTO (Recovery Time Objective)

### 4. Security Testing (NOT COVERED)

**Current Status:** Tests use hardcoded credentials

**Needed:**
```python
# tests/security/test_sql_injection.py
async def test_sql_injection_attempts():
    """Verify database is immune to SQL injection"""
    malicious_inputs = [
        "'; DROP TABLE pipelines; --",
        "1' OR '1'='1",
        "admin'--",
        "<script>alert('XSS')</script>"
    ]
    for input in malicious_inputs:
        result = await db.execute(
            "SELECT * FROM pipelines WHERE id = :id",
            {"id": input}
        )
        assert result is None  # Should return nothing
        # Verify tables still exist
        assert db.table_exists("pipelines")
```

**Why It Matters:**
- Production faces real attacks
- Need to verify parameterized queries work
- Need to test input validation

### 5. Monitoring & Alerting (NOT COVERED)

**Current Status:** Tests don't verify observability

**Needed:**
```python
# tests/observability/test_metrics_collection.py
async def test_execution_metrics_recorded():
    """Verify all executions generate metrics"""
    # Execute pipeline
    job_id = await execute_pipeline()
    
    # Verify metrics exist in Prometheus/Grafana
    metrics = await prometheus.query(
        f'pipeline_executions_total{{job_id="{job_id}"}}'
    )
    assert metrics.value > 0
    
    # Verify logs exist
    logs = await elasticsearch.search(f"job_id:{job_id}")
    assert len(logs) > 0
```

**Why It Matters:**
- Production needs real-time visibility
- Need to verify metrics are collected
- Need to verify alerts fire correctly

### 6. Load Testing (NOT COVERED)

**Current Status:** Tests run sequentially

**Needed:**
```python
# tests/load/test_sustained_load.py
@pytest.mark.load
async def test_1hour_sustained_load():
    """Run 1000 req/min for 1 hour"""
    duration = 3600  # 1 hour
    rate = 1000 / 60  # 16.67 req/sec
    
    start = time.time()
    total_requests = 0
    errors = 0
    
    while time.time() - start < duration:
        try:
            await execute_pipeline()
            total_requests += 1
        except Exception:
            errors += 1
        await asyncio.sleep(1/rate)
    
    error_rate = errors / total_requests
    assert error_rate < 0.001  # <0.1% errors
    
    # Verify database still responsive
    response_time = await db.ping()
    assert response_time < 0.1  # <100ms
```

**Why It Matters:**
- Production runs 24/7 with sustained load
- Need to verify no memory leaks
- Need to verify database connections don't exhaust

---

## Production Readiness Assessment

| Category | E2E Tests | Production Needs | Gap |
|----------|-----------|------------------|-----|
| **Functional Correctness** | ✅ 100% (44/44 tests) | ✅ Verified | None |
| **Database Compatibility** | ✅ 4 databases tested | ✅ Verified | None |
| **Data Integrity** | ✅ Constraints tested | ✅ Verified | None |
| **Performance** | ❌ Not tested | ⚠️ Unknown | **HIGH** |
| **Concurrency** | ❌ Not tested | ⚠️ Unknown | **HIGH** |
| **Migrations** | ❌ Not tested | ⚠️ Unknown | **MEDIUM** |
| **Backup/Restore** | ❌ Not tested | ⚠️ Unknown | **HIGH** |
| **Security** | ❌ Not tested | ⚠️ Unknown | **MEDIUM** |
| **Monitoring** | ❌ Not tested | ⚠️ Unknown | **MEDIUM** |
| **Load Testing** | ❌ Not tested | ⚠️ Unknown | **HIGH** |

### Summary

**The E2E test suite validates that the database layer works correctly**, but this represents approximately **30% of production readiness**.

**Still needed for production:**
1. Performance benchmarks (2-3 days)
2. Concurrency testing (1-2 days)
3. Migration testing (1 day)
4. Backup/restore procedures (1 day)
5. Security audit (2 days)
6. Monitoring setup (1-2 days)
7. Load testing (2-3 days)

**Estimated effort:** 10-15 days additional work

**Current status:** Database layer is **functionally verified** but **not production-ready** without the above additions.
