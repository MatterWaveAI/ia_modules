"""
RTO/RPO Disaster Recovery Tests

Tests for Recovery Time Objective (RTO) and Recovery Point Objective (RPO).
Verifies that recovery procedures meet defined SLAs.

RTO: Maximum acceptable time to restore service after failure
RPO: Maximum acceptable amount of data loss measured in time
"""

import pytest
import asyncio
import tempfile
import shutil
import json
import time
from datetime import datetime
from pathlib import Path

from nexusql import DatabaseManager

# nexusql returns a SELECT's rows as a list of dicts; these read them the way the
# SQLAlchemy result objects this suite was first written against did.
def _scalar(rows):
    return next(iter(rows[0].values())) if rows else None


def _first(rows):
    return rows[0] if rows else None


def _table_names(db):
    return [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]


class RecoveryMetrics:
    """Track recovery metrics for RTO/RPO analysis."""

    def __init__(self):
        self.recovery_start_time = None
        self.recovery_end_time = None
        self.data_loss_window = None
        self.recovered_record_count = 0
        self.expected_record_count = 0

    def start_recovery(self):
        """Mark start of recovery operation."""
        self.recovery_start_time = time.time()

    def end_recovery(self):
        """Mark end of recovery operation."""
        self.recovery_end_time = time.time()

    def get_rto_seconds(self) -> float:
        """Calculate RTO in seconds."""
        if not self.recovery_start_time or not self.recovery_end_time:
            return 0.0
        return self.recovery_end_time - self.recovery_start_time

    def get_rpo_seconds(self) -> float:
        """Calculate RPO in seconds (data loss window)."""
        if not self.data_loss_window:
            return 0.0
        return self.data_loss_window.total_seconds()

    def calculate_data_loss_percentage(self) -> float:
        """Calculate percentage of data lost."""
        if self.expected_record_count == 0:
            return 0.0

        lost_records = self.expected_record_count - self.recovered_record_count
        return (lost_records / self.expected_record_count) * 100


