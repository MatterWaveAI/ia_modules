"""Check output_data in database for parallel pipeline"""
import psycopg2
import json

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="ia_modules_db",
    user="postgres",
    password="postgres"
)

cursor = conn.cursor()

# Get most recent parallel pipeline execution
cursor.execute("""
    SELECT execution_id, pipeline_name, status, output_data
    FROM pipeline_executions
    WHERE pipeline_name LIKE '%arallel%'
    ORDER BY started_at DESC
    LIMIT 1
""")

row = cursor.fetchone()
if row:
    exec_id, name, status, output_data = row
    print(f"Execution: {exec_id}")
    print(f"Pipeline: {name}")
    print(f"Status: {status}")
    print("\n" + "=" * 60)
    print("OUTPUT_DATA in database:")
    print("=" * 60)
    print(f"Type in DB: {type(output_data)}")
    print(f"Value: {output_data}")
    
    if output_data:
        try:
            parsed = json.loads(output_data) if isinstance(output_data, str) else output_data
            print("\nParsed JSON:")
            print(json.dumps(parsed, indent=2))
        except Exception as e:
            print(f"Error parsing: {e}")
    
    # Also check step outputs
    print("\n" + "=" * 60)
    print("STEP OUTPUTS:")
    print("=" * 60)
    cursor.execute("""
        SELECT step_name, status, output_data
        FROM step_executions
        WHERE execution_id = %s
        ORDER BY started_at
    """, (exec_id,))
    
    for step_row in cursor.fetchall():
        step_name, step_status, step_output = step_row
        print(f"\nStep: {step_name}")
        print(f"  Status: {step_status}")
        if step_output:
            try:
                parsed_step = json.loads(step_output) if isinstance(step_output, str) else step_output
                print(f"  Output keys: {list(parsed_step.keys()) if isinstance(parsed_step, dict) else 'not a dict'}")
            except Exception as e:
                print(f"  Error: {e}")
else:
    print("No parallel pipeline execution found")

cursor.close()
conn.close()
