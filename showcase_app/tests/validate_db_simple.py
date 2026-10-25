"""
Simple Database Validation Script

Connects directly to PostgreSQL and runs validation queries.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


def main():
    # Load environment variables
    from dotenv import load_dotenv
    backend_env = Path(__file__).parent.parent / "backend" / ".env"
    load_dotenv(backend_env)
    
    db_url = os.getenv('DATABASE_URL', 'postgresql://ia_user:ia_password@localhost:5433/ia_modules')
    print(f"Connecting to: {db_url}\n")
    
    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)
    
    print("=" * 80)
    print("DATABASE VALIDATION REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 80 + "\n")
    
    issues = []
    recommendations = []
    
    # Query 1: Check for completed executions with zero completed_steps
    print("\n1. Checking for completed executions with zero completed_steps...")
    query1 = """
        SELECT execution_id, pipeline_name, status, total_steps, completed_steps, failed_steps
        FROM pipeline_executions
        WHERE status = 'completed' AND completed_steps = 0
        ORDER BY started_at DESC
        LIMIT 10;
    """
    cur.execute(query1)
    rows = cur.fetchall()
    if rows:
        print(f"   WARNING: Found {len(rows)} completed executions with 0 completed_steps")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['pipeline_name']} | Steps: {row['total_steps']}/{row['completed_steps']}")
        issues.append(("Completed executions with zero completed_steps", len(rows), "HIGH"))
        recommendations.append(("test_execution_step_counting", "Verify that completed_steps is accurately tracked"))
    else:
        print("   OK: No issues found")
    
    # Query 2: Check for inconsistent step counts
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
    cur.execute(query2)
    rows = cur.fetchall()
    if rows:
        print(f"   WARNING: Found {len(rows)} executions with inconsistent step counts")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | Total: {row['total_steps']}, Sum: {row['sum_steps']}")
        issues.append(("Inconsistent step counts", len(rows), "HIGH"))
        recommendations.append(("test_step_count_consistency", "Verify total_steps = completed + failed + pending"))
    else:
        print("   OK: No issues found")
    
    # Query 3: Check for NULL output_data on completed executions
    print("\n3. Checking for completed executions with NULL output_data...")
    query3 = """
        SELECT execution_id, pipeline_name
        FROM pipeline_executions
        WHERE status = 'completed' AND output_data IS NULL
        LIMIT 10;
    """
    cur.execute(query3)
    rows = cur.fetchall()
    if rows:
        print(f"   WARNING: Found {len(rows)} completed executions with NULL output_data")
        for row in rows:
            print(f"      - {row['execution_id'][:8]}... | {row['pipeline_name']}")
        issues.append(("Completed executions with NULL output_data", len(rows), "MEDIUM"))
        recommendations.append(("test_output_data_persistence", "Verify output_data is saved on completion"))
    else:
        print("   OK: No issues found")
    
    # Summary Statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    stats_query = """
        SELECT 
            COUNT(*) as total_executions,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
            AVG(execution_time_ms) as avg_duration_ms
        FROM pipeline_executions;
    """
    cur.execute(stats_query)
    stats = cur.fetchone()
    if stats:
        print(f"\nTotal Executions: {stats['total_executions']}")
        print(f"Completed: {stats['completed']}")
        print(f"Failed: {stats['failed']}")
        avg_ms = stats['avg_duration_ms']
        print(f"Avg Duration: {avg_ms:.0f}ms" if avg_ms else "Avg Duration: N/A")
    
    # Generate Markdown Report
    print("\n" + "=" * 80)
    print("GENERATING MARKDOWN REPORT")
    print("=" * 80)
    
    report_path = Path(__file__).parent / "DATABASE_VALIDATION_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Database Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Database:** {db_url}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Total Issues Found:** {len(issues)}\n")
        high = len([i for i in issues if i[2] == 'HIGH'])
        medium = len([i for i in issues if i[2] == 'MEDIUM'])
        f.write(f"- **High Severity:** {high}\n")
        f.write(f"- **Medium Severity:** {medium}\n\n")
        
        if issues:
            f.write("## Issues Found\n\n")
            for i, (title, count, severity) in enumerate(issues, 1):
                f.write(f"### {i}. {title} [{severity}]\n\n")
                f.write(f"**Count:** {count} records\n\n")
        else:
            f.write("## No Issues Found\n\n")
            f.write("All validation checks passed successfully!\n\n")
        
        if stats:
            f.write("## Statistics\n\n")
            f.write(f"- **Total Executions:** {stats['total_executions']}\n")
            f.write(f"- **Completed:** {stats['completed']}\n")
            f.write(f"- **Failed:** {stats['failed']}\n")
            avg_ms = stats['avg_duration_ms']
            f.write(f"- **Avg Duration:** {avg_ms:.0f}ms\n\n" if avg_ms else "- **Avg Duration:** N/A\n\n")
        
        f.write("## Recommended Tests\n\n")
        if recommendations:
            for test_name, description in recommendations:
                f.write(f"### `{test_name}`\n\n")
                f.write(f"{description}\n\n")
                f.write("```python\n")
                f.write(f"def {test_name}():\n")
                f.write(f"    # TODO: Implement test for: {description}\n")
                f.write("    pass\n")
                f.write("```\n\n")
        else:
            f.write("No additional tests recommended at this time.\n\n")
        
        f.write("## Next Steps\n\n")
        f.write("1. Review and fix high-severity issues immediately\n")
        f.write("2. Implement recommended unit and integration tests\n")
        f.write("3. Run this validation script regularly (e.g., in CI/CD)\n")
        f.write("4. Update `_count_total_steps()` methods to fix step counting\n")
    
    print(f"\nReport saved to: {report_path}")
    
    cur.close()
    conn.close()
    
    # Exit with appropriate code
    if any(i[2] == 'HIGH' for i in issues):
        print("\nHigh severity issues found - please review!")
        sys.exit(1)
    else:
        print("\nValidation complete!")
        sys.exit(0)


if __name__ == "__main__":
    main()
