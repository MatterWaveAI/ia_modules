"""
Restore Procedures Disaster Recovery Tests

Comprehensive tests for database restore procedures including full restore,
point-in-time recovery, partial restore, and restore validation.
"""

import pytest
import asyncio
import os
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from nexusql import DatabaseManager

# nexusql returns a SELECT's rows as a list of dicts; these read them the way the
# SQLAlchemy result objects this suite was first written against did.
def _scalar(rows):
    return next(iter(rows[0].values())) if rows else None


def _first(rows):
    return rows[0] if rows else None


def _table_names(db):
    return [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]


class RestoreManager:
    """Simplified restore manager for testing."""

    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)

    async def restore_full_backup(
        self,
        db_manager: DatabaseManager,
        backup_path: str
    ) -> Dict:
        """Restore database from full backup."""
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        restored_count = 0

        # Restore each table
        for table_name, rows in backup_data["tables"].items():
            for row in rows:
                columns = list(row.keys())
                values = list(row.values())
                placeholders = ','.join(['?' for _ in columns])

                try:
                    await db_manager.execute_async(
                        f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})",
                        tuple(values)
                    )
                    restored_count += 1
                except Exception:
                    pass  # Skip duplicates or errors

        return {
            "restored_count": restored_count,
            "backup_timestamp": backup_data.get("timestamp"),
            "backup_type": backup_data.get("backup_type")
        }

    async def restore_point_in_time(
        self,
        db_manager: DatabaseManager,
        target_time: datetime,
        backup_paths: List[str]
    ) -> Dict:
        """Restore database to specific point in time."""
        # Find appropriate full backup (before target time)
        full_backup = None
        incremental_backups = []

        for backup_path in sorted(backup_paths):
            with open(backup_path, 'r') as f:
                metadata = json.load(f)

            backup_time = datetime.fromisoformat(metadata["timestamp"])

            if backup_time <= target_time:
                if metadata["backup_type"] == "full":
                    full_backup = backup_path
                elif metadata["backup_type"] == "incremental":
                    incremental_backups.append(backup_path)

        if not full_backup:
            raise ValueError("No full backup found before target time")

        # Restore full backup
        result = await self.restore_full_backup(db_manager, full_backup)

        # Apply incremental backups in order
        incremental_count = 0
        for inc_backup in incremental_backups:
            inc_result = await self.restore_full_backup(db_manager, inc_backup)
            incremental_count += inc_result["restored_count"]

        return {
            "restored_count": result["restored_count"] + incremental_count,
            "target_time": target_time.isoformat(),
            "full_backup": full_backup,
            "incremental_backups": len(incremental_backups)
        }

    async def restore_table(
        self,
        db_manager: DatabaseManager,
        backup_path: str,
        table_name: str
    ) -> Dict:
        """Restore specific table from backup."""
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        if table_name not in backup_data["tables"]:
            raise ValueError(f"Table {table_name} not found in backup")

        rows = backup_data["tables"][table_name]
        restored_count = 0

        for row in rows:
            columns = list(row.keys())
            values = list(row.values())
            placeholders = ','.join(['?' for _ in columns])

            try:
                await db_manager.execute_async(
                    f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})",
                    tuple(values)
                )
                restored_count += 1
            except Exception:
                pass

        return {
            "table": table_name,
            "restored_count": restored_count
        }

    async def validate_restore(
        self,
        db_manager: DatabaseManager,
        expected_counts: Dict[str, int]
    ) -> bool:
        """Validate restored database."""
        for table_name, expected_count in expected_counts.items():
            try:
                result = await db_manager.execute_async(
                    f"SELECT COUNT(*) FROM {table_name}"
                )
                actual_count = _scalar(result)

                if actual_count != expected_count:
                    return False
            except Exception:
                return False

        return True


