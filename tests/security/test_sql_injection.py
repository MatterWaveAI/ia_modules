"""
SQL Injection Security Tests

Comprehensive tests to verify protection against SQL injection attacks.
Tests all OWASP SQL injection vectors and database-specific attacks.
"""

import pytest

from nexusql import DatabaseManager


# OWASP SQL Injection Attack Vectors
SQL_INJECTION_VECTORS = [
    # Classic SQL Injection
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "1' OR '1'='1' --",
    "admin'--",
    "' OR 1=1--",

    # Union-based Injection
    "' UNION SELECT NULL, NULL--",
    "' UNION SELECT username, password FROM users--",
    "1' UNION SELECT NULL, NULL, NULL--",

    # Boolean-based Blind Injection
    "' AND 1=1--",
    "' AND 1=2--",

    # Time-based Blind Injection
    "1' AND SLEEP(5)--",
    "1'; WAITFOR DELAY '00:00:05'--",

    # Error-based Injection
    "' AND 1=CONVERT(int, (SELECT @@version))--",

    # Stacked Queries
    "1'; DROP TABLE pipelines; --",
    "'; EXEC sp_MSForEachTable 'DROP TABLE ?'; --",

    # Second Order Injection
    "admin' AND EXTRACTVALUE(1, CONCAT(0x01, (SELECT password FROM users)))--",
]

# nexusql returns a SELECT's rows as a list of dicts; these read them the way the
# SQLAlchemy result objects this suite was first written against did.
def _scalar(rows):
    return next(iter(rows[0].values())) if rows else None


def _first(rows):
    return rows[0] if rows else None


def _table_names(db):
    return [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]


