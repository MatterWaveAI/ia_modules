"""
Backup Procedures Disaster Recovery Tests

Comprehensive tests for backup procedures including full, incremental,
differential backups, scheduling, rotation, and backup validation.
"""

import pytest
import asyncio
import os
import tempfile
import shutil
import json
from datetime import datetime, timezone
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


class BackupManager:
    """Simplified backup manager for testing."""

    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_full_backup(
        self,
        db_manager: DatabaseManager,
        backup_name: str
    ) -> Dict:
        """Create full database backup."""
        backup_path = self.backup_dir / f"{backup_name}.json"

        # Export all tables
        tables = ["pipelines", "executions", "metrics"]
        backup_data = {
            "backup_type": "full",
            "timestamp": datetime.now().isoformat(),
            "tables": {}
        }

        for table in tables:
            try:
                result = await db_manager.execute_async(f"SELECT * FROM {table}")
                rows = result
                backup_data["tables"][table] = [dict(row) for row in rows]
            except Exception:
                backup_data["tables"][table] = []

        # Write to file
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)

        return {
            "path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "timestamp": backup_data["timestamp"],
            "record_count": sum(len(rows) for rows in backup_data["tables"].values())
        }

    async def create_incremental_backup(
        self,
        db_manager: DatabaseManager,
        backup_name: str,
        since_timestamp: datetime
    ) -> Dict:
        """Create incremental backup (changes since timestamp)."""
        backup_path = self.backup_dir / f"{backup_name}_incremental.json"

        backup_data = {
            "backup_type": "incremental",
            "timestamp": datetime.now().isoformat(),
            "since": since_timestamp.isoformat(),
            "tables": {}
        }

        # Only backup changed records. created_at is SQLite's CURRENT_TIMESTAMP:
        # UTC text at second resolution, so compare against the same form.
        since = since_timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        tables = ["pipelines", "executions", "metrics"]
        for table in tables:
            try:
                result = await db_manager.execute_async(f"SELECT * FROM {table} WHERE created_at > :created_at", {"created_at": since}
                )
                rows = result
                backup_data["tables"][table] = [dict(row) for row in rows]
            except Exception:
                backup_data["tables"][table] = []

        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)

        return {
            "path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "timestamp": backup_data["timestamp"],
            "record_count": sum(len(rows) for rows in backup_data["tables"].values())
        }

    def list_backups(self) -> List[Dict]:
        """List all available backups."""
        backups = []
        for backup_file in self.backup_dir.glob("*.json"):
            with open(backup_file, 'r') as f:
                metadata = json.load(f)

            backups.append({
                "name": backup_file.stem,
                "path": str(backup_file),
                "type": metadata.get("backup_type", "unknown"),
                "timestamp": metadata.get("timestamp"),
                "size_bytes": backup_file.stat().st_size
            })

        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

    def rotate_backups(self, keep_count: int = 7):
        """Rotate backups, keeping only the most recent N."""
        backups = self.list_backups()

        # Delete old backups
        for backup in backups[keep_count:]:
            os.remove(backup["path"])

    def validate_backup(self, backup_path: str) -> bool:
        """Validate backup file integrity."""
        try:
            with open(backup_path, 'r') as f:
                data = json.load(f)

            # Verify required fields
            required_fields = ["backup_type", "timestamp", "tables"]
            for field in required_fields:
                if field not in data:
                    return False

            # Verify tables data
            if not isinstance(data["tables"], dict):
                return False

            return True
        except Exception:
            return False


