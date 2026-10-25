# Pipeline Execution Architecture

## Overview

The ia_modules pipeline system has **ONE executor** and **ONE tracker**, both using the **ServiceRegistry** pattern for dependency injection. Neither is hardcoded to a specific storage backend.

**ExecutionContext:** As of the refactor, execution-specific data (execution_id, pipeline_id, user_id, thread_id) is passed via ExecutionContext parameter instead of through services.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    ServiceRegistry                               │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │  Database    │  │   Tracker    │                            │
│  │  Manager     │  │              │                            │
│  │ (from nexusql)  │              │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
           │                  │
           ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Pipeline                                  │
│  - Loads and executes steps                                     │
│  - Determines execution order from flow                         │
│  - Calls tracker via services (optional)                        │
│  - Uses ExecutionContext parameter (execution_id, pipeline_id)  │
│  - Stores in-memory results format                              │
└─────────────────────────────────────────────────────────────────┘
           ▲
           │
  ┌────────────────┐
  │ ExecutionContext│
  │ - execution_id  │
  │ - pipeline_id   │
  │ - user_id       │
  │ - thread_id     │
  │ - metadata      │
  └────────────────┘
```

## Component Breakdown

### 1. Pipeline Executor (THE ONLY EXECUTOR)

**Location:** `ia_modules/pipeline/core.py` - `Pipeline` class

**Purpose:** Orchestrates step execution, determines order, runs code

**Storage:** In-memory results only (no database coupling)

**Key Methods:**
- `run()` - Entry point for pipeline execution
- `_build_execution_path()` - Determines step order from flow config
- `_execute_pipeline()` - Executes steps in order

**Uses ServiceRegistry for:**
- `execution_tracker` - Optional tracking (NOT hardcoded)
- `execution_id` - Current execution identifier
- `checkpointer` - Optional checkpoint storage
- `telemetry` - Optional observability
- `database` - Available to steps via services
- `http` - Available to steps via services

**Returns format:**
```python
{
    "input": {...},
    "output": {...},
    "steps": [
        {
            "step_name": "step1",
            "step_index": 0,
            "result": {...},      # Step output stored here
            "status": "completed"
        }
    ]
}
```

**NOT hardcoded to storage!** The Pipeline itself only maintains in-memory state. It optionally calls the tracker if one is registered in services.

---

### 2. ExecutionTracker (THE ONLY TRACKER)

**Location:** `ia_modules/pipeline/execution_tracker.py` - `ExecutionTracker` class

**Purpose:** Persists execution metadata, timing, and I/O for historical analysis

**Storage:** Uses injected DatabaseManager (NOT hardcoded to PostgreSQL!)

**Constructor:**
```python
class ExecutionTracker:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager  # Injected dependency
        self.active_executions: Dict[str, ExecutionRecord] = {}
```

**Key Methods:**
- `start_execution()` - Create execution record in database
- `start_step_execution()` - Create step record in database
- `complete_step_execution()` - Update step with results
- `get_execution()` - Load execution from database
- `get_execution_steps()` - Load step details from database

**Database Schema:**
- `pipeline_executions` table - Execution-level tracking
- `step_executions` table - Step-level tracking

**Returns format:**
```python
{
    "step_id": "step1",
    "step_name": "Data Preparation",
    "step_type": "task",
    "status": "completed",
    "started_at": "2025-10-24T10:00:00.123456",
    "completed_at": "2025-10-24T10:00:01.234567",
    "input_data": {...},          # Full input JSON
    "output_data": {...},         # Full output JSON
    "execution_time_ms": 1111,
    "retry_count": 0,
    "error_message": null,
    "metadata": {...}
}
```

**NOT hardcoded to PostgreSQL!** Uses the generic `DatabaseManager` interface which can be backed by:
- PostgreSQL (production)
- SQLite (testing/development)
- Any database with a DatabaseManager adapter

---

## Execution Flow

### Step-by-Step Process

```
1. Application creates ServiceRegistry
   ├─ Registers DatabaseManager (from nexusql)
   ├─ Creates ExecutionTracker(db_manager)
   └─ Registers tracker in services

2. Pipeline execution starts
   ├─ Pipeline.__init__(services=service_registry)
   ├─ Create ExecutionContext(execution_id='job-123', pipeline_id='pipe-456')
   └─ Call pipeline.run(input_data, execution_context)

