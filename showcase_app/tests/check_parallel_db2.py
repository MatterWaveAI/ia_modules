"""Check output_data for parallel pipeline using DatabaseManager"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from nexusql import DatabaseManager
import json

async def check_parallel():
    # Use the same database URL as .env
    db_url = os.getenv('DATABASE_URL', 'postgresql://ia_user:ia_password@localhost:5433/ia_modules')
    db = DatabaseManager(db_url)
    
    # Initialize database connection
    await db.initialize(apply_schema=False)

    # Get most recent parallel pipeline execution
    query = """
        SELECT execution_id, pipeline_name, status, output_data
        FROM pipeline_executions
        WHERE pipeline_name LIKE '%arallel%'
        ORDER BY started_at DESC
        LIMIT 1
    """

    rows = db.fetch_all(query)
    if rows:
        row = rows[0]
        exec_id = row['execution_id']
        name = row['pipeline_name']
        status = row['status']
        output_data = row['output_data']
        
        print(f"Execution: {exec_id}")
        print(f"Pipeline: {name}")
        print(f"Status: {status}")
        print("\n" + "=" * 60)
        print("OUTPUT_DATA in database:")
        print("=" * 60)
        print(f"Type: {type(output_data)}")
        print(f"Value: {output_data[:200] if output_data else None}...")
        
        if output_data:
            try:
                parsed = json.loads(output_data) if isinstance(output_data, str) else output_data
                print("\nParsed JSON:")
                print(json.dumps(parsed, indent=2))
            except Exception as e:
                print(f"Error parsing: {e}")
        
        # Check step outputs
        print("\n" + "=" * 60)
        print("STEP OUTPUTS:")
        print("=" * 60)
        step_query = """
            SELECT step_name, status, output_data
            FROM step_executions
            WHERE execution_id = :exec_id
            ORDER BY started_at
        """
        
        step_rows = db.fetch_all(step_query, {'exec_id': exec_id})
        for step_row in step_rows:
            step_name = step_row['step_name']
            step_status = step_row['status']
            step_output = step_row['output_data']
            
            print(f"\nStep: {step_name}")
            print(f"  Status: {step_status}")
            if step_output:
                try:
                    parsed_step = json.loads(step_output) if isinstance(step_output, str) else step_output
                    print(f"  Output type: {type(parsed_step)}")
                    if isinstance(parsed_step, dict):
                        print(f"  Output keys: {list(parsed_step.keys())}")
                        print(f"  Sample: {json.dumps(parsed_step, indent=4)[:200]}...")
                    elif isinstance(parsed_step, list):
                        print(f"  Output is list with {len(parsed_step)} items")
                    else:
                        print(f"  Output: {parsed_step}")
                except Exception as e:
                    print(f"  Error: {e}")
    else:
        print("No parallel pipeline execution found")

if __name__ == "__main__":
    asyncio.run(check_parallel())