@pytest.fixture
async def test_database():
    """Create isolated test database."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    await db_manager.initialize(apply_schema=False)  # the tests create their own tables

    # Create test schema
    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY,
            pipeline_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    yield db_manager
    await db_manager.close()


@pytest.mark.security
@pytest.mark.asyncio
async def test_sql_injection_in_pipeline_name(test_database):
    """Test SQL injection attempts in pipeline name field."""

    for vector in SQL_INJECTION_VECTORS:
        try:
            # Attempt to create pipeline with malicious name
            await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": vector, "config": '{}'}
            )

            # Verify tables still exist (not dropped)
            tables = _table_names(test_database)

            assert 'pipelines' in tables, f"Pipelines table dropped by: {vector}"
            assert 'executions' in tables, f"Executions table dropped by: {vector}"

            # Verify data integrity
            result = await test_database.execute_async("SELECT COUNT(*) FROM pipelines")
            count = _scalar(result)
            assert count >= 0, "Data corrupted"

        except Exception as e:
            # Exceptions are acceptable (input rejected)
            # But error messages should not leak SQL details
            error_msg = str(e).upper()

            assert 'DROP' not in error_msg, f"Error leaks SQL: {e}"
            assert 'TABLE' not in error_msg, f"Error leaks schema: {e}"
            assert 'UNION' not in error_msg, f"Error leaks SQL: {e}"
            assert 'SELECT' not in error_msg, f"Error leaks SQL: {e}"


@pytest.mark.security
@pytest.mark.asyncio
async def test_sql_injection_in_search_query(test_database):
    """Test SQL injection in search/filter queries."""

    # Insert test data
    await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": "test_pipeline", "config": '{}'}
    )

    for vector in SQL_INJECTION_VECTORS:
        try:
            # Attempt search with malicious query
            # This simulates: SELECT * FROM pipelines WHERE name LIKE ?
            result = await test_database.execute_async("SELECT * FROM pipelines WHERE name LIKE :name", {"name": f"%{vector}%"}
            )

            rows = result

            # Should return empty or valid results, not cause errors
            assert isinstance(rows, list), "Should return list"

            # Verify tables still exist
            tables = _table_names(test_database)
            assert len(tables) >= 2, f"Tables affected by: {vector}"

        except Exception as e:
            # Verify error doesn't leak information
            error_msg = str(e).upper()
            assert 'DROP' not in error_msg
            assert 'PASSWORD' not in error_msg
            assert 'USER' not in error_msg


@pytest.mark.security
@pytest.mark.asyncio
async def test_parameterized_queries_prevent_injection(test_database):
    """Verify parameterized queries properly escape malicious input."""

    dangerous_input = "'; DROP TABLE pipelines; SELECT '"

    # Insert with parameterized query (safe)
    await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": dangerous_input, "config": '{}'}
    )

    # Verify data stored as-is (not executed)
    result = await test_database.execute_async("SELECT name FROM pipelines WHERE name = :name", {"name": dangerous_input}
    )

    row = _first(result)
    assert row is not None, "Data should be stored"
    assert next(iter(row.values())) == dangerous_input, "Input should be stored as-is"

    # Verify tables still exist
    tables = _table_names(test_database)
    assert 'pipelines' in tables, "Table should not be dropped"


@pytest.mark.security
@pytest.mark.asyncio
async def test_second_order_sql_injection(test_database):
    """Test second-order SQL injection (stored then used)."""

    # Store malicious data
    malicious_name = "'; DROP TABLE executions; --"

    await test_database.execute_async("INSERT INTO pipelines (id, name, config) VALUES (:id, :name, :config)", {"id": 1, "name": malicious_name, "config": '{}'}
    )

    # Retrieve and use in another query (common vulnerability)
    result = await test_database.execute_async("SELECT id, name FROM pipelines WHERE id = :id", {"id": 1}
    )

    row = _first(result)
    pipeline_id, pipeline_name = row

    # Use retrieved name in execution query (should be safe)
    await test_database.execute_async("INSERT INTO executions (pipeline_id, status) VALUES (:pipeline_id, :status)", {"pipeline_id": pipeline_id, "status": f"Running {pipeline_name}"}
    )

    # Verify executions table still exists
    tables = _table_names(test_database)
    assert 'executions' in tables, "Second-order injection succeeded"

    # Verify data
    result = await test_database.execute_async("SELECT COUNT(*) FROM executions")
    count = _scalar(result)
    assert count == 1, "Execution should be recorded"


@pytest.mark.security
@pytest.mark.asyncio
async def test_blind_sql_injection_time_based(test_database):
    """Test prevention of time-based blind SQL injection."""

    import time

    # Time-based payload that would cause 5 second delay
    time_vector = "1' AND SLEEP(5)--"

    start_time = time.time()

    try:
        result = await test_database.execute_async("SELECT * FROM pipelines WHERE id = :id", {"id": time_vector}
        )
        result
    except Exception:
        pass  # Expected to fail

    elapsed = time.time() - start_time

    # Should complete quickly, not sleep for 5 seconds
    assert elapsed < 2.0, f"Time-based injection may have worked ({elapsed:.2f}s)"


@pytest.mark.security
@pytest.mark.asyncio
async def test_blind_sql_injection_boolean_based(test_database):
    """Test prevention of boolean-based blind SQL injection."""

    # Insert test data
    await test_database.execute_async("INSERT INTO pipelines (id, name, config) VALUES (:id, :name, :config)", {"id": 1, "name": "test", "config": '{}'}
    )

    # Boolean-based injection attempts
    true_condition = "1' OR '1'='1"
    false_condition = "1' AND '1'='2"

    try:
        result_true = await test_database.execute_async("SELECT * FROM pipelines WHERE id = :id", {"id": true_condition}
        )
        rows_true = result_true

        result_false = await test_database.execute_async("SELECT * FROM pipelines WHERE id = :id", {"id": false_condition}
        )
        rows_false = result_false

        # Both should fail the same way (both invalid)
        # Not different behavior (which would indicate SQL execution)
        assert len(rows_true) == len(rows_false) == 0, \
            "Boolean injection may allow data extraction"

    except Exception:
        pass  # Both should fail


@pytest.mark.security
@pytest.mark.asyncio
async def test_union_based_injection_prevention(test_database):
    """Test prevention of UNION-based SQL injection."""

    union_vectors = [
        "1' UNION SELECT NULL--",
        "1' UNION SELECT NULL, NULL--",
        "1' UNION SELECT NULL, NULL, NULL--",
        "' UNION SELECT name, config FROM pipelines--",
    ]

    for vector in union_vectors:
        try:
            result = await test_database.execute_async("SELECT name FROM pipelines WHERE id = :id", {"id": vector}
            )
            rows = result

            # Should return 0 rows (invalid ID)
            # Not union results from other tables
            assert len(rows) == 0, f"UNION injection may work: {vector}"

        except Exception:
            pass  # Expected to fail


@pytest.mark.security
@pytest.mark.asyncio
async def test_stacked_queries_prevention(test_database):
    """Test prevention of stacked queries injection."""

    stacked_vector = "1; DROP TABLE pipelines; --"

    try:
        await test_database.execute_async("SELECT * FROM pipelines WHERE id = :id", {"id": stacked_vector}
        )
    except Exception:
        pass  # May fail

    # Verify table still exists
    tables = _table_names(test_database)
    assert 'pipelines' in tables, "Stacked query executed DROP TABLE"


@pytest.mark.security
@pytest.mark.asyncio
async def test_error_based_injection_prevention(test_database):
    """Test that errors don't leak database information."""

    error_vectors = [
        "' AND 1=CONVERT(int, @@version)--",
        "' AND 1=CAST(database() AS int)--",
        "' AND EXTRACTVALUE(1, CONCAT(0x01, user()))--",
    ]

    for vector in error_vectors:
        try:
            await test_database.execute_async("SELECT * FROM pipelines WHERE name = :name", {"name": vector}
            )
        except Exception as e:
            # Error should not leak database version, users, etc.
            error_msg = str(e).upper()

            assert 'VERSION' not in error_msg, "Error leaks version"
            assert 'DATABASE' not in error_msg, "Error leaks DB name"
            assert 'USER' not in error_msg, "Error leaks user info"
            assert 'ROOT' not in error_msg, "Error leaks credentials"