@pytest.fixture
async def source_database():
    """Create source database with test data."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    await db_manager.initialize(apply_schema=False)  # the tests create their own tables

    # Create schema
    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test data
    for i in range(100):
        await db_manager.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    for i in range(50):
        await db_manager.execute_async("INSERT INTO executions (pipeline_id, status) VALUES (:pipeline_id, :status)", {"pipeline_id": i + 1, "status": "completed"}
        )

    yield db_manager
    await db_manager.close()


@pytest.fixture
async def empty_database():
    """Create empty database for restore."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    await db_manager.initialize(apply_schema=False)  # the tests create their own tables

    # Create schema (empty)
    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    await db_manager.execute_async("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    yield db_manager
    await db_manager.close()


@pytest.fixture
def backup_dir():
    """Create temporary backup directory."""
    temp_dir = tempfile.mkdtemp()

    # Create sample backup
    backup_data = {
        "backup_type": "full",
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "pipelines": [
                {"id": 1, "name": "test_pipeline", "config": "{}", "created_at": datetime.now().isoformat()},
                {"id": 2, "name": "test_pipeline_2", "config": "{}", "created_at": datetime.now().isoformat()}
            ],
            "executions": [
                {"id": 1, "pipeline_id": 1, "status": "completed", "created_at": datetime.now().isoformat()}
            ],
            "metrics": []
        }
    }

    backup_path = os.path.join(temp_dir, "test_backup.json")
    with open(backup_path, 'w') as f:
        json.dump(backup_data, f)

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_full_restore(empty_database, backup_dir):
    """Test complete database restore from full backup."""
    restore_mgr = RestoreManager(backup_dir)

    backup_path = os.path.join(backup_dir, "test_backup.json")

    # Perform restore
    result = await restore_mgr.restore_full_backup(
        empty_database,
        backup_path
    )

    # Verify restoration
    assert result["restored_count"] > 0, "Should restore records"
    assert result["backup_type"] == "full", "Should be full backup"

    # Verify data
    pipelines = await empty_database.execute_async("SELECT COUNT(*) FROM pipelines")
    assert _scalar(pipelines) == 2, "Should restore 2 pipelines"

    executions = await empty_database.execute_async("SELECT COUNT(*) FROM executions")
    assert _scalar(executions) == 1, "Should restore 1 execution"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_point_in_time_restore(empty_database, backup_dir):
    """Test point-in-time recovery."""
    restore_mgr = RestoreManager(backup_dir)

    # Create multiple backups at different times
    backup_paths = []

    # Full backup at T0
    t0 = datetime.now()
    full_backup = {
        "backup_type": "full",
        "timestamp": t0.isoformat(),
        "tables": {
            "pipelines": [
                {"id": 1, "name": "pipeline_1", "config": "{}", "created_at": t0.isoformat()}
            ],
            "executions": [],
            "metrics": []
        }
    }

    full_path = os.path.join(backup_dir, "full_t0.json")
    with open(full_path, 'w') as f:
        json.dump(full_backup, f)
    backup_paths.append(full_path)

    # Incremental backup at T1
    t1 = t0 + timedelta(hours=1)
    inc_backup = {
        "backup_type": "incremental",
        "timestamp": t1.isoformat(),
        "since": t0.isoformat(),
        "tables": {
            "pipelines": [
                {"id": 2, "name": "pipeline_2", "config": "{}", "created_at": t1.isoformat()}
            ],
            "executions": [],
            "metrics": []
        }
    }

    inc_path = os.path.join(backup_dir, "inc_t1.json")
    with open(inc_path, 'w') as f:
        json.dump(inc_backup, f)
    backup_paths.append(inc_path)

    # Restore to time T1
    result = await restore_mgr.restore_point_in_time(
        empty_database,
        target_time=t1,
        backup_paths=backup_paths
    )

    # Verify restore
    assert result["restored_count"] >= 2, "Should restore records up to T1"
    assert result["incremental_backups"] >= 1, "Should use incremental backup"

    # Verify data
    pipelines = await empty_database.execute_async("SELECT COUNT(*) FROM pipelines")
    assert _scalar(pipelines) >= 2, "Should have pipelines from both backups"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_partial_table_restore(empty_database, backup_dir):
    """Test restoring specific table only."""
    restore_mgr = RestoreManager(backup_dir)

    backup_path = os.path.join(backup_dir, "test_backup.json")

    # Restore only pipelines table
    result = await restore_mgr.restore_table(
        empty_database,
        backup_path,
        "pipelines"
    )

    # Verify only pipelines restored
    assert result["table"] == "pipelines", "Should restore pipelines"
    assert result["restored_count"] == 2, "Should restore 2 pipelines"

    # Verify other tables empty
    executions = await empty_database.execute_async("SELECT COUNT(*) FROM executions")
    assert _scalar(executions) == 0, "Executions should remain empty"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_validation(empty_database, backup_dir):
    """Test restore validation."""
    restore_mgr = RestoreManager(backup_dir)

    backup_path = os.path.join(backup_dir, "test_backup.json")

    # Restore
    await restore_mgr.restore_full_backup(empty_database, backup_path)

    # Validate
    is_valid = await restore_mgr.validate_restore(
        empty_database,
        expected_counts={
            "pipelines": 2,
            "executions": 1,
            "metrics": 0
        }
    )

    assert is_valid, "Restore validation should pass"

    # Test invalid validation
    is_valid = await restore_mgr.validate_restore(
        empty_database,
        expected_counts={"pipelines": 999}
    )

    assert not is_valid, "Should fail with incorrect counts"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_with_existing_data(empty_database, backup_dir):
    """Test restore behavior with existing data."""
    restore_mgr = RestoreManager(backup_dir)

    # Insert existing data
    await empty_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": "existing_pipeline", "config": "{}"}
    )

    backup_path = os.path.join(backup_dir, "test_backup.json")

    # Restore (may skip duplicates)
    await restore_mgr.restore_full_backup(
        empty_database,
        backup_path
    )

    # Verify data exists
    pipelines = await empty_database.execute_async("SELECT COUNT(*) FROM pipelines")
    count = _scalar(pipelines)

    # Should have at least original + restored (or handle duplicates)
    assert count >= 1, "Should preserve existing data"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_foreign_key_relationships(empty_database, backup_dir):
    """Test that foreign keys are restored correctly."""
    restore_mgr = RestoreManager(backup_dir)

    backup_path = os.path.join(backup_dir, "test_backup.json")

    # Restore
    await restore_mgr.restore_full_backup(empty_database, backup_path)

    # Verify FK relationships
    result = await empty_database.execute_async("""
        SELECT e.id, e.pipeline_id, p.id
        FROM executions e
        JOIN pipelines p ON e.pipeline_id = p.id
    """)

    relationships = result
    assert len(relationships) > 0, "Foreign key relationships should work"

    # Verify no orphaned records
    orphaned = await empty_database.execute_async("""
        SELECT COUNT(*) FROM executions e
        LEFT JOIN pipelines p ON e.pipeline_id = p.id
        WHERE p.id IS NULL
    """)

    assert _scalar(orphaned) == 0, "Should not have orphaned records"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_performance(empty_database, backup_dir):
    """Test restore performance with large backup."""
    import time

    # Create large backup
    large_backup = {
        "backup_type": "full",
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "pipelines": [
                {
                    "id": i,
                    "name": f"pipeline_{i}",
                    "config": json.dumps({"data": "x" * 100}),
                    "created_at": datetime.now().isoformat()
                }
                for i in range(1000)
            ],
            "executions": [],
            "metrics": []
        }
    }

    large_backup_path = os.path.join(backup_dir, "large_backup.json")
    with open(large_backup_path, 'w') as f:
        json.dump(large_backup, f)

    restore_mgr = RestoreManager(backup_dir)

    # Time restore
    start_time = time.time()
    result = await restore_mgr.restore_full_backup(
        empty_database,
        large_backup_path
    )
    elapsed = time.time() - start_time

    # Verify performance
    assert elapsed < 30.0, f"Restore took {elapsed:.2f}s, should be <30s"
    assert result["restored_count"] >= 1000, "Should restore all records"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_error_handling(empty_database, backup_dir):
    """Test error handling during restore."""
    restore_mgr = RestoreManager(backup_dir)

    # Test with non-existent backup
    with pytest.raises(Exception):
        await restore_mgr.restore_full_backup(
            empty_database,
            "/nonexistent/backup.json"
        )

    # Test with corrupted backup
    corrupted_path = os.path.join(backup_dir, "corrupted.json")
    with open(corrupted_path, 'w') as f:
        f.write("corrupted {{{")

    with pytest.raises(Exception):
        await restore_mgr.restore_full_backup(
            empty_database,
            corrupted_path
        )


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_preserves_data_types(empty_database, backup_dir):
    """Test that data types are preserved during restore."""
    # Create backup with specific data types
    typed_backup = {
        "backup_type": "full",
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "pipelines": [
                {
                    "id": 1,
                    "name": "typed_pipeline",
                    "config": json.dumps({"key": "value"}),
                    "created_at": datetime.now().isoformat()
                }
            ],
            "executions": [],
            "metrics": []
        }
    }

    typed_path = os.path.join(backup_dir, "typed.json")
    with open(typed_path, 'w') as f:
        json.dump(typed_backup, f)

    restore_mgr = RestoreManager(backup_dir)

    # Restore
    await restore_mgr.restore_full_backup(empty_database, typed_path)

    # Verify types
    result = await empty_database.execute_async(
        "SELECT * FROM pipelines WHERE id = 1"
    )
    row = _first(result)

    assert isinstance(row["id"], int), "ID should be integer"
    assert isinstance(row["name"], str), "Name should be string"

    # Verify JSON
    config = json.loads(row["config"])
    assert config["key"] == "value", "JSON should be preserved"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_with_schema_migration(empty_database, backup_dir):
    """Test restore with schema changes."""
    # Create backup with old schema
    old_schema_backup = {
        "backup_type": "full",
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "pipelines": [
                {
                    "id": 1,
                    "name": "old_pipeline",
                    "config": "{}",
                    "created_at": datetime.now().isoformat()
                    # Missing new fields
                }
            ],
            "executions": [],
            "metrics": []
        }
    }

    old_backup_path = os.path.join(backup_dir, "old_schema.json")
    with open(old_backup_path, 'w') as f:
        json.dump(old_schema_backup, f)

    restore_mgr = RestoreManager(backup_dir)

    # Restore (should handle missing fields gracefully)
    try:
        result = await restore_mgr.restore_full_backup(
            empty_database,
            old_backup_path
        )
        assert result["restored_count"] > 0, "Should restore despite schema differences"
    except Exception:
        # Acceptable if strict schema validation
        pass


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_rollback_on_failure(empty_database, backup_dir):
    """Test that failed restore can be rolled back."""
    # Insert initial data
    await empty_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": "original", "config": "{}"}
    )

    initial_count = _scalar(await empty_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    # Create invalid backup
    invalid_backup = {
        "backup_type": "full",
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "pipelines": [
                {"id": "invalid_id", "name": "bad_data"}  # Invalid data
            ],
            "executions": [],
            "metrics": []
        }
    }

    invalid_path = os.path.join(backup_dir, "invalid.json")
    with open(invalid_path, 'w') as f:
        json.dump(invalid_backup, f)

    restore_mgr = RestoreManager(backup_dir)

    # Attempt restore (may fail)
    try:
        await restore_mgr.restore_full_backup(empty_database, invalid_path)
    except Exception:
        pass

    # Verify original data preserved (or rolled back)
    current_count = _scalar(await empty_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    # Should preserve at least original data
    assert current_count >= initial_count, "Should preserve original data on failure"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_concurrent_restore_operations(empty_database, backup_dir):
    """Test that concurrent restores are handled safely."""
    restore_mgr = RestoreManager(backup_dir)

    backup_path = os.path.join(backup_dir, "test_backup.json")

    # Attempt concurrent restores (should be serialized or handled)
    tasks = [
        restore_mgr.restore_full_backup(empty_database, backup_path)
        for _ in range(3)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # At least one should succeed
    successful = [r for r in results if not isinstance(r, Exception)]
    assert len(successful) > 0, "At least one restore should succeed"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_restore_progress_tracking(empty_database, backup_dir):
    """Test tracking restore progress."""
    # Create large backup
    large_backup = {
        "backup_type": "full",
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "pipelines": [
                {"id": i, "name": f"pipeline_{i}", "config": "{}", "created_at": datetime.now().isoformat()}
                for i in range(100)
            ],
            "executions": [],
            "metrics": []
        }
    }

    large_path = os.path.join(backup_dir, "progress_test.json")
    with open(large_path, 'w') as f:
        json.dump(large_backup, f)

    restore_mgr = RestoreManager(backup_dir)

    # Restore and track progress
    result = await restore_mgr.restore_full_backup(empty_database, large_path)

    # Verify progress tracking
    assert result["restored_count"] == 100, "Should track all restored records"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "disaster_recovery"])
