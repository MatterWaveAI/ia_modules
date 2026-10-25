"""
Test script for importing pipelines with step modules into database

This script tests the complete import flow:
1. Import pipeline JSON
2. Scan and import Python step modules
3. Verify database storage
4. Test step loading from database
"""

import asyncio
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nexusql import DatabaseManager
from ia_modules.pipeline.importer import PipelineImportService
from ia_modules.pipeline.db_step_loader import DatabaseStepLoader
from ia_modules.database import MIGRATIONS_DIR


async def test_pipeline_import():
    """Test importing pipelines from tests/pipelines directory"""

    print("=" * 60)
    print("Pipeline Step Module Import Test")
    print("=" * 60)

    # Initialize database (in-memory for testing)
    print("\n1. Initializing database...")
    db = DatabaseManager("sqlite:///:memory:")
    await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
    print("   [OK] Database initialized")

    # Create importer pointing to tests/pipelines
    pipelines_dir = Path(__file__).parent / "pipelines"
    print(f"\n2. Scanning for pipelines in: {pipelines_dir}")

    importer = PipelineImportService(
        db_provider=db,
        pipelines_dir=str(pipelines_dir)
    )

    # Import all pipelines
    print("\n3. Importing pipelines...")
    results = await importer.import_all_pipelines(clear_existing=True)

    print("\n   Import Results:")
    print(f"   - Imported: {results['imported']}")
    print(f"   - Updated:  {results['updated']}")
    print(f"   - Skipped:  {results['skipped']}")
    print(f"   - Errors:   {results['errors']}")

    if results['details']:
        print("\n   Details:")
        for detail in results['details']:
            action = detail['action']
            file_name = detail['file']
            pipeline_id = detail.get('pipeline_id', 'N/A')
            print(f"   - [{action.upper()}] {file_name} (ID: {pipeline_id})")

    # Verify step modules were imported
    print("\n4. Verifying step modules in database...")
    query = """
    SELECT
        p.name as pipeline_name,
        psm.step_id,
        psm.class_name,
        psm.module_path,
        LENGTH(psm.source_code) as code_length,
        psm.content_hash
    FROM pipeline_step_modules psm
    JOIN pipelines p ON psm.pipeline_id = p.id
    WHERE psm.is_active = 1
    ORDER BY p.name, psm.step_id
    """

    result = db.fetch_all(query)

    # Handle both list and object responses
    data = None
    if isinstance(result, list):
        data = result
    elif hasattr(result, 'data'):
        data = result.data

    if data and len(data) > 0:
        print(f"\n   Found {len(data)} step modules:")
        print(f"\n   {'Pipeline':<25} {'Step ID':<15} {'Class':<15} {'Code Size':<10} {'Hash'}")
        print(f"   {'-' * 90}")

        for row in data:
            print(f"   {row['pipeline_name']:<25} {row['step_id']:<15} {row['class_name']:<15} {row['code_length']:<10} {row['content_hash'][:8]}")
    else:
        print("   ⚠ No step modules found in database")

    # Test loading a step from database
    print("\n5. Testing step loading from database...")

    if data and len(data) > 0:
        # Get first step
        first_step = data[0]
        module_path = first_step['module_path']
        class_name = first_step['class_name']

        print(f"   Loading: {module_path}.{class_name}")

        loader = DatabaseStepLoader(db)

        try:
            step_class = await loader.load_step_class(module_path, class_name)
            print(f"   [OK] Successfully loaded step class: {step_class.__name__}")

            # Try to instantiate
            step_instance = step_class("test_step", {})
            print("   [OK] Successfully instantiated step")

            # Try to run
            result = await step_instance.run({"topic": "database test"})
            print("   [OK] Successfully executed step")
            print(f"   Output: {result}")

        except Exception as e:
            print(f"   [ERROR] Error loading step: {e}")
    else:
        print("   ⚠ Skipping load test (no steps found)")

    # Test validation
    print("\n6. Testing code validation...")

    valid_code = '''
from ia_modules.pipeline.core import Step
from typing import Dict, Any

class TestStep(Step):
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "success"}
'''

    invalid_code = '''
import os
os.system("echo 'dangerous'")
'''

    loader = DatabaseStepLoader(db, enable_cache=False)

    try:
        loader._validate_source_code(valid_code)
        print("   [OK] Valid code passed validation")
    except Exception as e:
        print(f"   [ERROR] Valid code rejected: {e}")

    try:
        loader._validate_source_code(invalid_code)
        print("   [ERROR] Invalid code passed validation (should have failed!)")
    except ValueError as e:
        print(f"   [OK] Invalid code rejected: {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

    # Cleanup
    db.disconnect()


if __name__ == "__main__":
    asyncio.run(test_pipeline_import())