3. For each step:
   ├─ Pipeline gets tracker: self.services.get('execution_tracker')
   ├─ Get execution_id from execution_context.execution_id
   │
   ├─ IF tracker exists:
   │  └─ tracker.start_step_execution(execution_id, ...) → Database INSERT
   │
   ├─ Pipeline executes step code
   │  └─ await step.run(data)
   │
   ├─ IF tracker exists:
   │  └─ tracker.complete_step_execution() → Database UPDATE
   │
   └─ Pipeline stores in-memory result
      └─ results["steps"].append({"step_name", "result", "status"})

4. Pipeline returns in-memory results
   └─ {"input", "output", "steps": [...]}

5. Tracker data persists in database
   └─ Available for historical queries
```

### Code Example

**From `pipeline_service.py`:**

```python
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR
from ia_modules.pipeline.core import ExecutionContext
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.execution_tracker import ExecutionTracker

# 1. Setup services (dependency injection)
self.services = ServiceRegistry()
db_manager = DatabaseManager(database_url)
# ia_modules' tables (pipeline_executions, step_executions, ...) come from its own migrations
await db_manager.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])
self.services.register('database', db_manager)

# 2. Create tracker with injected database
self.tracker = ExecutionTracker(db_manager)

# 3. Register tracker in services
self.services.register('execution_tracker', self.tracker)

# 4. Create execution context
execution_context = ExecutionContext(
    execution_id='job-123',
    pipeline_id='pipe-456',
    user_id='user-789'
)

# 5. Execute pipeline
graph_runner = GraphPipelineRunner(self.services)
result = await graph_runner.run_pipeline_from_json(
    config,
    input_data,
    execution_context  # Required!
)
```

**From `core.py` (Pipeline execution):**

```python
# Pipeline OPTIONALLY uses tracker via services
tracker = self.services.get('execution_tracker') if self.services else None
execution_id = execution_context.execution_id  # From ExecutionContext parameter

if tracker and execution_id:
    # Track to database (optional!)
    step_execution_id = await tracker.start_step_execution(
        execution_id=execution_context.execution_id,
        pipeline_id=execution_context.pipeline_id or self.name,
        step_id=current_step_name,
        step_name=current_step_name,
        ...
    )

# Execute the actual step
step_result = await step.run(current_data)

if tracker and step_execution_id:
    # Update database (optional!)
    await tracker.complete_step_execution(...)

# ALWAYS store in-memory result
results["steps"].append({
    "step_name": step_name,
    "result": step_result,
    "status": "completed"
})
```

---

## Two Data Formats Explained

### Why Two Formats?

The **Pipeline** and **ExecutionTracker** serve different purposes:

| Aspect | Pipeline Results | ExecutionTracker Records |
|--------|-----------------|-------------------------|
| **Purpose** | Runtime execution data | Historical analysis & debugging |
| **Lifetime** | In-memory only | Persistent in database |
| **Scope** | Current execution | All executions ever |
| **Detail Level** | Minimal (just results) | Comprehensive (I/O, timing, metadata) |
| **Access Pattern** | Sequential processing | Random access queries |

### Format Comparison

**Pipeline In-Memory Format:**
```python
{
    "step_name": "step1",
    "step_index": 0,
    "result": {                    # Combined output
        "transformed_topic": "...",
        "additional_data": "..."
    },
    "status": "completed"
}
```

**ExecutionTracker Database Format:**
```python
{
    "step_id": "step1",
    "step_name": "Data Preparation",
    "step_type": "task",
    "status": "completed",
    "started_at": "2025-10-24T10:00:00.123456",  # Precise timing
    "completed_at": "2025-10-24T10:00:01.234567",
    "input_data": {                              # Separate input
        "topic": "machine learning"
    },
    "output_data": {                             # Separate output
        "transformed_topic": "PROCESSED_MACHINE_LEARNING"
    },
    "execution_time_ms": 1111,                   # Calculated duration
    "retry_count": 0,                            # Retry tracking
    "error_message": null,
    "metadata": {                                # Additional context
        "source": "user_request",
        "priority": "high"
    }
}
```

---

## Dynamic Step Loading

### How Steps Get Loaded and Executed

**File:** `ia_modules/pipeline/runner.py`

```python
def load_step_class(module_path: str, class_name: str):
    """Dynamically import step class using Python's importlib"""
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

def create_step_from_json(step_def: Dict[str, Any]) -> Step:
    """Create step instance from JSON definition"""
    # Load the class dynamically
    step_class = load_step_class(
        step_def['module'],        # e.g., "tests.pipelines.simple_pipeline.steps.step1"
        step_def['step_class']     # e.g., "Step1"
    )
    
    # Instantiate the class
    step_name = step_def.get('id', 'Unknown')
    return step_class(step_name, config)
