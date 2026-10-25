"""
Database Validation Script

Runs SQL queries to check for data integrity issues in the showcase_app database
and generates a markdown report with findings and test recommendations.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor


def main():
    # Load environment variables
    from dotenv import load_dotenv
    backend_env = Path(__file__).parent.parent / "backend" / ".env"
    load_dotenv(backend_env)
    
    db_url = os.getenv('DATABASE_URL', 'postgresql://ia_user:ia_password@localhost:5433/ia_modules')
    print(f"Connecting to: {db_url}")
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "="*80)
    print("DATABASE VALIDATION REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    issues = []
    recommendations = []
    
    # Query 1: Check for executions with status=completed but completed_steps=0
    print("\n1. Checking for completed executions with zero completed_steps...")
    query1 = """
        SELECT execution_id, pipeline_name, status, total_steps, completed_steps, failed_steps,
               started_at, completed_at
        FROM pipeline_executions
        WHERE status = 'completed' AND completed_steps = 0
        ORDER BY started_at DESC
        LIMIT 10;
    """
    rows = cur.execute(query1)
    rows = cur.fetchall()
    if rows:
        print(f"   ⚠️  ISSUE: Found {len(rows)} completed executions with 0 completed_steps")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['pipeline_name']} | Steps: {row['total_steps']}/{row['completed_steps']}")
        issues.append({
            "title": "Completed executions with zero completed_steps",
            "count": len(rows),
            "query": query1,
            "severity": "HIGH"
        })
        recommendations.append({
            "test": "test_execution_step_counting",
            "description": "Verify that completed_steps is accurately tracked during pipeline execution",
            "type": "integration"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 2: Check for inconsistent step counts (completed + failed != total)
    print("\n2. Checking for inconsistent step counts...")
    query2 = """
        SELECT execution_id, pipeline_name, total_steps, completed_steps, failed_steps,
               (completed_steps + failed_steps) as sum_steps
        FROM pipeline_executions
        WHERE total_steps > 0 
          AND (completed_steps + failed_steps) != total_steps
        ORDER BY started_at DESC
        LIMIT 10;
    """
    rows = cur.execute(query2)
    if rows:
        print(f"   ⚠️  ISSUE: Found {len(rows)} executions with inconsistent step counts")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | Total: {row['total_steps']}, Completed: {row['completed_steps']}, Failed: {row['failed_steps']}, Sum: {row['sum_steps']}")
        issues.append({
            "title": "Inconsistent step counts",
            "count": len(rows),
            "query": query2,
            "severity": "HIGH"
        })
        recommendations.append({
            "test": "test_step_count_consistency",
            "description": "Verify that total_steps = completed_steps + failed_steps + pending_steps",
            "type": "unit"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 3: Check for NULL output_data on completed executions
    print("\n3. Checking for completed executions with NULL output_data...")
    query3 = """
        SELECT execution_id, pipeline_name, status, output_data
        FROM pipeline_executions
        WHERE status = 'completed' AND output_data IS NULL
        ORDER BY started_at DESC
        LIMIT 10;
    """
    rows = cur.execute(query3)
    if rows:
        print(f"   ⚠️  WARNING: Found {len(rows)} completed executions with NULL output_data")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['pipeline_name']}")
        issues.append({
            "title": "Completed executions with NULL output_data",
            "count": len(rows),
            "query": query3,
            "severity": "MEDIUM"
        })
        recommendations.append({
            "test": "test_output_data_persistence",
            "description": "Verify that output_data is saved when pipeline completes successfully",
            "type": "integration"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 4: Check for executions with no started_at time
    print("\n4. Checking for executions with missing started_at...")
    query4 = """
        SELECT execution_id, pipeline_name, status, started_at
        FROM pipeline_executions
        WHERE started_at IS NULL
        LIMIT 10;
    """
    rows = cur.execute(query4)
    if rows:
        print(f"   ⚠️  ISSUE: Found {len(rows)} executions with NULL started_at")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['pipeline_name']}")
        issues.append({
            "title": "Executions with missing started_at timestamp",
            "count": len(rows),
            "query": query4,
            "severity": "HIGH"
        })
        recommendations.append({
            "test": "test_execution_timestamps",
            "description": "Verify that started_at is set when execution begins",
            "type": "unit"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 5: Check for completed executions with NULL completed_at
    print("\n5. Checking for completed executions with missing completed_at...")
    query5 = """
        SELECT execution_id, pipeline_name, status, completed_at
        FROM pipeline_executions
        WHERE status IN ('completed', 'failed') AND completed_at IS NULL
        LIMIT 10;
    """
    rows = cur.execute(query5)
    if rows:
        print(f"   ⚠️  ISSUE: Found {len(rows)} finished executions with NULL completed_at")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['pipeline_name']} | Status: {row['status']}")
        issues.append({
            "title": "Finished executions with missing completed_at timestamp",
            "count": len(rows),
            "query": query5,
            "severity": "HIGH"
        })
        recommendations.append({
            "test": "test_completion_timestamps",
            "description": "Verify that completed_at is set when execution finishes",
            "type": "unit"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 6: Check for orphaned step executions (no parent execution)
    print("\n6. Checking for orphaned step executions...")
    query6 = """
        SELECT se.execution_id, COUNT(*) as orphaned_steps
        FROM step_executions se
        LEFT JOIN pipeline_executions pe ON se.execution_id = pe.execution_id
        WHERE pe.execution_id IS NULL
        GROUP BY se.execution_id
        LIMIT 10;
    """
    rows = cur.execute(query6)
    if rows:
        print(f"   ⚠️  WARNING: Found {len(rows)} executions with orphaned steps")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['orphaned_steps']} orphaned steps")
        issues.append({
            "title": "Orphaned step executions without parent execution",
            "count": len(rows),
            "query": query6,
            "severity": "MEDIUM"
        })
        recommendations.append({
            "test": "test_step_execution_referential_integrity",
            "description": "Verify that step_executions have valid parent execution_id",
            "type": "integration"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 7: Check execution duration consistency
    print("\n7. Checking for execution duration inconsistencies...")
    query7 = """
        SELECT execution_id, pipeline_name, execution_time_ms,
               EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 as calculated_ms,
               ABS(execution_time_ms - EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) as diff_ms
        FROM pipeline_executions
        WHERE completed_at IS NOT NULL 
          AND started_at IS NOT NULL
          AND execution_time_ms IS NOT NULL
          AND ABS(execution_time_ms - EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) > 100
        LIMIT 10;
    """
    rows = cur.execute(query7)
    if rows:
        print(f"   ⚠️  WARNING: Found {len(rows)} executions with duration mismatches")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | Stored: {row['execution_time_ms']}ms, Calculated: {row['calculated_ms']:.0f}ms, Diff: {row['diff_ms']:.0f}ms")
        issues.append({
            "title": "Execution duration mismatches",
            "count": len(rows),
            "query": query7,
            "severity": "LOW"
        })
        recommendations.append({
            "test": "test_execution_duration_calculation",
            "description": "Verify that execution_time_ms matches (completed_at - started_at)",
            "type": "unit"
        })
    else:
        print("   ✅ OK: No issues found")
    
    # Query 8: Check for invalid JSON in input_data/output_data
    print("\n8. Checking for invalid JSON in data fields...")
    query8 = """
        SELECT execution_id, pipeline_name,
               CASE 
                   WHEN input_data IS NOT NULL AND NOT (input_data::text ~ '^[\\s]*[\\[\\{]') THEN 'input_data'
                   WHEN output_data IS NOT NULL AND NOT (output_data::text ~ '^[\\s]*[\\[\\{]') THEN 'output_data'
                   ELSE 'unknown'
               END as invalid_field
        FROM pipeline_executions
        WHERE (input_data IS NOT NULL AND NOT (input_data::text ~ '^[\\s]*[\\[\\{]'))
           OR (output_data IS NOT NULL AND NOT (output_data::text ~ '^[\\s]*[\\[\\{]'))
        LIMIT 10;
    """
    try:
        rows = cur.execute(query8)
        if rows:
            print(f"   ⚠️  WARNING: Found {len(rows)} executions with malformed JSON")
            for row in rows:
                print(f"      - {row['execution_id'][:8]}... | Invalid field: {row['invalid_field']}")
            issues.append({
                "title": "Malformed JSON in data fields",
                "count": len(rows),
                "query": query8,
                "severity": "MEDIUM"
            })
            recommendations.append({
                "test": "test_json_data_validation",
                "description": "Verify that input_data and output_data are valid JSON",
                "type": "unit"
            })
        else:
            print("   ✅ OK: No issues found")
    except Exception as e:
        print(f"   ⚠️  Could not check JSON validity: {e}")
    
    # Summary Statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    stats_query = """
        SELECT 
            COUNT(*) as total_executions,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
            COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
            AVG(execution_time_ms) as avg_duration_ms,
            MAX(execution_time_ms) as max_duration_ms
        FROM pipeline_executions;
    """
    stats = cur.execute(stats_query)
    if stats:
        print(f"\nTotal Executions: {stats['total_executions']}")
        print(f"Completed: {stats['completed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Running: {stats['running']}")
        print(f"Avg Duration: {stats['avg_duration_ms']:.0f}ms" if stats['avg_duration_ms'] else "Avg Duration: N/A")
        print(f"Max Duration: {stats['max_duration_ms']}ms" if stats['max_duration_ms'] else "Max Duration: N/A")
    
    # Generate Markdown Report
    print("\n" + "="*80)
    print("GENERATING MARKDOWN REPORT")
    print("="*80)
    
    report_path = Path(__file__).parent / "DATABASE_VALIDATION_REPORT.md"
    with open(report_path, 'w') as f:
        f.write("# Database Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Database:** {db_url}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Total Issues Found:** {len(issues)}\n")
        f.write(f"- **High Severity:** {len([i for i in issues if i['severity'] == 'HIGH'])}\n")
        f.write(f"- **Medium Severity:** {len([i for i in issues if i['severity'] == 'MEDIUM'])}\n")
        f.write(f"- **Low Severity:** {len([i for i in issues if i['severity'] == 'LOW'])}\n\n")
        
        if issues:
            f.write("## Issues Found\n\n")
            for i, issue in enumerate(issues, 1):
                f.write(f"### {i}. {issue['title']} [{issue['severity']}]\n\n")
                f.write(f"**Count:** {issue['count']} records\n\n")
                f.write("**Query:**\n```sql\n")
                f.write(issue['query'].strip())
                f.write("\n```\n\n")
        else:
            f.write("## ✅ No Issues Found\n\n")
            f.write("All validation checks passed successfully!\n\n")
        
        f.write("## Statistics\n\n")
        if stats:
            f.write(f"- **Total Executions:** {stats['total_executions']}\n")
            f.write(f"- **Completed:** {stats['completed']}\n")
            f.write(f"- **Failed:** {stats['failed']}\n")
            f.write(f"- **Running:** {stats['running']}\n")
            f.write(f"- **Avg Duration:** {stats['avg_duration_ms']:.0f}ms\n" if stats['avg_duration_ms'] else "- **Avg Duration:** N/A\n")
            f.write(f"- **Max Duration:** {stats['max_duration_ms']}ms\n\n" if stats['max_duration_ms'] else "- **Max Duration:** N/A\n\n")
        
        f.write("## Recommended Tests\n\n")
        if recommendations:
            f.write("### Unit Tests\n\n")
            for rec in [r for r in recommendations if r['type'] == 'unit']:
                f.write(f"#### `{rec['test']}`\n")
                f.write(f"{rec['description']}\n\n")
                f.write("```python\n")
                f.write(f"async def {rec['test']}():\n")
                f.write("    # TODO: Implement test\n")
                f.write("    pass\n")
                f.write("```\n\n")
            
            f.write("### Integration Tests\n\n")
            for rec in [r for r in recommendations if r['type'] == 'integration']:
                f.write(f"#### `{rec['test']}`\n")
                f.write(f"{rec['description']}\n\n")
                f.write("```python\n")
                f.write(f"async def {rec['test']}():\n")
                f.write("    # TODO: Implement test\n")
                f.write("    pass\n")
                f.write("```\n\n")
        else:
            f.write("No additional tests recommended at this time.\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Review and fix high-severity issues immediately\n")
        f.write("2. Implement recommended unit and integration tests\n")
        f.write("3. Run this validation script regularly (e.g., in CI/CD)\n")
        f.write("4. Add database constraints to prevent future issues\n")
        f.write("5. Update `_save_execution_to_db()` to fix step counting\n")
    
    print(f"\n✅ Report saved to: {report_path}")
    
    # Close database connection
    cur.close()
    conn.close()
    
    # Exit with appropriate code
    if any(i['severity'] == 'HIGH' for i in issues):
        print("\n❌ High severity issues found - please review!")
        sys.exit(1)
    else:
        print("\n✅ Validation complete!")
        sys.exit(0)


if __name__ == "__main__":
    main()

