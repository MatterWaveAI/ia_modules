"""Test if execution API returns pipeline_id for graph display"""
import requests

API_URL = "http://localhost:7331"

# Get recent executions
response = requests.get(f"{API_URL}/api/execute/")
print("Recent Executions:")
print("=" * 60)

if response.status_code == 200:
    executions = response.json()
    for exec in executions[:3]:  # Show first 3
        print(f"\nExecution: {exec['pipeline_name']}")
        print(f"  Job ID: {exec['job_id']}")
        print(f"  Pipeline ID: {exec.get('pipeline_id', 'MISSING!')}")
        print(f"  Status: {exec['status']}")
        
        # Check if we can get the pipeline config
        if exec.get('pipeline_id'):
            pipeline_response = requests.get(f"{API_URL}/api/pipelines/{exec['pipeline_id']}")
            if pipeline_response.status_code == 200:
                pipeline = pipeline_response.json()
                print(f"  ✅ Pipeline config available: {pipeline.get('name')}")
                print(f"     Steps in config: {len(pipeline.get('config', {}).get('steps', []))}")
                print(f"     Paths in config: {len(pipeline.get('config', {}).get('flow', {}).get('paths', []))}")
            else:
                print(f"  ❌ Pipeline config NOT found (status: {pipeline_response.status_code})")
else:
    print(f"❌ Failed to get executions: {response.status_code}")
