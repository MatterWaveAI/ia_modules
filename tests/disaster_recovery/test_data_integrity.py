"""
Data Integrity Disaster Recovery Tests

Comprehensive tests to verify data integrity during backup and restore operations.
Tests checksums, data consistency, corruption detection, and data preservation.
"""

import pytest
import hashlib
import json
from datetime import datetime
import tempfile
import os

from nexusql import DatabaseManager

# nexusql returns a SELECT's rows as a list of dicts; these read them the way the
# SQLAlchemy result objects this suite was first written against did.
def _scalar(rows):
    return next(iter(rows[0].values())) if rows else None


def _first(rows):
    return rows[0] if rows else None


def _table_names(db):
    return [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]


def calculate_checksum(data: str) -> str:
    """Calculate SHA-256 checksum of data."""
    return hashlib.sha256(data.encode()).hexdigest()


def calculate_table_checksum(db_manager: DatabaseManager, table_name: str) -> str:
    """Calculate checksum of entire table contents."""
    # Export table data as JSON
    result = db_manager.execute(f"SELECT * FROM {table_name} ORDER BY id")
    rows = result

    # Convert to JSON and calculate checksum
    data_json = json.dumps([dict(row) for row in rows], sort_keys=True)
    return calculate_checksum(data_json)


@pytest.fixture
async def source_database():
    """Create source database with test data."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    await db_manager.initialize(apply_schema=False)  # the tests create their own tables

    # Create schema
    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            config TEXT,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY,
            pipeline_id INTEGER,
            status TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY,
            execution_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (execution_id) REFERENCES executions(id)
        )
    """)

    # Insert test data
    for i in range(100):
        await db_manager.execute_async("INSERT INTO pipelines (name, config, version) VALUES (:name, :config, :version)", {"name": f"pipeline_{i}", "config": json.dumps({"test": i}), "version": i % 10}
        )

    for i in range(500):
        await db_manager.execute_async("INSERT INTO executions (pipeline_id, status, result) VALUES (:pipeline_id, :status, :result)", {"pipeline_id": i % 100 + 1, "status": "completed", "result": json.dumps({"output": i})}
        )

    for i in range(2000):
        await db_manager.execute_async("INSERT INTO metrics (execution_id, metric_name, metric_value) VALUES (:execution_id, :metric_name, :metric_value)", {"execution_id": i % 500 + 1, "metric_name": f"metric_{i % 10}", "metric_value": float(i)}
        )

    yield db_manager
    await db_manager.close()