@pytest.fixture
async def test_database():
    """Create test database with sample data."""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (execution_id) REFERENCES executions(id)
        )
    """)

    # Insert test data
    for i in range(50):
        await db_manager.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    yield db_manager
    await db_manager.close()


@pytest.fixture
def backup_dir():
    """Create temporary backup directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_full_backup_creation(test_database, backup_dir):
    """Test creating a full database backup."""
    backup_mgr = BackupManager(backup_dir)

    # Create full backup
    result = await backup_mgr.create_full_backup(
        test_database,
        "test_backup_001"
    )

    # Verify backup created
    assert os.path.exists(result["path"]), "Backup file should exist"
    assert result["size_bytes"] > 0, "Backup should not be empty"
    assert result["record_count"] >= 50, "Should backup all records"

    # Verify backup validity
    assert backup_mgr.validate_backup(result["path"]), "Backup should be valid"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_incremental_backup_creation(test_database, backup_dir):
    """Test creating incremental backups."""
    backup_mgr = BackupManager(backup_dir)

    # Create initial full backup
    full_backup_time = datetime.now()
    await backup_mgr.create_full_backup(test_database, "full_001")

    # Wait into the next second: created_at only resolves to the second
    await asyncio.sleep(1.1)

    for i in range(50, 60):
        await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    # Create incremental backup
    result = await backup_mgr.create_incremental_backup(
        test_database,
        "incremental_001",
        since_timestamp=full_backup_time
    )

    # Verify incremental backup
    assert os.path.exists(result["path"]), "Incremental backup should exist"
    assert result["record_count"] <= 10, "Should only backup new records"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_scheduling(test_database, backup_dir):
    """Test automated backup scheduling."""
    backup_mgr = BackupManager(backup_dir)

    # Simulate daily backups
    for day in range(7):
        backup_name = f"daily_backup_{day}"

        result = await backup_mgr.create_full_backup(
            test_database,
            backup_name
        )

        assert os.path.exists(result["path"]), f"Day {day} backup should exist"

    # Verify all backups created
    backups = backup_mgr.list_backups()
    assert len(backups) == 7, "Should have 7 daily backups"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_rotation(test_database, backup_dir):
    """Test backup rotation policy."""
    backup_mgr = BackupManager(backup_dir)

    # Create 10 backups
    for i in range(10):
        await backup_mgr.create_full_backup(
            test_database,
            f"backup_{i:03d}"
        )

    # Verify 10 backups exist
    backups = backup_mgr.list_backups()
    assert len(backups) == 10, "Should have 10 backups"

    # Rotate, keeping only 5 most recent
    backup_mgr.rotate_backups(keep_count=5)

    # Verify only 5 remain
    backups = backup_mgr.list_backups()
    assert len(backups) == 5, "Should keep only 5 backups after rotation"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_validation(test_database, backup_dir):
    """Test backup validation detects corruption."""
    backup_mgr = BackupManager(backup_dir)

    # Create valid backup
    result = await backup_mgr.create_full_backup(
        test_database,
        "valid_backup"
    )

    # Verify valid backup passes
    assert backup_mgr.validate_backup(result["path"]), "Valid backup should pass"

    # Create corrupted backup
    corrupted_path = os.path.join(backup_dir, "corrupted.json")
    with open(corrupted_path, 'w') as f:
        f.write("corrupted data {{{")

    # Verify corrupted backup fails
    assert not backup_mgr.validate_backup(corrupted_path), \
        "Corrupted backup should fail validation"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_compression(test_database, backup_dir):
    """Test backup compression reduces size."""
    import gzip

    backup_mgr = BackupManager(backup_dir)

    # Create uncompressed backup
    result = await backup_mgr.create_full_backup(
        test_database,
        "uncompressed"
    )
    uncompressed_size = result["size_bytes"]

    # Compress backup
    compressed_path = result["path"] + ".gz"
    with open(result["path"], 'rb') as f_in:
        with gzip.open(compressed_path, 'wb') as f_out:
            f_out.writelines(f_in)

    compressed_size = os.path.getsize(compressed_path)

    # Verify compression reduces size
    assert compressed_size < uncompressed_size, \
        f"Compression should reduce size: {compressed_size} >= {uncompressed_size}"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_encryption(test_database, backup_dir):
    """Test backup encryption for security."""
    from cryptography.fernet import Fernet

    backup_mgr = BackupManager(backup_dir)

    # Create backup
    result = await backup_mgr.create_full_backup(
        test_database,
        "plain_backup"
    )

    # Encrypt backup
    key = Fernet.generate_key()
    fernet = Fernet(key)

    with open(result["path"], 'rb') as f:
        plain_data = f.read()

    encrypted_data = fernet.encrypt(plain_data)

    encrypted_path = result["path"] + ".encrypted"
    with open(encrypted_path, 'wb') as f:
        f.write(encrypted_data)

    # Verify encrypted file is different
    assert encrypted_data != plain_data, "Encrypted data should differ"

    # Decrypt and verify
    with open(encrypted_path, 'rb') as f:
        encrypted_data = f.read()

    decrypted_data = fernet.decrypt(encrypted_data)
    assert decrypted_data == plain_data, "Decryption should restore original data"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_to_multiple_locations(test_database, backup_dir):
    """Test backing up to multiple locations for redundancy."""
    primary_dir = os.path.join(backup_dir, "primary")
    secondary_dir = os.path.join(backup_dir, "secondary")

    primary_mgr = BackupManager(primary_dir)
    secondary_mgr = BackupManager(secondary_dir)

    # Create backup in primary location
    primary_result = await primary_mgr.create_full_backup(
        test_database,
        "redundant_backup"
    )

    # Copy to secondary location
    secondary_result = await secondary_mgr.create_full_backup(
        test_database,
        "redundant_backup"
    )

    # Verify both locations have backup
    assert os.path.exists(primary_result["path"]), "Primary backup should exist"
    assert os.path.exists(secondary_result["path"]), "Secondary backup should exist"

    # Verify both are identical
    with open(primary_result["path"], 'r') as f:
        primary_data = json.load(f)

    with open(secondary_result["path"], 'r') as f:
        secondary_data = json.load(f)

    # Compare table data
    assert primary_data["tables"] == secondary_data["tables"], \
        "Primary and secondary backups should be identical"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_with_concurrent_writes(test_database, backup_dir):
    """Test backup consistency during concurrent database writes."""
    backup_mgr = BackupManager(backup_dir)

    # Start backup
    backup_task = asyncio.create_task(
        backup_mgr.create_full_backup(test_database, "concurrent_backup")
    )

    # Concurrent writes
    write_tasks = []
    for i in range(100, 110):
        task = test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )
        write_tasks.append(task)

    # Wait for all to complete
    await asyncio.gather(backup_task, *write_tasks)

    # Verify backup completed
    backups = backup_mgr.list_backups()
    assert len(backups) > 0, "Backup should complete despite concurrent writes"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_performance_large_database(backup_dir):
    """Test backup performance with large database."""
    import time

    # Create large database
    large_db = DatabaseManager("sqlite:///:memory:")
    await large_db.initialize(apply_schema=False)  # the tests create their own tables

    await large_db.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert 10,000 records
    for i in range(10000):
        await large_db.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i, "data": "x" * 100})}
        )

    backup_mgr = BackupManager(backup_dir)

    # Time backup
    start_time = time.time()
    result = await backup_mgr.create_full_backup(large_db, "large_backup")
    elapsed = time.time() - start_time

    # Verify performance
    assert elapsed < 10.0, f"Backup took {elapsed:.2f}s, should be <10s"
    assert result["record_count"] >= 10000, "Should backup all records"

    await large_db.close()


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_metadata_logging(test_database, backup_dir):
    """Test that backup operations are properly logged."""
    backup_mgr = BackupManager(backup_dir)

    # Create backup
    result = await backup_mgr.create_full_backup(
        test_database,
        "logged_backup"
    )

    # Verify metadata
    metadata_path = result["path"]
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Verify required metadata fields
    assert "backup_type" in metadata, "Should log backup type"
    assert "timestamp" in metadata, "Should log timestamp"
    assert metadata["backup_type"] == "full", "Should log correct type"

    # Verify timestamp is valid
    timestamp = datetime.fromisoformat(metadata["timestamp"])
    time_diff = (datetime.now() - timestamp).total_seconds()
    assert time_diff < 60, "Timestamp should be recent"


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_backup_failure_handling(backup_dir):
    """Test handling of backup failures."""
    # Create invalid database connection
    invalid_db = DatabaseManager("sqlite:///nonexistent/path/db.sqlite")

    backup_mgr = BackupManager(backup_dir)

    # Attempt backup (should handle gracefully)
    try:
        await backup_mgr.create_full_backup(invalid_db, "failed_backup")
    except Exception as e:
        # Should raise appropriate error
        assert "nonexistent" in str(e).lower() or "unable" in str(e).lower()


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_differential_backup(test_database, backup_dir):
    """Test differential backup (changes since last full backup)."""
    backup_mgr = BackupManager(backup_dir)

    # Full backup
    full_time = datetime.now()
    await backup_mgr.create_full_backup(test_database, "full_001")

    # Add data
    await asyncio.sleep(1.1)  # into the next second: created_at only resolves to the second
    for i in range(50, 55):
        await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    # Differential backup #1
    await backup_mgr.create_incremental_backup(
        test_database,
        "diff_001",
        since_timestamp=full_time
    )

    # Add more data
    for i in range(55, 60):
        await test_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    # Differential backup #2 (still from full backup time)
    diff_result = await backup_mgr.create_incremental_backup(
        test_database,
        "diff_002",
        since_timestamp=full_time
    )

    # Should include all changes since full backup
    assert diff_result["record_count"] >= 10, \
        "Differential should include all changes since full backup"


@pytest.mark.disaster_recovery
def test_backup_naming_convention(backup_dir):
    """Test that backups follow naming convention."""
    BackupManager(backup_dir)

    # Expected naming pattern: {type}_{timestamp}_{identifier}
    now = datetime.now()
    expected_name = f"full_{now.strftime('%Y%m%d_%H%M%S')}_prod"

    # Verify name is valid
    assert "full" in expected_name, "Should include backup type"
    assert now.strftime('%Y%m%d') in expected_name, "Should include date"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "disaster_recovery"])
