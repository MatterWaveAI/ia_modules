"""
Check a specific execution to debug data issues
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from nexusql import DatabaseManager
import json
from dotenv import load_dotenv

def check_execution(execution_id=None):
    """Check specific execution data"""
    
    # Load environment
    load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://ia_user:ia_password@localhost:5433/ia_modules')
    
    db = DatabaseManager(database_url)
    db.connect()
    
    print("=" * 80)
    print("CHECKING EXECUTIONS")
    print("=" * 80)
    
    # Get recent executions
    query = """
        SELECT 
            execution_id,
            pipeline_id,
            pipeline_name,
            status,
            started_at,
            completed_at,
            total_steps,
            completed_steps,
            failed_steps
        FROM pipeline_executions
        ORDER BY started_at DESC
        LIMIT 10
    """
    
    rows = db.fetch_all(query, {})
    
    print(f"\nFound {len(rows)} recent executions:\n")
    
    for i, row in enumerate(rows, 1):
        print(f"{i}. [{row['status']}] {row['pipeline_name']} - {row['execution_id']}")
        print(f"   Steps: {row['completed_steps']}/{row['total_steps']} completed, {row['failed_steps']} failed")
        print(f"   Started: {row['started_at']}")
        print()
    
    # If no specific execution provided, use the most recent
    if not execution_id and rows:
        execution_id = rows[0]['execution_id']
        print(f"\nUsing most recent execution: {execution_id}\n")
    
    if not execution_id:
        print("No executions found!")
        return
    
    print("=" * 80)
    print(f"DETAILED CHECK FOR EXECUTION: {execution_id}")
    print("=" * 80)
    
    # Get execution details
    exec_query = """
        SELECT * FROM pipeline_executions
        WHERE execution_id = :execution_id
    """
    exec_row = db.fetch_one(exec_query, {'execution_id': execution_id})
    
    if not exec_row:
        print("Execution not found!")
        return
    
    print(f"\nExecution: {exec_row['pipeline_name']}")
    print(f"Status: {exec_row['status']}")
    print(f"Started: {exec_row['started_at']}")
    print(f"Completed: {exec_row['completed_at']}")
    print(f"Total Steps: {exec_row['total_steps']}")
    print(f"Completed Steps: {exec_row['completed_steps']}")
    print(f"Failed Steps: {exec_row['failed_steps']}")
    
    # Get steps
    steps_query = """
        SELECT 
            step_execution_id,
            step_id,
            step_name,
            step_type,
            status,
            started_at,
            completed_at,
            input_data,
            output_data,
            error_message,
            execution_time_ms,
            retry_count,
            metadata_json
        FROM step_executions
        WHERE execution_id = :execution_id
        ORDER BY started_at ASC
    """
    
    steps = db.fetch_all(steps_query, {'execution_id': execution_id})
    
    print(f"\n{'=' * 80}")
    print(f"STEPS ({len(steps)} total)")
    print(f"{'=' * 80}\n")
    
    for i, step in enumerate(steps, 1):
        print(f"\n--- STEP {i}: {step['step_name']} [{step['status']}] ---")
        print(f"Step ID: {step['step_id']}")
        print(f"Step Type: {step['step_type']}")
        print(f"Started: {step['started_at']}")
        print(f"Completed: {step['completed_at']}")
        print(f"Duration: {step['execution_time_ms']}ms")
        print(f"Retry Count: {step['retry_count']}")
        
        if step['error_message']:
            print(f"\nERROR: {step['error_message']}")
        
        print("\nInput Data:")
        if step['input_data']:
            try:
                input_data = json.loads(step['input_data']) if isinstance(step['input_data'], str) else step['input_data']
                print(json.dumps(input_data, indent=2))
            except Exception as e:
                print(f"  Error parsing: {e}")
                print(f"  Raw type: {type(step['input_data'])}")
                print(f"  Raw value: {step['input_data']}")
        else:
            print("  (null or empty)")
        
        print("\nOutput Data:")
        if step['output_data']:
            try:
                output_data = json.loads(step['output_data']) if isinstance(step['output_data'], str) else step['output_data']
                print(json.dumps(output_data, indent=2))
            except Exception as e:
                print(f"  Error parsing: {e}")
                print(f"  Raw type: {type(step['output_data'])}")
                print(f"  Raw value: {step['output_data']}")
        else:
            print("  (null or empty)")
        
        if step['metadata_json']:
            print("\nMetadata:")
            try:
                metadata = json.loads(step['metadata_json']) if isinstance(step['metadata_json'], str) else step['metadata_json']
                print(json.dumps(metadata, indent=2))
            except Exception as e:
                print(f"  Error parsing: {e}")

if __name__ == "__main__":
    import sys
    execution_id = sys.argv[1] if len(sys.argv) > 1 else None
    check_execution(execution_id)
