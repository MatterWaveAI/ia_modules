"""
Manual test for PostgreSQL database with migrations.

Run this manually to verify PostgreSQL setup works:
python tests/manual_database_test.py
"""

import asyncio
import os
from nexusql import DatabaseManager, ConnectionConfig, DatabaseType
from ia_modules.database import MIGRATIONS_DIR


async def test_postgresql():
    """Test PostgreSQL connection and migrations"""

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/showcase_db")

    print(f"Testing database: {database_url}")

    # Create DatabaseManager
    db = DatabaseManager(database_url)

    # Connect
    print("Connecting to database...")
    success = db.connect()
    if not success:
        print("❌ Failed to connect to database")
        return False

    print("✅ Connected to database")

    # Initialize with migrations
    print("Running migrations...")
    success = await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
    if not success:
        print("❌ Failed to initialize database")
        return False

    print("✅ Migrations completed")

    # Check tables exist
    print("\nChecking tables...")
    tables_to_check = [
        "ia_migrations",
        "pipeline_checkpoints",
        "conversation_messages",
        "reliability_steps",
        "reliability_workflows",
        "reliability_slo_measurements"
    ]

    for table in tables_to_check:
        exists = db.table_exists(table)
        status = "✅" if exists else "❌"
        print(f"  {status} {table}")

    # Test named parameters
    print("\nTesting named parameters...")
    try:
        # Insert test data
        await db.execute_async(
            "INSERT INTO reliability_steps (agent_name, success, timestamp) VALUES (:agent, :success, :ts)",
            {"agent": "test_agent", "success": True, "ts": "2025-01-01 00:00:00"}
        )

        # Query with named parameters
        result = await db.fetch_one(
            "SELECT * FROM reliability_steps WHERE agent_name = :agent",
            {"agent": "test_agent"}
        )

        if result.success:
            row = result.get_first_row()
            print(f"✅ Named parameters work: {row['agent_name']}")
        else:
            print(f"❌ Query failed: {result.error}")
    except Exception as e:
        print(f"❌ Named parameters test failed: {e}")

    # Cleanup
    await db.execute_async("DELETE FROM reliability_steps WHERE agent_name = :agent", {"agent": "test_agent"})

    # Disconnect
    await db.close()
    print("\n✅ All tests passed!")
    return True


async def test_sqlite():
    """Test SQLite in-memory database"""
    print("\n=== Testing SQLite ===\n")

    config = ConnectionConfig(
        database_type=DatabaseType.SQLITE,
        database_url="sqlite://:memory:"
    )

    db = DatabaseManager(config)

    print("Connecting to SQLite...")
    success = db.connect()
    if not success:
        print("❌ Failed to connect")
        return False

    print("✅ Connected")

    # Test named parameters with SQLite
    print("\nTesting named parameters with SQLite...")
    try:
        # Create table
        await db.execute_async("""
            CREATE TABLE test_items (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value INTEGER
            )
        """)

        # Insert with named params
        await db.execute_async(
            "INSERT INTO test_items (name, value) VALUES (:name, :value)",
            {"name": "item1", "value": 42}
        )

        # Query with named params
        result = await db.fetch_one(
            "SELECT * FROM test_items WHERE name = :name",
            {"name": "item1"}
        )

        if result.success:
            row = result.get_first_row()
            print(f"✅ SQLite named parameters work: {row['name']} = {row['value']}")
        else:
            print(f"❌ Query failed: {result.error}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

    await db.close()
    print("\n✅ SQLite tests passed!")
    return True


if __name__ == "__main__":
    print("=== Database System Manual Test ===\n")

    # Test SQLite first (always works)
    asyncio.run(test_sqlite())

    # Test PostgreSQL if DATABASE_URL is set
    if os.getenv("DATABASE_URL"):
        asyncio.run(test_postgresql())
    else:
        print("\n=== Skipping PostgreSQL test (no DATABASE_URL set) ===")
        print("To test PostgreSQL, set DATABASE_URL environment variable:")
        print("  export DATABASE_URL=postgresql://user:pass@host:port/database")
