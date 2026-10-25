"""
Check what data is actually stored in step_executions table
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from nexusql import DatabaseManager
import json

def check_step_data():
    """Check step execution data in database"""
    
    # Initialize database with PostgreSQL from environment
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://ia_user:ia_password@localhost:5433/ia_modules')
    print(f"Connecting to: {database_url}\n")
    
    db = DatabaseManager(database_url)
    db.connect()
    
    print("=" * 80)
    print("CHECKING STEP EXECUTION DATA IN DATABASE")
    print("=" * 80)
    
    # Get recent step executions
    query = """
        SELECT 
            step_execution_id,
            execution_id,
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
        ORDER BY started_at DESC
        LIMIT 5
    """
    
    rows = db.fetch_all(query, {})
    
    print(f"\nFound {len(rows)} recent step executions\n")
    
    for i, row in enumerate(rows, 1):
        print(f"\n{'=' * 80}")
        print(f"STEP {i}: {row['step_name']}")
        print(f"{'=' * 80}")
        print(f"Step Execution ID: {row['step_execution_id']}")
        print(f"Execution ID: {row['execution_id']}")
        print(f"Step ID: {row['step_id']}")
        print(f"Step Type: {row['step_type']}")
        print(f"Status: {row['status']}")
        print(f"Started At: {row['started_at']}")
        print(f"Completed At: {row['completed_at']}")
        print(f"Execution Time: {row['execution_time_ms']}ms")
        print(f"Retry Count: {row['retry_count']}")
        print(f"Error: {row['error_message']}")
        
        print("\n--- INPUT DATA ---")
        if row['input_data']:
            try:
                input_data = json.loads(row['input_data']) if isinstance(row['input_data'], str) else row['input_data']
                print(json.dumps(input_data, indent=2))
            except Exception as e:
                print(f"Error parsing input_data: {e}")
                print(f"Raw: {row['input_data']}")
        else:
            print("(null)")
        
        print("\n--- OUTPUT DATA ---")
        if row['output_data']:
            try:
                output_data = json.loads(row['output_data']) if isinstance(row['output_data'], str) else row['output_data']
                print(json.dumps(output_data, indent=2))
            except Exception as e:
                print(f"Error parsing output_data: {e}")
                print(f"Raw: {row['output_data']}")
        else:
            print("(null)")
        
        print("\n--- METADATA ---")
        if row['metadata_json']:
            try:
                metadata = json.loads(row['metadata_json']) if isinstance(row['metadata_json'], str) else row['metadata_json']
                print(json.dumps(metadata, indent=2))
            except Exception as e:
                print(f"Error parsing metadata_json: {e}")
                print(f"Raw: {row['metadata_json']}")
        else:
            print("(null)")
    
    # Also check what the API would return
    print(f"\n\n{'=' * 80}")
    print("CHECKING API ENDPOINT DATA FORMAT")
    print(f"{'=' * 80}\n")
    
    # Get one execution with steps
    exec_query = """
        SELECT execution_id 
        FROM pipeline_executions 
        WHERE status IN ('completed', 'failed')
        ORDER BY started_at DESC 
        LIMIT 1
    """
    exec_row = db.fetch_one(exec_query, {})
    
    if exec_row:
        execution_id = exec_row['execution_id']
        print(f"Execution ID: {execution_id}")
        
        steps_query = """
            SELECT * FROM step_executions
            WHERE execution_id = :execution_id
            ORDER BY started_at ASC
        """
        steps = db.fetch_all(steps_query, {'execution_id': execution_id})
        
        print(f"Found {len(steps)} steps for this execution\n")
        
        for step in steps:
            print(f"\nStep: {step['step_name']}")
            print(f"  - Has input_data: {step['input_data'] is not None}")
            print(f"  - Has output_data: {step['output_data'] is not None}")
            print(f"  - Has metadata_json: {step['metadata_json'] is not None}")
            
            if step['input_data']:
                print(f"  - Input data type: {type(step['input_data'])}")
                print(f"  - Input data length: {len(str(step['input_data']))}")
            
            if step['output_data']:
                print(f"  - Output data type: {type(step['output_data'])}")
                print(f"  - Output data length: {len(str(step['output_data']))}")

if __name__ == "__main__":
    check_step_data()