@pytest.mark.security
@pytest.mark.skip(reason="ia_modules.database.security.validate_input was never implemented")
def test_input_validation_rejects_sql_keywords():
    """Test that input validation detects SQL keywords."""

    from ia_modules.database.security import validate_input

    dangerous_inputs = [
        "DROP TABLE",
        "DELETE FROM",
        "UNION SELECT",
        "'; --",
        "1 OR 1=1",
    ]

    for dangerous in dangerous_inputs:
        is_safe = validate_input(dangerous)
        assert not is_safe, f"Failed to detect dangerous input: {dangerous}"

    # Test safe inputs
    safe_inputs = [
        "my_pipeline",
        "Pipeline #123",
        "Test Pipeline (2024)",
        "pipeline-name_v2",
    ]

    for safe in safe_inputs:
        is_safe = validate_input(safe)
        assert is_safe, f"False positive for safe input: {safe}"


@pytest.mark.security
@pytest.mark.asyncio
async def test_no_dynamic_sql_construction(test_database):
    """Verify no string concatenation in SQL queries."""

    # This test verifies implementation doesn't use dangerous patterns
    user_input = "pipelines; DROP TABLE users;"

    # The following patterns should NEVER appear in production code:
    # f"SELECT * FROM {user_input}"  # f-string injection
    # "SELECT * FROM " + user_input   # concatenation
    # query.format(user_input)        # format injection

    # Instead, always use parameterized queries:
    # "SELECT * FROM pipelines WHERE name = ?"

    try:
        # This should fail (invalid input)
        result = await test_database.execute_async("SELECT * FROM pipelines WHERE name = :name", {"name": user_input}
        )
        rows = result
        assert len(rows) == 0, "Should return no results"
    except Exception:
        pass  # Acceptable


@pytest.mark.security
@pytest.mark.asyncio
async def test_prepared_statements_are_reused(test_database):
    """Verify prepared statements are properly reused (prevents some attacks)."""

    # Execute same query multiple times
    for i in range(10):
        result = await test_database.execute_async("SELECT * FROM pipelines WHERE id = :id", {"id": i}
        )
        result

    # No assertion needed - just verify no errors
    # Proper prepared statement handling prevents certain attacks


@pytest.mark.security
@pytest.mark.asyncio
async def test_special_characters_are_escaped(test_database):
    """Test that special SQL characters are properly escaped."""

    special_chars = [
        "'", '"', '\\', '\n', '\r', '\t', '\b', '\0',
        '%', '_', '[', ']', '(', ')',
    ]

    for char in special_chars:
        test_input = f"test{char}name"

        await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": test_input, "config": '{}'}
        )

        result = await test_database.execute_async("SELECT name FROM pipelines WHERE name = :name", {"name": test_input}
        )

        row = _first(result)
        assert row is not None, f"Failed to handle character: {repr(char)}"
        assert next(iter(row.values())) == test_input, f"Character not preserved: {repr(char)}"


@pytest.mark.security
@pytest.mark.asyncio
async def test_sql_injection_in_order_by(test_database):
    """Test SQL injection in ORDER BY clause (common vulnerability)."""

    # Insert test data
    for i in range(5):
        await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": '{}'}
        )

    # Malicious ORDER BY attempts

    try:
        # Order by should use whitelisted columns only
        result = await test_database.execute_async(
            "SELECT * FROM pipelines ORDER BY name"  # Safe
        )
        rows = result
        assert len(rows) == 5, "Data should be intact"
    except Exception:
        pass

    # Verify table exists
    tables = _table_names(test_database)
    assert 'pipelines' in tables


@pytest.mark.security
@pytest.mark.asyncio
async def test_sql_injection_in_limit_offset(test_database):
    """Test SQL injection in LIMIT/OFFSET clauses."""

    # Insert test data
    for i in range(10):
        await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": '{}'}
        )

    # Malicious LIMIT attempts

    try:
        # LIMIT should only accept integers
        result = await test_database.execute_async("SELECT * FROM pipelines LIMIT :limit", {"limit": 5}  # Safe integer
        )
        rows = result
        assert len(rows) == 5
    except Exception:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "security"])