```

**Example JSON:**
```json
{
    "id": "step1",
    "name": "Data Preparation",
    "step_class": "Step1",
    "module": "tests.pipelines.simple_pipeline.steps.step1",
    "config": {}
}
```

**Loads this Python file:**
```python
# tests/pipelines/simple_pipeline/steps/step1.py
from ia_modules.pipeline.core import Step

class Step1(Step):
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        topic = input.get("topic")
        transformed = f"PROCESSED_{topic.upper()}"
        return {"topic": transformed}
```

---

## Execution Order Determination

**File:** `ia_modules/pipeline/core.py`

```python
def _build_execution_path(self) -> List[str]:
    """Build the execution path based on flow definition"""
    paths = self.flow.get("paths", [])
    step_order = []
    visited = set()
    
    # Start with start_at
    start_step = self.flow.get("start_at")
    step_order.append(start_step)
    visited.add(start_step)
    
    # Follow the paths
    for path in paths:
        from_step = path.get("from")
        to_step = path.get("to")
        
        if from_step in step_order and to_step not in visited:
            step_order.append(to_step)
            visited.add(to_step)
    
    return step_order
```

**From JSON flow:**
```json
{
    "flow": {
        "start_at": "step1",
        "paths": [
            {"from": "step1", "to": "step2"},
            {"from": "step2", "to": "step3"}
        ]
    }
}
```

**Produces execution order:** `["step1", "step2", "step3"]`

---

## Service Injection Pattern

### Why Not Hardcoded?

The system uses **Dependency Injection** via `ServiceRegistry`:

**Benefits:**
1. **Testability** - Mock databases for testing
2. **Flexibility** - Swap PostgreSQL for SQLite
3. **Decoupling** - Pipeline doesn't know about database
4. **Optional Features** - Tracker is optional, not required

### Example: Testing Without Database

```python
# Production: With tracking
services = ServiceRegistry()
services.register('database', PostgreSQLManager(...))
services.register('execution_tracker', ExecutionTracker(db))
pipeline = Pipeline(name, steps, flow, services)

# Testing: Without tracking (faster!)
services = ServiceRegistry()
# Don't register tracker - pipeline still works!
pipeline = Pipeline(name, steps, flow, services)
```

### Example: Swapping Databases

```python
# PostgreSQL (production)
db = DatabaseManager("postgresql://user:pass@localhost:5432/app")

# SQLite (development)
db = DatabaseManager("sqlite:///test.db")

# Either way, create ia_modules' tables first
await db.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])

# Same code works with both!
tracker = ExecutionTracker(db)
```

---

## API Response Formats

### The Problem We Fixed

**Before Fix:** API returned in-memory format (missing timing/I/O data)

```python
# OLD: pipeline_service.py
async def get_execution(self, job_id: str):
    if job_id in self.executions:
        return self.executions[job_id]  # In-memory format
    # Database format only if not in memory
```

**After Fix:** API always returns database format (complete data)

```python
# NEW: pipeline_service.py
async def get_execution(self, job_id: str):
    # Always load from database for complete data
    if self.tracker:
        record = await self.tracker.get_execution(job_id)
        step_records = await self.tracker.get_execution_steps(job_id)
        # Return database format with all details
```

---

## Summary

### Key Points

1. **ONE Executor:** The `Pipeline` class is the only thing that runs steps
2. **ONE Tracker:** The `ExecutionTracker` class is the only thing that persists to database
3. **NOT Hardcoded:** Both use `ServiceRegistry` for dependency injection
4. **Database Agnostic:** Tracker works with PostgreSQL, SQLite, or any DatabaseManager adapter
5. **Optional Tracking:** Pipeline works with or without tracker
6. **Two Formats:** In-memory for execution, database for analysis

### Dependency Flow

```
Application
    └─ Creates DatabaseManager (PostgreSQL or SQLite)
        └─ Creates ExecutionTracker(db_manager)
            └─ Creates ServiceRegistry
                └─ Registers: database, execution_tracker, execution_id
                    └─ Creates Pipeline(services)
                        └─ Pipeline optionally uses tracker via services.get()
```

### Remember

- **ExecutionTracker is NOT hardcoded to PostgreSQL** - it accepts any DatabaseManager
- **Pipeline is NOT hardcoded to ExecutionTracker** - it optionally gets it from services
- **Both use Dependency Injection** - clean, testable, flexible architecture
- **Two different data formats** - in-memory for execution, database for persistence