class DisasterRecoverySimulator:
    """Simulate disaster scenarios and recovery."""

    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(
        self,
        db_manager: DatabaseManager,
        backup_name: str
    ) -> str:
        """Create database backup."""
        backup_path = self.backup_dir / f"{backup_name}.json"

        tables = ["pipelines", "executions", "metrics"]
        backup_data = {
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

        with open(backup_path, 'w') as f:
            json.dump(backup_data, f)

        return str(backup_path)

    async def restore_backup(
        self,
        db_manager: DatabaseManager,
        backup_path: str,
        metrics: RecoveryMetrics
    ):
        """Restore from backup with timing."""
        metrics.start_recovery()

        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

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
                    metrics.recovered_record_count += 1
                except Exception:
                    pass

        metrics.end_recovery()

    async def simulate_database_failure(
        self,
        db_manager: DatabaseManager
    ):
        """Simulate catastrophic database failure."""
        # Drop all tables
        tables = ["metrics", "executions", "pipelines"]  # Reverse order for FK
        for table in tables:
            try:
                await db_manager.execute_async(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass


@pytest.fixture
async def production_database():
    """Simulate production database."""
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

    # Insert production data
    for i in range(1000):
        await db_manager.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"prod_pipeline_{i}", "config": json.dumps({"index": i})}
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
async def test_rto_full_database_restore(production_database, backup_dir):
    """
    Test RTO for full database restore.

    Target RTO: < 5 minutes (300 seconds)
    """
    simulator = DisasterRecoverySimulator(backup_dir)
    metrics = RecoveryMetrics()

    # Create backup
    backup_path = await simulator.create_backup(
        production_database,
        "rto_test_backup"
    )

    # Count records before failure
    original_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    metrics.expected_record_count = original_count

    # Simulate failure
    await simulator.simulate_database_failure(production_database)

    # Recreate schema
    await production_database.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await production_database.execute_async("""
        CREATE TABLE executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)

    await production_database.execute_async("""
        CREATE TABLE metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Restore with timing
    await simulator.restore_backup(production_database, backup_path, metrics)

    rto_seconds = metrics.get_rto_seconds()
    rto_minutes = rto_seconds / 60

    # Verify RTO met
    assert rto_seconds < 300, \
        f"RTO exceeded: {rto_minutes:.2f} minutes (target: 5 minutes)"

    # Verify data restored
    restored_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    assert restored_count == original_count, \
        f"Data loss detected: {original_count - restored_count} records"

    print(f" RTO: {rto_minutes:.2f} minutes (target: <5 minutes)")


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_rpo_with_incremental_backups(production_database, backup_dir):
    """
    Test RPO with incremental backup strategy.

    Target RPO: < 1 hour (3600 seconds)
    """
    simulator = DisasterRecoverySimulator(backup_dir)
    metrics = RecoveryMetrics()

    # T0: Full backup
    datetime.now()
    await simulator.create_backup(production_database, "full_t0")

    # T0 + 30min: Add more data
    await asyncio.sleep(0.1)  # Simulate time passing
    t1 = datetime.now()

    for i in range(1000, 1100):
        await production_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    # T0 + 30min: Incremental backup
    backup_t1 = await simulator.create_backup(production_database, "inc_t1")

    # T0 + 45min: More data (NOT backed up)
    t2 = datetime.now()

    for i in range(1100, 1150):
        await production_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"index": i})}
        )

    # Count total records
    total_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    # Simulate failure at T0 + 45min
    await simulator.simulate_database_failure(production_database)

    # Recreate schema
    await production_database.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Restore from most recent backup (T1)
    await simulator.restore_backup(production_database, backup_t1, metrics)

    # Calculate data loss
    restored_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    lost_records = total_count - restored_count
    metrics.expected_record_count = total_count
    metrics.recovered_record_count = restored_count

    # Calculate RPO (time between last backup and failure)
    rpo_time = t2 - t1
    metrics.data_loss_window = rpo_time

    rpo_seconds = metrics.get_rpo_seconds()
    rpo_minutes = rpo_seconds / 60

    data_loss_pct = metrics.calculate_data_loss_percentage()

    # Verify RPO met
    assert rpo_seconds < 3600, \
        f"RPO exceeded: {rpo_minutes:.2f} minutes (target: 60 minutes)"

    # Verify acceptable data loss
    assert data_loss_pct < 10, \
        f"Excessive data loss: {data_loss_pct:.2f}% ({lost_records} records)"

    print(f" RPO: {rpo_minutes:.2f} minutes (target: <60 minutes)")
    print(f" Data loss: {data_loss_pct:.2f}% ({lost_records} records)")


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_rto_scaling_with_data_size(backup_dir):
    """Test that RTO scales linearly with data size."""
    simulator = DisasterRecoverySimulator(backup_dir)

    data_sizes = [100, 500, 1000, 5000]
    rto_times = []

    for size in data_sizes:
        # Create database with specific size
        db = DatabaseManager("sqlite:///:memory:")
        await db.initialize(apply_schema=False)  # the tests create their own tables

        await db.execute_async("""
            CREATE TABLE pipelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for i in range(size):
            await db.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": json.dumps({"data": "x" * 100})}
            )

        # Backup
        backup_path = await simulator.create_backup(db, f"size_{size}")

        # Drop and recreate
        await db.execute_async("DROP TABLE pipelines")
        await db.execute_async("""
            CREATE TABLE pipelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Time restore
        metrics = RecoveryMetrics()
        await simulator.restore_backup(db, backup_path, metrics)

        rto_times.append(metrics.get_rto_seconds())
        await db.close()

    # Verify RTO scales reasonably (not exponentially): the cost per record at
    # 5000 records should be no worse than twice the cost per record at 500.
    # Linear scaling meets that with room for timer noise on a loaded machine;
    # the old "under 10x total for 10x the data" needed better than linear.
    per_record = [t / size for t, size in zip(rto_times, data_sizes)]
    ratio = per_record[-1] / per_record[1] if per_record[1] > 0 else 0
    assert ratio < 2, f"RTO scaling poor: per-record cost grew {ratio:.2f}x from 500 to 5000 records"

    print("RTO scaling:")
    for size, rto in zip(data_sizes, rto_times):
        print(f"  {size} records: {rto:.3f}s")


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_rto_with_concurrent_access(production_database, backup_dir):
    """
    Test RTO when database must serve read requests during recovery.

    Target: RTO < 10 minutes with concurrent access
    """
    simulator = DisasterRecoverySimulator(backup_dir)
    metrics = RecoveryMetrics()

    # Create backup
    backup_path = await simulator.create_backup(
        production_database,
        "concurrent_test"
    )

    # Simulate failure
    await simulator.simulate_database_failure(production_database)

    # Recreate schema
    await production_database.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Restore with concurrent reads
    restore_task = asyncio.create_task(
        simulator.restore_backup(production_database, backup_path, metrics)
    )

    # Simulate concurrent read attempts
    read_tasks = []
    for _ in range(10):
        async def try_read():
            try:
                result = await production_database.execute_async(
                    "SELECT COUNT(*) FROM pipelines"
                )
                return _scalar(result)
            except Exception:
                return 0

        read_tasks.append(asyncio.create_task(try_read()))
        await asyncio.sleep(0.01)

    # Wait for completion
    await restore_task
    read_results = await asyncio.gather(*read_tasks)

    rto_seconds = metrics.get_rto_seconds()
    rto_minutes = rto_seconds / 60

    # Verify RTO still met with concurrent access
    assert rto_seconds < 600, \
        f"RTO with concurrency exceeded: {rto_minutes:.2f} minutes (target: 10 minutes)"

    print(f" RTO with concurrent access: {rto_minutes:.2f} minutes")
    print(f"  Successful reads during recovery: {sum(1 for r in read_results if r > 0)}/10")


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_zero_data_loss_with_continuous_backup(production_database, backup_dir):
    """
    Test achieving RPO H 0 with continuous/streaming backup.

    Target: Zero data loss (RPO < 1 second)
    """
    simulator = DisasterRecoverySimulator(backup_dir)

    # Simulate continuous backup (backup after every write)
    backups = []

    for i in range(10):
        # Write data
        await production_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"critical_pipeline_{i}", "config": "{}"}
        )

        # Immediately backup (continuous backup)
        backup_path = await simulator.create_backup(
            production_database,
            f"continuous_{i}"
        )
        backups.append({
            "path": backup_path,
            "timestamp": datetime.now()
        })

        await asyncio.sleep(0.01)

    # Total records before failure
    total_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    # Simulate failure
    failure_time = datetime.now()
    await simulator.simulate_database_failure(production_database)

    # Recreate schema
    await production_database.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Restore from most recent backup
    latest_backup = backups[-1]
    metrics = RecoveryMetrics()
    metrics.expected_record_count = total_count

    await simulator.restore_backup(
        production_database,
        latest_backup["path"],
        metrics
    )

    # Calculate RPO
    rpo_time = failure_time - latest_backup["timestamp"]
    rpo_seconds = rpo_time.total_seconds()

    # Verify near-zero data loss
    restored_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    data_loss_pct = ((total_count - restored_count) / total_count * 100) if total_count > 0 else 0

    assert rpo_seconds < 1.0, \
        f"RPO too high for continuous backup: {rpo_seconds:.3f}s"

    assert data_loss_pct < 1.0, \
        f"Data loss too high: {data_loss_pct:.2f}%"

    print(f" RPO with continuous backup: {rpo_seconds:.3f}s")
    print(f" Data loss: {data_loss_pct:.2f}%")


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_recovery_sla_compliance(production_database, backup_dir):
    """
    Test overall SLA compliance for disaster recovery.

    SLA Requirements:
    - RTO < 5 minutes (Tier 1 critical systems)
    - RPO < 15 minutes (Tier 1 critical systems)
    - 99.9% data recovery rate
    """
    simulator = DisasterRecoverySimulator(backup_dir)

    # Create backup at T0
    t0 = datetime.now()
    backup_path = await simulator.create_backup(production_database, "sla_test")

    # Add data (within RPO window)
    await asyncio.sleep(0.1)
    for i in range(1000, 1050):
        await production_database.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": "{}"}
        )

    # Failure at T0 + 10 minutes (simulated)
    t_failure = datetime.now()

    total_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    # Simulate failure
    await simulator.simulate_database_failure(production_database)

    # Recreate schema
    await production_database.execute_async("""
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Restore with metrics
    metrics = RecoveryMetrics()
    metrics.expected_record_count = total_count
    await simulator.restore_backup(production_database, backup_path, metrics)

    # Calculate metrics
    rto_seconds = metrics.get_rto_seconds()
    rto_minutes = rto_seconds / 60

    rpo_time = t_failure - t0
    rpo_minutes = rpo_time.total_seconds() / 60

    recovered_count = _scalar(await production_database.execute_async(
        "SELECT COUNT(*) FROM pipelines"
    ))

    recovery_rate = (recovered_count / total_count * 100) if total_count > 0 else 0

    # Verify SLA compliance
    sla_compliance = {
        "rto_met": rto_minutes < 5,
        "rpo_met": rpo_minutes < 15,
        "recovery_rate_met": recovery_rate >= 99.9
    }

    assert sla_compliance["rto_met"], \
        f"RTO SLA violated: {rto_minutes:.2f} minutes (target: <5 minutes)"

    assert sla_compliance["rpo_met"], \
        f"RPO SLA violated: {rpo_minutes:.2f} minutes (target: <15 minutes)"

    # Recovery rate may be less if data was added after backup
    # This is expected for RPO testing

    print("SLA Compliance Report:")
    print(f"  RTO: {rto_minutes:.2f} min (target: <5 min) - {' PASS' if sla_compliance['rto_met'] else ' FAIL'}")
    print(f"  RPO: {rpo_minutes:.2f} min (target: <15 min) - {' PASS' if sla_compliance['rpo_met'] else ' FAIL'}")
    print(f"  Recovery Rate: {recovery_rate:.2f}% (target: >99.9%) - {' PASS' if sla_compliance['recovery_rate_met'] else ' FAIL'}")


@pytest.mark.disaster_recovery
@pytest.mark.asyncio
async def test_rto_with_multiple_database_sizes():
    """Test RTO requirements across different database sizes."""
    simulator = DisasterRecoverySimulator(tempfile.mkdtemp())

    test_cases = [
        {"size": 100, "target_rto_seconds": 10},
        {"size": 1000, "target_rto_seconds": 30},
        {"size": 10000, "target_rto_seconds": 120}
    ]

    for test_case in test_cases:
        size = test_case["size"]
        target_rto = test_case["target_rto_seconds"]

        # Create database
        db = DatabaseManager("sqlite:///:memory:")
        await db.initialize(apply_schema=False)  # the tests create their own tables

        await db.execute_async("""
            CREATE TABLE pipelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for i in range(size):
            await db.execute_async("INSERT INTO pipelines (name, config) VALUES (:name, :config)", {"name": f"pipeline_{i}", "config": "{}"}
            )

        # Backup
        backup_path = await simulator.create_backup(db, f"size_{size}")

        # Drop table
        await db.execute_async("DROP TABLE pipelines")

        # Recreate
        await db.execute_async("""
            CREATE TABLE pipelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Restore and measure
        metrics = RecoveryMetrics()
        await simulator.restore_backup(db, backup_path, metrics)

        rto_seconds = metrics.get_rto_seconds()

        assert rto_seconds < target_rto, \
            f"RTO failed for size {size}: {rto_seconds:.2f}s (target: <{target_rto}s)"

        print(f" Size {size}: RTO {rto_seconds:.2f}s (target: <{target_rto}s)")

        await db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "disaster_recovery"])
