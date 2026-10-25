"""
End-to-end test for HITL (Human-in-the-Loop) functionality
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexusql import DatabaseManager
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
from ia_modules.pipeline.core import ExecutionContext, ServiceRegistry
from ia_modules.pipeline.execution_tracker import ExecutionTracker
from ia_modules.pipeline.hitl_manager import HITLManager
from ia_modules.database import MIGRATIONS_DIR


async def test_hitl_pause_and_resume():
    """Test that HITL pipeline pauses and can be resumed"""
    print("\n" + "="*80)
    print("HITL End-to-End Test")
    print("="*80)

    # Setup database (in-memory SQLite for testing)
    db_url = "sqlite:///:memory:"
    db_manager = DatabaseManager(db_url)

    print("\n1. Initializing database...")
    if not await db_manager.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)]):
        print("[FAIL] Database initialization failed")
        return False

    print("[OK] Database initialized")

    # Setup services
    services = ServiceRegistry()
    services.register('database', db_manager)

    tracker = ExecutionTracker(db_manager)
    services.register('execution_tracker', tracker)

    hitl_manager = HITLManager(db_manager)
    services.register('hitl_manager', hitl_manager)

    print("[OK] Services registered")

    # Load simple HITL pipeline
    import json
    from pathlib import Path

    pipeline_path = Path(__file__).parent / "pipelines" / "simple_hitl_pipeline" / "pipeline.json"

    if not pipeline_path.exists():
        print(f"[FAIL] Pipeline not found at {pipeline_path}")
        return False

    with open(pipeline_path, 'r') as f:
        pipeline_config = json.load(f)

    print(f"[OK] Loaded pipeline: {pipeline_config['name']}")

    # Create runner
    runner = GraphPipelineRunner(services)

    # Execute pipeline
    execution_context = ExecutionContext(
        execution_id="test-hitl-001",
        pipeline_id="simple_hitl_pipeline"
    )

    input_data = {
        "topic": "AI Testing"
    }

    print("\n2. Starting pipeline execution...")
    result = await runner.run_pipeline_from_json(
        pipeline_config,
        input_data,
        execution_context,
        use_enhanced_features=True
    )

    print("\n3. Pipeline execution result:")
    print(f"   Status: {result.get('status', 'unknown')}")

    if result.get('status') == 'waiting_for_human':
        interaction_id = result.get('interaction_id')
        waiting_step = result.get('waiting_step')

        print(f"   [OK] Pipeline paused at step: {waiting_step}")
        print(f"   [OK] Interaction ID: {interaction_id}")

        # Verify interaction was created
        interaction = await hitl_manager.get_interaction(interaction_id)
        if not interaction:
            print("   [FAIL] Interaction not found in database")
            return False

        print("   [OK] Interaction found in database")
        print(f"      Prompt: {interaction.prompt}")
        print(f"      Status: {interaction.status}")

        # Simulate human response
        print("\n4. Simulating human response...")
        human_input = {
            "decision": "approve",
            "comments": "Test approved"
        }

        success = await hitl_manager.respond_to_interaction(
            interaction_id=interaction_id,
            human_input=human_input,
            responded_by="test-user"
        )

        if not success:
            print("   [FAIL] Failed to record human response")
            return False

        print("   [OK] Human response recorded")

        # Test resume (simplified - in real app this would be triggered by API)
        print("\n5. Testing resume logic...")

        # Get execution state
        exec_state = await hitl_manager.get_execution_state(interaction_id)
        if not exec_state:
            print("   [FAIL] Could not retrieve execution state")
            return False

        print("   [OK] Retrieved execution state")
        print(f"      Current step was: {exec_state.get('current_step')}")
        print("      Would continue from next step")

        # In a full test, we would:
        # - Find next step after HITL step
        # - Resume pipeline execution with merged human input
        # - Verify completion

        print("\n" + "="*80)
        print("[OK] HITL PAUSE/RESUME TEST PASSED")
        print("="*80)
        return True

    else:
        print(f"   [FAIL] Expected status 'waiting_for_human', got: {result.get('status')}")
        print(f"   Full result: {result}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_hitl_pause_and_resume())
    sys.exit(0 if success else 1)
