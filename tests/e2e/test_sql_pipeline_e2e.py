"""
End-to-End Database Integration Tests

These tests verify that data is correctly saved, retrieved, and manipulated
across all supported databases (PostgreSQL, MySQL, MSSQL, SQLite).

Tests cover real-world scenarios using the actual schema from migrations.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from nexusql import DatabaseManager
from nexusql import DatabaseType
from ia_modules.database import MIGRATIONS_DIR


@pytest.fixture
async def initialized_db(db_config):
    """Fixture that provides an initialized database with schema"""
    db = DatabaseManager(db_config)
    
    # Initialize with migrations
    await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
    
    yield db
    
    # Cleanup
    db.disconnect()


class TestPipelineLifecycle:
    """Test complete pipeline lifecycle E2E"""

    @pytest.mark.asyncio
    async def test_create_and_execute_pipeline(self, initialized_db):
        """Test creating a pipeline and executing it with steps"""
        db = initialized_db
        
        execution_id = None
        pipeline_id = None

        try:
            # Create a pipeline
            pipeline_id = str(uuid.uuid4())
            pipeline_slug = f"test-pipeline-{pipeline_id[:8]}"
            
            insert_pipeline = """
            INSERT INTO pipelines (id, slug, name, description, version, is_active, created_at)
            VALUES (:id, :slug, :name, :description, :version, :is_active, :created_at)
            """
            
            db.execute(insert_pipeline, {
                "id": pipeline_id,
                "slug": pipeline_slug,
                "name": "Test Pipeline",
                "description": "E2E test pipeline",
                "version": "1.0",
                "is_active": True,  # a real boolean: PostgreSQL rejects 1 for a BOOLEAN column
                "created_at": datetime.now(timezone.utc)
            })

            # Verify pipeline was created
            verify = db.fetch_one("SELECT * FROM pipelines WHERE id = :id", {"id": pipeline_id})
            assert verify is not None
            assert verify["name"] == "Test Pipeline"
            assert verify["slug"] == pipeline_slug

            # Start a pipeline execution
            execution_id = str(uuid.uuid4())
            insert_execution = """
            INSERT INTO pipeline_executions (
                execution_id, pipeline_id, pipeline_slug, pipeline_name,
                status, started_at, total_steps, completed_steps
            ) VALUES (:execution_id, :pipeline_id, :pipeline_slug, :pipeline_name,
                      :status, :started_at, :total_steps, :completed_steps)
            """
            
            db.execute(insert_execution, {
                "execution_id": execution_id,
                "pipeline_id": pipeline_id,
                "pipeline_slug": pipeline_slug,
                "pipeline_name": "Test Pipeline",
                "status": "running",
                "started_at": datetime.now(timezone.utc),
                "total_steps": 3,
                "completed_steps": 0
            })

            # Add step executions
            for i in range(3):
                step_exec_id = str(uuid.uuid4())
                insert_step = """
                INSERT INTO step_executions (
                    step_execution_id, execution_id, step_id, step_name,
                    status, started_at, step_order
                ) VALUES (:step_execution_id, :execution_id, :step_id, :step_name,
                          :status, :started_at, :step_order)
                """
                
                db.execute(insert_step, {
                    "step_execution_id": step_exec_id,
                    "execution_id": execution_id,
                    "step_id": f"step_{i+1}",
                    "step_name": f"Test Step {i+1}",
                    "status": "completed",
                    "started_at": datetime.now(timezone.utc),
                    "step_order": i
                })

            # Update execution status
            update_execution = """
            UPDATE pipeline_executions
            SET status = :status, completed_steps = :completed_steps, completed_at = :completed_at
            WHERE execution_id = :execution_id
            """
            
            db.execute(update_execution, {
                "status": "completed",
                "completed_steps": 3,
                "completed_at": datetime.now(timezone.utc),
                "execution_id": execution_id
            })

            # Verify final state
            final_execution = db.fetch_one(
                "SELECT * FROM pipeline_executions WHERE execution_id = :id",
                {"id": execution_id}
            )
            assert final_execution["status"] == "completed"
            assert final_execution["completed_steps"] == 3

            # Verify all steps were recorded
            steps = db.execute(
                "SELECT * FROM step_executions WHERE execution_id = :id ORDER BY step_order",
                {"id": execution_id}
            )
            assert len(steps) == 3
            assert steps[0]["step_name"] == "Test Step 1"
            assert steps[2]["step_name"] == "Test Step 3"

            # Add execution logs
            log_query = """
            INSERT INTO execution_logs (execution_id, step_id, log_level, message, timestamp)
            VALUES (:execution_id, :step_id, :log_level, :message, :timestamp)
            """
            
            for i in range(3):
                db.execute(log_query, {
                    "execution_id": execution_id,
                    "step_id": f"step_{i+1}",
                    "log_level": "INFO",
                    "message": f"Step {i+1} completed successfully",
                    "timestamp": datetime.now(timezone.utc)
                })

            # Verify logs
            logs = db.execute(
                "SELECT * FROM execution_logs WHERE execution_id = :id",
                {"id": execution_id}
            )
            assert len(logs) == 3

        finally:
            # Cleanup
            if execution_id:
                db.execute("DELETE FROM execution_logs WHERE execution_id = :id", {"id": execution_id})
                db.execute("DELETE FROM step_executions WHERE execution_id = :id", {"id": execution_id})
                db.execute("DELETE FROM pipeline_executions WHERE execution_id = :id", {"id": execution_id})
            if pipeline_id:
                db.execute("DELETE FROM pipelines WHERE id = :id", {"id": pipeline_id})


class TestCheckpointSystem:
    """Test checkpoint system E2E"""

    @pytest.mark.asyncio
    async def test_checkpoint_creation_and_retrieval(self, initialized_db):
        """Test creating and retrieving checkpoints"""
        db = initialized_db
        

        try:
            thread_id = f"thread-{uuid.uuid4()}"
            pipeline_id = f"pipeline-{uuid.uuid4()}"

            # Create parent checkpoint
            parent_checkpoint_id = str(uuid.uuid4()) if db.config.database_type != DatabaseType.POSTGRESQL else None
            
            insert_checkpoint = """
            INSERT INTO pipeline_checkpoints (
                thread_id, pipeline_id, step_id, step_index, step_name,
                timestamp, state, status
            ) VALUES (:thread_id, :pipeline_id, :step_id, :step_index, :step_name,
                      :timestamp, :state, :status)
            """

            # For non-PostgreSQL, we need to provide checkpoint_id
            if db.config.database_type != DatabaseType.POSTGRESQL:
                insert_checkpoint = """
                INSERT INTO pipeline_checkpoints (
                    checkpoint_id, thread_id, pipeline_id, step_id, step_index, step_name,
                    timestamp, state, status
                ) VALUES (:checkpoint_id, :thread_id, :pipeline_id, :step_id, :step_index, :step_name,
                          :timestamp, :state, :status)
                """
                parent_checkpoint_id = str(uuid.uuid4())
                
                db.execute(insert_checkpoint, {
                    "checkpoint_id": parent_checkpoint_id,
                    "thread_id": thread_id,
                    "pipeline_id": pipeline_id,
                    "step_id": "step_1",
                    "step_index": 0,
                    "step_name": "Initial Step",
                    "timestamp": datetime.now(timezone.utc),
                    "state": '{"data": "checkpoint1"}',
                    "status": "completed"
                })
            else:
                db.execute(insert_checkpoint, {
                    "thread_id": thread_id,
                    "pipeline_id": pipeline_id,
                    "step_id": "step_1",
                    "step_index": 0,
                    "step_name": "Initial Step",
                    "timestamp": datetime.now(timezone.utc),
                    "state": '{"data": "checkpoint1"}',
                    "status": "completed"
                })
                
                # Get the generated checkpoint_id
                result = db.fetch_one(
                    "SELECT checkpoint_id FROM pipeline_checkpoints WHERE thread_id = :thread_id ORDER BY timestamp DESC LIMIT 1",
                    {"thread_id": thread_id}
                )
                parent_checkpoint_id = result["checkpoint_id"]

            # Create child checkpoint
            child_checkpoint_id = str(uuid.uuid4())
            
            if db.config.database_type != DatabaseType.POSTGRESQL:
                insert_child = """
                INSERT INTO pipeline_checkpoints (
                    checkpoint_id, thread_id, pipeline_id, step_id, step_index, step_name,
                    timestamp, state, status, parent_checkpoint_id
                ) VALUES (:checkpoint_id, :thread_id, :pipeline_id, :step_id, :step_index, :step_name,
                          :timestamp, :state, :status, :parent_checkpoint_id)
                """
                
                db.execute(insert_child, {
                    "checkpoint_id": child_checkpoint_id,
                    "thread_id": thread_id,
                    "pipeline_id": pipeline_id,
                    "step_id": "step_2",
                    "step_index": 1,
                    "step_name": "Second Step",
                    "timestamp": datetime.now(timezone.utc),
                    "state": '{"data": "checkpoint2"}',
                    "status": "completed",
                    "parent_checkpoint_id": parent_checkpoint_id
                })
            else:
                insert_child = """
                INSERT INTO pipeline_checkpoints (
                    thread_id, pipeline_id, step_id, step_index, step_name,
                    timestamp, state, status, parent_checkpoint_id
                ) VALUES (:thread_id, :pipeline_id, :step_id, :step_index, :step_name,
                          :timestamp, :state, :status, :parent_checkpoint_id)
                """
                
                db.execute(insert_child, {
                    "thread_id": thread_id,
                    "pipeline_id": pipeline_id,
                    "step_id": "step_2",
                    "step_index": 1,
                    "step_name": "Second Step",
                    "timestamp": datetime.now(timezone.utc),
                    "state": '{"data": "checkpoint2"}',
                    "status": "completed",
                    "parent_checkpoint_id": parent_checkpoint_id
                })

            # Retrieve all checkpoints for thread
            checkpoints = db.execute(
                "SELECT * FROM pipeline_checkpoints WHERE thread_id = :thread_id ORDER BY step_index",
                {"thread_id": thread_id}
            )
            
            assert len(checkpoints) == 2
            assert checkpoints[0]["step_name"] == "Initial Step"
            assert checkpoints[1]["step_name"] == "Second Step"
            assert checkpoints[1]["parent_checkpoint_id"] is not None

            # Test querying by pipeline
            pipeline_checkpoints = db.execute(
                "SELECT * FROM pipeline_checkpoints WHERE pipeline_id = :pipeline_id",
                {"pipeline_id": pipeline_id}
            )
            assert len(pipeline_checkpoints) == 2

        finally:
            # Cleanup
            db.execute("DELETE FROM pipeline_checkpoints WHERE thread_id = :id", {"id": thread_id})
            


class TestConversationMemory:
    """Test conversation memory E2E"""

    @pytest.mark.asyncio
    async def test_conversation_flow(self, initialized_db):
        """Test storing and retrieving conversation messages"""
        db = initialized_db
        

        try:
            thread_id = f"thread-{uuid.uuid4()}"
            user_id = f"user-{uuid.uuid4()}"

            # Create a conversation
            messages = [
                ("user", "Hello, I need help with my pipeline"),
                ("assistant", "I'd be happy to help! What issue are you experiencing?"),
                ("user", "It's failing at step 3"),
                ("assistant", "Let me check the logs for step 3")
            ]

            base_time = datetime.now(timezone.utc)
            for idx, (role, content) in enumerate(messages):
                # Use incrementing timestamps to ensure ordering
                msg_timestamp = base_time + timedelta(seconds=idx)
                
                if db.config.database_type != DatabaseType.POSTGRESQL:
                    # For non-PostgreSQL, provide message_id
                    insert_msg = """
                    INSERT INTO conversation_messages (
                        message_id, thread_id, user_id, role, content, timestamp
                    ) VALUES (:message_id, :thread_id, :user_id, :role, :content, :timestamp)
                    """
                    
                    db.execute(insert_msg, {
                        "message_id": str(uuid.uuid4()),
                        "thread_id": thread_id,
                        "user_id": user_id,
                        "role": role,
                        "content": content,
                        "timestamp": msg_timestamp
                    })
                else:
                    insert_msg = """
                    INSERT INTO conversation_messages (
                        thread_id, user_id, role, content, timestamp
                    ) VALUES (:thread_id, :user_id, :role, :content, :timestamp)
                    """
                    
                    db.execute(insert_msg, {
                        "thread_id": thread_id,
                        "user_id": user_id,
                        "role": role,
                        "content": content,
                        "timestamp": msg_timestamp
                    })

            # Retrieve conversation
            conversation = db.execute(
                "SELECT * FROM conversation_messages WHERE thread_id = :thread_id ORDER BY timestamp",
                {"thread_id": thread_id}
            )
            
            assert len(conversation) == 4
            assert conversation[0]["role"] == "user"
            assert conversation[0]["content"] == "Hello, I need help with my pipeline"
            assert conversation[3]["role"] == "assistant"

            # Count messages by role
            user_messages = db.fetch_one(
                "SELECT COUNT(*) as count FROM conversation_messages WHERE thread_id = :thread_id AND role = :role",
                {"thread_id": thread_id, "role": "user"}
            )
            assert user_messages["count"] == 2

        finally:
            # Cleanup
            db.execute("DELETE FROM conversation_messages WHERE thread_id = :id", {"id": thread_id})
            


class TestReliabilityMetrics:
    """Test reliability metrics E2E"""

    @pytest.mark.asyncio
    async def test_step_metrics_recording(self, initialized_db):
        """Test recording and querying step reliability metrics"""
        db = initialized_db
        

        try:
            agent_name = f"test-agent-{uuid.uuid4()}"
            
            # Record successful steps
            for i in range(5):
                insert_step = """
                INSERT INTO reliability_steps (
                    agent_name, success, required_compensation, required_human,
                    mode, timestamp
                ) VALUES (:agent_name, :success, :required_compensation, :required_human,
                          :mode, :timestamp)
                """
                
                db.execute(insert_step, {
                    "agent_name": agent_name,
                    "success": True,
                    "required_compensation": False,
                    "required_human": False,
                    "mode": "autonomous",
                    "timestamp": datetime.now(timezone.utc)
                })

            # Record failed steps
            for i in range(2):
                db.execute(insert_step, {
                    "agent_name": agent_name,
                    "success": False,
                    "required_compensation": True,
                    "required_human": True,
                    "mode": "autonomous",
                    "timestamp": datetime.now(timezone.utc)
                })

            # Calculate success rate
            all_steps = db.execute(
                "SELECT * FROM reliability_steps WHERE agent_name = :agent",
                {"agent": agent_name}
            )
            assert len(all_steps) == 7

            successful = db.fetch_one(
                "SELECT COUNT(*) as count FROM reliability_steps WHERE agent_name = :agent AND success = :success",
                {"agent": agent_name, "success": True}
            )
            assert successful["count"] == 5

            failed = db.fetch_one(
                "SELECT COUNT(*) as count FROM reliability_steps WHERE agent_name = :agent AND success = :success",
                {"agent": agent_name, "success": False}
            )
            assert failed["count"] == 2

            # Test compensation rate
            compensation_needed = db.fetch_one(
                "SELECT COUNT(*) as count FROM reliability_steps WHERE agent_name = :agent AND required_compensation = :comp",
                {"agent": agent_name, "comp": True}
            )
            assert compensation_needed["count"] == 2

        finally:
            # Cleanup
            db.execute("DELETE FROM reliability_steps WHERE agent_name = :agent", {"agent": agent_name})
            


    @pytest.mark.asyncio
    async def test_workflow_metrics(self, initialized_db):
        """Test recording workflow metrics"""
        db = initialized_db
        

        try:
            workflow_id = f"workflow-{uuid.uuid4()}"
            
            # Record workflow
            insert_workflow = """
            INSERT INTO reliability_workflows (
                workflow_id, steps, retries, success, required_human, timestamp
            ) VALUES (:workflow_id, :steps, :retries, :success, :required_human, :timestamp)
            """
            
            db.execute(insert_workflow, {
                "workflow_id": workflow_id,
                "steps": 5,
                "retries": 2,
                "success": True,
                "required_human": False,
                "timestamp": datetime.now(timezone.utc)
            })

            # Verify workflow
            workflow = db.fetch_one(
                "SELECT * FROM reliability_workflows WHERE workflow_id = :id",
                {"id": workflow_id}
            )
            
            assert workflow is not None
            assert workflow["steps"] == 5
            assert workflow["retries"] == 2
            assert workflow["success"] is True or workflow["success"] == 1

        finally:
            # Cleanup
            db.execute("DELETE FROM reliability_workflows WHERE workflow_id = :id", {"id": workflow_id})
            


    @pytest.mark.asyncio
    async def test_slo_measurements(self, initialized_db):
        """Test SLO measurements (MTTE/RSR)"""
        db = initialized_db
        

        try:
            thread_id = f"thread-{uuid.uuid4()}"
            
            # Record MTTE measurements
            for i in range(3):
                insert_slo = """
                INSERT INTO reliability_slo_measurements (
                    measurement_type, thread_id, duration_ms, success, timestamp
                ) VALUES (:measurement_type, :thread_id, :duration_ms, :success, :timestamp)
                """
                
                db.execute(insert_slo, {
                    "measurement_type": "mtte",
                    "thread_id": thread_id,
                    "duration_ms": 100 + i * 50,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc)
                })

            # Record RSR measurements
            for i in range(2):
                insert_rsr = """
                INSERT INTO reliability_slo_measurements (
                    measurement_type, thread_id, replay_mode, success, timestamp
                ) VALUES (:measurement_type, :thread_id, :replay_mode, :success, :timestamp)
                """
                
                db.execute(insert_rsr, {
                    "measurement_type": "rsr",
                    "thread_id": thread_id,
                    "replay_mode": "full",
                    "success": True,
                    "timestamp": datetime.now(timezone.utc)
                })

            # Query MTTE measurements
            mtte_measurements = db.execute(
                "SELECT * FROM reliability_slo_measurements WHERE thread_id = :id AND measurement_type = :type",
                {"id": thread_id, "type": "mtte"}
            )
            assert len(mtte_measurements) == 3

            # Calculate average MTTE
            avg_mtte = db.fetch_one(
                "SELECT AVG(duration_ms) as avg_duration FROM reliability_slo_measurements WHERE thread_id = :id AND measurement_type = :type",
                {"id": thread_id, "type": "mtte"}
            )
            assert avg_mtte["avg_duration"] > 0

            # Query RSR measurements
            rsr_measurements = db.execute(
                "SELECT * FROM reliability_slo_measurements WHERE thread_id = :id AND measurement_type = :type",
                {"id": thread_id, "type": "rsr"}
            )
            assert len(rsr_measurements) == 2

        finally:
            # Cleanup
            db.execute("DELETE FROM reliability_slo_measurements WHERE thread_id = :id", {"id": thread_id})
            


class TestComplexQueries:
    """Test complex multi-table queries E2E"""

    @pytest.mark.asyncio
    async def test_pipeline_execution_with_logs(self, initialized_db):
        """Test joining pipeline executions with logs"""
        db = initialized_db
        

        try:
            pipeline_id = str(uuid.uuid4())
            execution_id = str(uuid.uuid4())
            
            # Create pipeline and execution
            db.execute(
                "INSERT INTO pipelines (id, slug, name) VALUES (:id, :slug, :name)",
                {"id": pipeline_id, "slug": f"test-{pipeline_id[:8]}", "name": "Test"}
            )
            
            db.execute(
                """INSERT INTO pipeline_executions (execution_id, pipeline_id, status, started_at, total_steps)
                   VALUES (:execution_id, :pipeline_id, :status, :started_at, :total_steps)""",
                {"execution_id": execution_id, "pipeline_id": pipeline_id, "status": "completed",
                 "started_at": datetime.now(timezone.utc), "total_steps": 1}
            )

            # Add logs
            for i in range(5):
                db.execute(
                    """INSERT INTO execution_logs (execution_id, log_level, message, timestamp)
                       VALUES (:execution_id, :log_level, :message, :timestamp)""",
                    {"execution_id": execution_id, "log_level": "INFO",
                     "message": f"Log message {i}", "timestamp": datetime.now(timezone.utc)}
                )

            # Query execution with log count
            query = """
            SELECT e.execution_id, e.status, COUNT(l.id) as log_count
            FROM pipeline_executions e
            LEFT JOIN execution_logs l ON e.execution_id = l.execution_id
            WHERE e.execution_id = :id
            GROUP BY e.execution_id, e.status
            """
            
            result = db.fetch_one(query, {"id": execution_id})
            assert result is not None
            assert result["log_count"] == 5
            assert result["status"] == "completed"

        finally:
            # Cleanup
            db.execute("DELETE FROM execution_logs WHERE execution_id = :id", {"id": execution_id})
            db.execute("DELETE FROM pipeline_executions WHERE execution_id = :id", {"id": execution_id})
            db.execute("DELETE FROM pipelines WHERE id = :id", {"id": pipeline_id})
            


    @pytest.mark.asyncio
    async def test_time_range_queries(self, initialized_db):
        """Test querying data by time ranges"""
        db = initialized_db
        

        try:
            agent_name = f"time-test-{uuid.uuid4()}"
            
            # Insert steps over time
            now = datetime.now(timezone.utc)
            timestamps = [
                now - timedelta(hours=2),
                now - timedelta(hours=1),
                now - timedelta(minutes=30),
                now
            ]
            
            for ts in timestamps:
                db.execute(
                    """INSERT INTO reliability_steps (agent_name, success, timestamp)
                       VALUES (:agent_name, :success, :timestamp)""",
                    {"agent_name": agent_name, "success": True, "timestamp": ts}
                )

            # Query last hour
            one_hour_ago = now - timedelta(hours=1)
            recent_steps = db.execute(
                "SELECT * FROM reliability_steps WHERE agent_name = :agent AND timestamp >= :since",
                {"agent": agent_name, "since": one_hour_ago}
            )
            
            # MySQL may have less precision in timestamps, so we expect 2 or 3 results
            assert len(recent_steps) >= 2 and len(recent_steps) <= 3

            # Query all time
            all_steps = db.execute(
                "SELECT * FROM reliability_steps WHERE agent_name = :agent",
                {"agent": agent_name}
            )
            assert len(all_steps) == 4

        finally:
            # Cleanup
            db.execute("DELETE FROM reliability_steps WHERE agent_name = :agent", {"agent": agent_name})
            


class TestTransactionBehavior:
    """Test transaction handling E2E"""

    @pytest.mark.asyncio
    async def test_rollback_on_error(self, initialized_db):
        """Test that failed transactions are rolled back"""
        db = initialized_db
        

        try:
            pipeline_id = str(uuid.uuid4())
            
            # Start a transaction and intentionally cause an error
            db.execute(
                "INSERT INTO pipelines (id, slug, name) VALUES (:id, :slug, :name)",
                {"id": pipeline_id, "slug": f"test-{pipeline_id[:8]}", "name": "Test"}
            )
            
            # Verify it was inserted
            result = db.fetch_one("SELECT * FROM pipelines WHERE id = :id", {"id": pipeline_id})
            assert result is not None

            # Try to insert duplicate (should fail)
            try:
                db.execute(
                    "INSERT INTO pipelines (id, slug, name) VALUES (:id, :slug, :name)",
                    {"id": pipeline_id, "slug": f"test-{pipeline_id[:8]}", "name": "Test2"}
                )
            except Exception:
                pass  # Expected to fail

            # Original record should still exist
            result = db.fetch_one("SELECT * FROM pipelines WHERE id = :id", {"id": pipeline_id})
            assert result is not None
            assert result["name"] == "Test"

        finally:
            # Cleanup
            db.execute("DELETE FROM pipelines WHERE id = :id", {"id": pipeline_id})
            


class TestDataIntegrity:
    """Test data integrity constraints E2E"""

    @pytest.mark.asyncio
    async def test_foreign_key_integrity(self, initialized_db):
        """Test foreign key constraints"""
        db = initialized_db
        

        try:
            execution_id = str(uuid.uuid4())
            step_exec_id = str(uuid.uuid4())
            
            # Create execution
            db.execute(
                """INSERT INTO pipeline_executions (execution_id, status, started_at, total_steps)
                   VALUES (:execution_id, :status, :started_at, :total_steps)""",
                {"execution_id": execution_id, "status": "running",
                 "started_at": datetime.now(timezone.utc), "total_steps": 1}
            )

            # Create step execution (valid FK)
            db.execute(
                """INSERT INTO step_executions (step_execution_id, execution_id, step_id, step_name, status, started_at, step_order)
                   VALUES (:step_execution_id, :execution_id, :step_id, :step_name, :status, :started_at, :step_order)""",
                {"step_execution_id": step_exec_id, "execution_id": execution_id,
                 "step_id": "step1", "step_name": "Test Step", "status": "completed",
                 "started_at": datetime.now(timezone.utc), "step_order": 0}
            )

            # Verify step was created
            step = db.fetch_one("SELECT * FROM step_executions WHERE step_execution_id = :id", {"id": step_exec_id})
            assert step is not None
            assert step["execution_id"] == execution_id

            # Clean up in correct order (child first)
            db.execute("DELETE FROM step_executions WHERE step_execution_id = :id", {"id": step_exec_id})
            db.execute("DELETE FROM pipeline_executions WHERE execution_id = :id", {"id": execution_id})

        finally:
            pass


    @pytest.mark.asyncio
    async def test_unique_constraints(self, initialized_db):
        """Test unique constraints on slug fields"""
        db = initialized_db
        

        try:
            pipeline_id_1 = str(uuid.uuid4())
            pipeline_id_2 = str(uuid.uuid4())
            slug = f"unique-test-{uuid.uuid4()}"
            
            # Insert first pipeline
            db.execute(
                "INSERT INTO pipelines (id, slug, name) VALUES (:id, :slug, :name)",
                {"id": pipeline_id_1, "slug": slug, "name": "First"}
            )

            # Try to insert second pipeline with same slug (should fail)
            with pytest.raises(Exception):
                db.execute(
                    "INSERT INTO pipelines (id, slug, name) VALUES (:id, :slug, :name)",
                    {"id": pipeline_id_2, "slug": slug, "name": "Second"}
                )

            # Verify only one exists
            count = db.fetch_one("SELECT COUNT(*) as count FROM pipelines WHERE slug = :slug", {"slug": slug})
            assert count["count"] == 1

        finally:
            # Cleanup
            db.execute("DELETE FROM pipelines WHERE slug = :slug", {"slug": slug})
            
