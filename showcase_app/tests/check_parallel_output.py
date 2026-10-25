"""Check parallel pipeline execution data"""
import requests

API_URL = "http://localhost:7331"

# Get recent executions
response = requests.get(f"{API_URL}/api/execute/")
if response.status_code == 200:
    executions = response.json()
    
    # Find parallel pipeline execution
    parallel_exec = None
    for exec in executions:
        if 'parallel' in exec.get('pipeline_name', '').lower():
            parallel_exec = exec
            break
    
    if parallel_exec:
        job_id = parallel_exec['job_id']
        print(f"Found Parallel Pipeline Execution: {job_id}")
        print(f"Pipeline: {parallel_exec['pipeline_name']}")
        print(f"Status: {parallel_exec['status']}")
        print()
        
        # Get detailed execution
        detail_response = requests.get(f"{API_URL}/api/execute/{job_id}")
        if detail_response.status_code == 200:
            detail = detail_response.json()
            
            print("=" * 60)
            print("INPUT DATA:")
            print("=" * 60)
            import json
            print(json.dumps(detail.get('input_data'), indent=2))
            
            print("\n" + "=" * 60)
            print("OUTPUT DATA:")
            print("=" * 60)
            print(f"Type: {type(detail.get('output_data'))}")
            print(f"Value: {detail.get('output_data')}")
            print()
            print("Full JSON:")
            print(json.dumps(detail.get('output_data'), indent=2))
            
            print("\n" + "=" * 60)
            print("STEPS:")
            print("=" * 60)
            for i, step in enumerate(detail.get('steps', []), 1):
                print(f"\nStep {i}: {step.get('step_name')}")
                print(f"  Status: {step.get('status')}")
                print(f"  Output data type: {type(step.get('output_data'))}")
                if step.get('output_data'):
                    print(f"  Output keys: {list(step.get('output_data', {}).keys())}")
    else:
        print("No parallel pipeline execution found")
        print("\nAvailable executions:")
        for exec in executions[:5]:
            print(f"  - {exec.get('pipeline_name')} ({exec.get('job_id')})")
else:
    print(f"Failed to get executions: {response.status_code}")
