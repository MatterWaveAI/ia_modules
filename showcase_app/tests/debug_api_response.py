"""
Test what the API is actually returning for execution data
"""
import requests
import json

# Get recent executions
response = requests.get('http://localhost:7331/api/execute/')
print("=" * 80)
print("GET /api/execute/")
print("=" * 80)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    executions = response.json()
    print(f"\nFound {len(executions)} executions\n")
    
    # Get the most recent one
    if executions:
        execution = executions[0]
        job_id = execution['job_id']
        
        print(f"Most recent: {execution['pipeline_name']} ({job_id})")
        print(f"Status: {execution['status']}")
        print(f"Steps: {len(execution.get('steps', []))}")
        print()
        
        # Get detailed execution
        detail_response = requests.get(f'http://localhost:7331/api/execute/{job_id}')
        print("=" * 80)
        print(f"GET /api/execute/{job_id}")
        print("=" * 80)
        print(f"Status: {detail_response.status_code}")
        
        if detail_response.status_code == 200:
            detail = detail_response.json()
            
            print("\nExecution Details:")
            print(f"  Pipeline: {detail.get('pipeline_name')}")
            print(f"  Status: {detail.get('status')}")
            print(f"  Started: {detail.get('started_at')}")
            print(f"  Completed: {detail.get('completed_at')}")
            
            steps = detail.get('steps', [])
            print(f"\n  Steps ({len(steps)} total):")
            
            for i, step in enumerate(steps, 1):
                print(f"\n  Step {i}: {step.get('step_name')}")
                print(f"    Status: {step.get('status')}")
                print(f"    Started: {step.get('started_at')}")
                print(f"    Completed: {step.get('completed_at')}")
                print(f"    Duration: {step.get('execution_time_ms')}ms")
                print(f"    Has input_data: {step.get('input_data') is not None}")
                print(f"    Has output_data: {step.get('output_data') is not None}")
                
                if step.get('input_data'):
                    print(f"    Input type: {type(step.get('input_data'))}")
                    if isinstance(step.get('input_data'), dict):
                        print(f"    Input keys: {list(step.get('input_data').keys())}")
                    else:
                        print(f"    Input value: {step.get('input_data')[:100] if isinstance(step.get('input_data'), str) else step.get('input_data')}")
                
                if step.get('output_data'):
                    print(f"    Output type: {type(step.get('output_data'))}")
                    if isinstance(step.get('output_data'), dict):
                        print(f"    Output keys: {list(step.get('output_data').keys())}")
                    else:
                        print(f"    Output value: {step.get('output_data')[:100] if isinstance(step.get('output_data'), str) else step.get('output_data')}")
            
            print("\n\n" + "=" * 80)
            print("FULL FIRST STEP JSON")
            print("=" * 80)
            if steps:
                print(json.dumps(steps[0], indent=2))
        else:
            print(f"Error: {detail_response.text}")
else:
    print(f"Error: {response.text}")