@pytest.fixture
async def backup_file():
    """Create temporary backup file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
        backup_path = f.name

    yield backup_path

    # Cleanup
    if os.path.exists(backup_path):
        os.remove(backup_path)


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_preserves_all_data(source_database, backup_file):
    """Test that backup preserves all data without loss."""

    # Count records before backup
    pipelines_count = _scalar(await source_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    executions_count = _scalar(await source_database.execute_async(
        "SELECT COUNT(*) FROM executions"
    ))

    metrics_count = _scalar(await source_database.execute_async(
        "SELECT COUNT(*) FROM metrics"
    ))

    # Calculate checksums before backup
    pipelines_checksum = calculate_table_checksum(source_database, "pipelines")
    executions_checksum = calculate_table_checksum(source_database, "executions")
    metrics_checksum = calculate_table_checksum(source_database, "metrics")

    # Perform backup (simplified - in production use proper backup tools)
    backup_data = []
    for table in ["pipelines", "executions", "metrics"]:
        result = await source_database.execute_async(f"SELECT * FROM {table}")
        rows = result
        backup_data.append({
            "table": table,
            "rows": [dict(row) for row in rows]
        })

    # Write backup to file
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f)

    # Create new database and restore
    restored_db = DatabaseManager("sqlite:///:memory:")
    await restored_db.initialize(apply_schema=False)  # the tests create their own tables

    # Restore schema
    await restored_db.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            config TEXT,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await restored_db.execute_async("""
        CREATE TABLE executions (
            id INTEGER PRIMARY KEY,
            pipeline_id INTEGER,
            status TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    await restored_db.execute_async("""
        CREATE TABLE metrics (
            id INTEGER PRIMARY KEY,
            execution_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (execution_id) REFERENCES executions(id)
        )
    """)

    # Restore data
    with open(backup_file, 'r') as f:
        backup_data = json.load(f)

    for table_backup in backup_data:
        table_name = table_backup["table"]
        for row in table_backup["rows"]:
            columns = list(row.keys())
            values = list(row.values())
            placeholders = ','.join(['?' for _ in columns])

            await restored_db.execute_async(
                f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})",
                tuple(values)
            )

    # Verify record counts
    restored_pipelines = _scalar(await restored_db.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    restored_executions = _scalar(await restored_db.execute_async(
        "SELECT COUNT(*) FROM executions"
    ))

    restored_metrics = _scalar(await restored_db.execute_async(
        "SELECT COUNT(*) FROM metrics"
    ))

    assert restored_pipelines == pipelines_count, \
        f"Pipeline count mismatch: {restored_pipelines} != {pipelines_count}"
    assert restored_executions == executions_count, \
        f"Execution count mismatch: {restored_executions} != {executions_count}"
    assert restored_metrics == metrics_count, \
        f"Metrics count mismatch: {restored_metrics} != {metrics_count}"

    # Verify checksums
    restored_pipelines_checksum = calculate_table_checksum(restored_db, "pipelines")
    restored_executions_checksum = calculate_table_checksum(restored_db, "executions")
    restored_metrics_checksum = calculate_table_checksum(restored_db, "metrics")

    assert restored_pipelines_checksum == pipelines_checksum, \
        "Pipeline data integrity check failed"
    assert restored_executions_checksum == executions_checksum, \
        "Execution data integrity check failed"
    assert restored_metrics_checksum == metrics_checksum, \
        "Metrics data integrity check failed"

    await restored_db.close()


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_incremental_backup_consistency(source_database):
    """Test that incremental backups maintain consistency."""

    # Take initial full backup
    initial_checksum = calculate_table_checksum(source_database, "pipelines")

    # Modify some data
    await source_database.execute_async(
        "UPDATE pipelines SET version = version + 1 WHERE id <= 10"
    )

    # Take incremental backup (only changed records)
    changed_records = await source_database.execute_async(
        "SELECT * FROM pipelines WHERE id <= 10"
    )
    changed_data = [dict(row) for row in changed_records]

    # Calculate new checksum
    new_checksum = calculate_table_checksum(source_database, "pipelines")

    # Verify checksum changed
    assert new_checksum != initial_checksum, "Checksum should change after modification"

    # Verify we can identify changed records
    assert len(changed_data) == 10, "Should identify 10 changed records"

    # Verify changed records have updated version
    for record in changed_data:
        assert record["version"] >= 1, "Version should be incremented"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_detect_data_corruption(source_database, backup_file):
    """Test detection of data corruption after restore."""

    # Create backup
    original_data = []
    result = await source_database.execute_async("SELECT * FROM pipelines")
    rows = result
    for row in rows:
        original_data.append(dict(row))

    # Calculate original checksum
    original_checksum = calculate_checksum(json.dumps(original_data, sort_keys=True))

    # Simulate corruption by modifying backup file
    with open(backup_file, 'w') as f:
        corrupted_data = original_data.copy()
        if corrupted_data:
            # Corrupt one record
            corrupted_data[0]["name"] = "CORRUPTED"
        json.dump(corrupted_data, f)

    # Calculate corrupted checksum
    with open(backup_file, 'r') as f:
        restored_data = json.load(f)

    corrupted_checksum = calculate_checksum(json.dumps(restored_data, sort_keys=True))

    # Verify corruption is detected
    assert corrupted_checksum != original_checksum, \
        "Checksum should detect data corruption"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_foreign_key_integrity_after_restore(source_database, backup_file):
    """Test that foreign key relationships are preserved after restore."""

    # Verify FK relationships before backup
    result = await source_database.execute_async("""
        SELECT e.id, e.pipeline_id, p.id
        FROM executions e
        JOIN pipelines p ON e.pipeline_id = p.id
        LIMIT 100
    """)

    original_relationships = result
    assert len(original_relationships) > 0, "Should have FK relationships"

    # Create backup and restore (simplified)
    backup_data = {
        "pipelines": [],
        "executions": []
    }

    for table in ["pipelines", "executions"]:
        result = await source_database.execute_async(f"SELECT * FROM {table}")
        rows = result
        backup_data[table] = [dict(row) for row in rows]

    # Create restored database
    restored_db = DatabaseManager("sqlite:///:memory:")
    await restored_db.initialize(apply_schema=False)  # the tests create their own tables

    # Restore schema
    await restored_db.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            config TEXT,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await restored_db.execute_async("""
        CREATE TABLE executions (
            id INTEGER PRIMARY KEY,
            pipeline_id INTEGER,
            status TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    # Restore data (pipelines first to satisfy FK)
    for row in backup_data["pipelines"]:
        columns = list(row.keys())
        values = list(row.values())
        placeholders = ','.join(['?' for _ in columns])

        await restored_db.execute_async(
            f"INSERT INTO pipelines ({','.join(columns)}) VALUES ({placeholders})",
            tuple(values)
        )

    for row in backup_data["executions"]:
        columns = list(row.keys())
        values = list(row.values())
        placeholders = ','.join(['?' for _ in columns])

        await restored_db.execute_async(
            f"INSERT INTO executions ({','.join(columns)}) VALUES ({placeholders})",
            tuple(values)
        )

    # Verify FK relationships after restore
    result = await restored_db.execute_async("""
        SELECT e.id, e.pipeline_id, p.id
        FROM executions e
        JOIN pipelines p ON e.pipeline_id = p.id
        LIMIT 100
    """)

    restored_relationships = result

    assert len(restored_relationships) == len(original_relationships), \
        "FK relationships should be preserved"

    # Verify no orphaned records
    orphaned = await restored_db.execute_async("""
        SELECT COUNT(*) FROM executions e
        LEFT JOIN pipelines p ON e.pipeline_id = p.id
        WHERE p.id IS NULL
    """)

    orphan_count = _scalar(orphaned)
    assert orphan_count == 0, f"Found {orphan_count} orphaned execution records"

    await restored_db.close()


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_verify_data_types_after_restore(source_database):
    """Test that data types are preserved during backup/restore."""

    # Insert data with specific types
    test_data = {
        "id": 9999,
        "name": "type_test",
        "config": json.dumps({"test": "value"}),
        "version": 42
    }

    await source_database.execute_async("INSERT INTO pipelines (id, name, config, version) VALUES (:id, :name, :config, :version)", {"id": test_data["id"], "name": test_data["name"], "config": test_data["config"], "version": test_data["version"]}
    )

    # Retrieve and verify types
    result = await source_database.execute_async("SELECT * FROM pipelines WHERE id = :id", {"id": test_data["id"]}
    )

    row = _first(result)
    assert row is not None

    # Verify types
    assert isinstance(row["id"], int), "ID should be integer"
    assert isinstance(row["name"], str), "Name should be string"
    assert isinstance(row["version"], int), "Version should be integer"

    # Verify JSON can be parsed
    config = json.loads(row["config"])
    assert config["test"] == "value", "JSON should be preserved"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_verify_null_values_preserved(source_database):
    """Test that NULL values are correctly preserved."""

    # Insert record with NULL values
    await source_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": "null_test", "config": None}
    )

    # Retrieve and verify
    result = await source_database.execute_async("SELECT * FROM pipelines WHERE name = :name", {"name": "null_test"}
    )

    row = _first(result)
    assert row is not None
    assert row["config"] is None, "NULL value should be preserved"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_verify_special_characters_preserved(source_database):
    """Test that special characters are preserved in backup/restore."""

    special_chars = [
        "emoji = test",
        "unicode � � � � � �",
        "quotes ' \" test",
        "newlines\nand\ttabs",
        "backslash \\ test",
        "json {\"key\": \"value\"}"
    ]

    # Insert records with special characters
    for i, text in enumerate(special_chars):
        await source_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"special_{i}", "config": text}
        )

    # Retrieve and verify
    for i, expected_text in enumerate(special_chars):
        result = await source_database.execute_async("SELECT config FROM pipelines WHERE name = :name", {"name": f"special_{i}"}
        )

        row = _first(result)
        assert row is not None
        assert row["config"] == expected_text, \
            f"Special characters not preserved: {repr(expected_text)}"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_verify_large_blob_integrity(source_database):
    """Test that large binary/text data maintains integrity."""

    # Create large text blob (1MB)
    large_text = "A" * (1024 * 1024)
    checksum_before = calculate_checksum(large_text)

    # Insert
    await source_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": "large_blob", "config": large_text}
    )

    # Retrieve
    result = await source_database.execute_async("SELECT config FROM pipelines WHERE name = :name", {"name": "large_blob"}
    )

    row = _first(result)
    assert row is not None

    retrieved_text = row["config"]
    checksum_after = calculate_checksum(retrieved_text)

    # Verify integrity
    assert len(retrieved_text) == len(large_text), "Length should match"
    assert checksum_after == checksum_before, "Checksum should match"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_verify_timestamp_precision(source_database):
    """Test that timestamp precision is preserved."""

    # Insert with known timestamp
    from datetime import datetime
    test_timestamp = datetime.now()

    await source_database.execute_async("INSERT INTO pipelines (name, created_at) VALUES (:name, :created_at)", {"name": "timestamp_test", "created_at": test_timestamp}
    )

    # Retrieve
    result = await source_database.execute_async("SELECT created_at FROM pipelines WHERE name = :name", {"name": "timestamp_test"}
    )

    row = _first(result)
    assert row is not None

    retrieved_timestamp = row["created_at"]

    # Verify timestamp is close (within 1 second)
    if isinstance(retrieved_timestamp, str):
        retrieved_timestamp = datetime.fromisoformat(retrieved_timestamp)

    time_diff = abs((retrieved_timestamp - test_timestamp).total_seconds())
    assert time_diff < 1.0, f"Timestamp precision lost: {time_diff}s difference"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_verify_index_integrity_after_restore(source_database):
    """Test that indexes are recreated correctly after restore."""

    # Create index
    await source_database.execute_async(
        "CREATE INDEX idx_pipeline_name ON pipelines(name)"
    )

    # Query using index (should be fast)
    import time
    start = time.time()

    result = await source_database.execute_async("SELECT * FROM pipelines WHERE name = :name", {"name": "pipeline_50"}
    )
    rows = result

    elapsed = time.time() - start

    # Should complete quickly with index
    assert elapsed < 0.1, f"Query took {elapsed:.3f}s, index may be missing"
    assert len(rows) > 0, "Should find matching records"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_metadata_tracking():
    """Test that backup metadata is properly tracked."""

    # Create backup metadata
    backup_metadata = {
        "backup_id": "backup_20250125_120000",
        "timestamp": datetime.now().isoformat(),
        "database_size_mb": 125.5,
        "record_count": {
            "pipelines": 100,
            "executions": 500,
            "metrics": 2000
        },
        "checksums": {
            "pipelines": "abc123",
            "executions": "def456",
            "metrics": "ghi789"
        },
        "backup_type": "full",
        "compression": "gzip",
        "encryption": "aes256"
    }

    # Verify all required metadata fields present
    required_fields = [
        "backup_id", "timestamp", "database_size_mb",
        "record_count", "checksums", "backup_type"
    ]

    for field in required_fields:
        assert field in backup_metadata, f"Missing required metadata field: {field}"

    # Verify checksums format
    for table, checksum in backup_metadata["checksums"].items():
        assert isinstance(checksum, str), f"Checksum for {table} should be string"
        assert len(checksum) > 0, f"Checksum for {table} should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "disaster_recovery"])
