# IA Modules - Developer Guide

## Overview

This comprehensive developer guide covers everything needed to work with, extend, and contribute to the IA Modules framework. Whether you're building custom pipeline steps, integrating the framework into applications, or contributing to the core library, this guide provides detailed instructions and best practices.

**Important Updates:**
- **ExecutionContext**: Pipeline.run() now requires an ExecutionContext parameter containing execution_id, pipeline_id, user_id, and thread_id
- **Database**: Uses `nexusql.DatabaseManager` (external package, 0.4.0+) instead of `ia_modules.database.manager`. nexusql does not create ia_modules' tables: pass `ia_modules.database.MIGRATIONS_DIR` to `initialize()` (or use `get_database()`, which does it for you). nexusql's `DatabaseManager` has no `fetch_all()`; `execute()` returns the rows as a list of dicts
- **Service Registry**: execution_id is no longer registered in services - it comes from ExecutionContext

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Project Structure](#project-structure)
- [Building Custom Steps](#building-custom-steps)
- [Creating Pipelines](#creating-pipelines)
- [Database Integration](#database-integration)
- [Service Integration](#service-integration)
- [Testing Your Code](#testing-your-code)
- [Contributing Guidelines](#contributing-guidelines)
- [Deployment Strategies](#deployment-strategies)
- [Troubleshooting](#troubleshooting)
- [Performance Optimization](#performance-optimization)

## Getting Started

### Prerequisites

**Python Environment:**
- Python 3.11 or higher
- pip package manager
- Virtual environment support (venv or conda)

**Development Tools:**
- Git for version control
- Code editor with Python support (VS Code, PyCharm, etc.)
- Command line terminal

### Quick Start

```bash
# Clone the repository
git clone https://github.com/matterwaveai/ia_modules.git
cd ia_modules

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate
# Activate virtual environment (macOS/Linux)
source venv/bin/activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install pytest pytest-asyncio pytest-mock pytest-cov black flake8

# Verify installation
python -c "from ia_modules.pipeline.core import Step; print('✓ IA Modules installed successfully')"
```

## Development Environment Setup

### Recommended Directory Structure

```
my_project/
├── venv/                    # Virtual environment
├── pipelines/               # Pipeline JSON configurations
│   ├── data_processing.json
│   ├── ai_analysis.json
│   └── batch_processing.json
├── steps/                   # Custom step implementations
│   ├── __init__.py
│   ├── data_steps.py
│   ├── analysis_steps.py
│   └── output_steps.py
├── migrations/              # Database migrations
│   ├── V001__initial_schema.sql
│   └── V002__add_indexes.sql
├── tests/                   # Test files
│   ├── test_steps.py
│   ├── test_pipelines.py
│   └── conftest.py
├── config/                  # Configuration files
│   ├── development.py
│   ├── production.py
│   └── testing.py
├── main.py                  # Application entry point
├── requirements.txt         # Dependencies
└── README.md               # Project documentation
```

### Environment Configuration

Create a `.env` file for environment-specific settings:

```bash
# .env
DATABASE_URL=sqlite:///./app_data.db
LOG_LEVEL=INFO
PIPELINE_DIR=./pipelines
MIGRATION_DIR=./migrations

# Development settings
DEBUG=true
ENABLE_LOGGING=true

# Production settings (comment out for development)
# DEBUG=false
# DATABASE_URL=postgresql://user:pass@prod-db:5432/app_db
```

### IDE Configuration

#### VS Code Settings

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8

  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: [tests/]
```

## Project Structure

### Core Modules Overview

```
ia_modules/
├── __init__.py
├── pipeline/               # Core pipeline execution
│   ├── __init__.py
│   ├── core.py            # Step, Pipeline, TemplateParameterResolver
│   ├── runner.py          # Pipeline execution functions
│   ├── services.py        # ServiceRegistry, logging
│   ├── routing.py         # Flow control logic
│   ├── enhanced_pipeline.py # Advanced pipeline features
│   ├── importer.py        # Pipeline import service
│   └── condition_functions.py # Conditional logic
├── database/              # Database abstraction
│   ├── __init__.py
│   ├── interfaces.py      # Abstract database interfaces
│   ├── manager.py         # Database manager implementation
│   ├── migrations.py      # Migration system
│   └── migrations/        # SQL migration files
├── auth/                  # Authentication system
│   ├── __init__.py
│   ├── models.py          # User models
│   ├── middleware.py      # Authentication middleware
│   ├── security.py        # Security utilities
│   └── session.py         # Session management
├── web/                   # Web utilities
│   ├── __init__.py
│   ├── database.py        # Web-specific database utilities
│   └── execution_tracker.py # Pipeline execution tracking
└── tests/                 # Test suite
    ├── unit/              # Unit tests
    ├── integration/       # Integration tests
    ├── e2e/              # End-to-end tests
    ├── pipelines/         # Test pipelines
    └── fixtures/          # Test fixtures
```

## Building Custom Steps

### Basic Step Implementation

```python
# steps/my_custom_steps.py
from ia_modules.pipeline.core import Step
from typing import Dict, Any
import asyncio

class DataTransformStep(Step):
    """Transform input data according to configuration"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Access step configuration
        transform_type = self.config.get('transform_type', 'uppercase')
        field_name = self.config.get('field_name', 'text')

        # Access input data
        input_text = data.get(field_name, '')

        # Perform transformation
        if transform_type == 'uppercase':
            transformed = input_text.upper()
        elif transform_type == 'lowercase':
            transformed = input_text.lower()
        elif transform_type == 'reverse':
            transformed = input_text[::-1]
        else:
            transformed = input_text

        return {
            'transformed_text': transformed,
            'original_text': input_text,
            'transform_type': transform_type,
            'status': 'success'
        }

class DatabaseWriterStep(Step):
    """Write data to database using injected service"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Access database service
        db = self.get_db()
        if not db:
            return {
                'error': 'Database service not available',
                'status': 'failed'
            }

        # Get configuration
        table_name = self.config.get('table_name', 'processed_data')

        # Prepare data for insertion
        record_data = {
            'content': data.get('transformed_text', ''),
            'metadata': str(data),
            'processed_at': 'CURRENT_TIMESTAMP'
        }

        try:
            # Execute database operation
            db.execute(
                f"INSERT INTO {table_name} (content, metadata, processed_at) VALUES (?, ?, datetime('now'))",
                (record_data['content'], record_data['metadata'])
            )

            return {
                'database_write': 'success',
                'table': table_name,
                'record_count': 1,
                'status': 'success'
            }

        except Exception as e:
            return {
                'error': f'Database write failed: {str(e)}',
                'status': 'failed'
            }

class APICallStep(Step):
    """Make HTTP API calls using injected HTTP service"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Access HTTP service
        http = self.get_http()
        if not http:
            return {'error': 'HTTP service not available'}

        # Get configuration
        api_url = self.config.get('api_url')
        method = self.config.get('method', 'GET')
        timeout = self.config.get('timeout', 30)

        if not api_url:
            return {'error': 'API URL not configured'}

        try:
            # Make API call
            if method.upper() == 'GET':
                response = await http.get(api_url, timeout=timeout)
            elif method.upper() == 'POST':
                payload = data.get('api_payload', {})
                response = await http.post(api_url, json=payload, timeout=timeout)
            else:
                return {'error': f'Unsupported HTTP method: {method}'}

            return {
                'api_response': response.json(),
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'status': 'success'
            }

        except Exception as e:
            return {
                'error': f'API call failed: {str(e)}',
                'status': 'failed'
            }

class ConditionalProcessingStep(Step):
    """Demonstrate conditional logic within a step"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Get input value for condition
        score = data.get('quality_score', 0.0)
        threshold = self.config.get('threshold', 0.5)

        if score > threshold:
            # High quality processing
            result = await self._process_high_quality(data)
            processing_type = 'high_quality'
        else:
            # Standard processing
            result = await self._process_standard(data)
            processing_type = 'standard'

        return {
            'processed_result': result,
            'processing_type': processing_type,
            'quality_score': score,
            'threshold_used': threshold,
            'status': 'success'
        }

    async def _process_high_quality(self, data: Dict[str, Any]) -> Dict:
        """High quality processing logic"""
        await asyncio.sleep(0.1)  # Simulate processing time
        return {
            'algorithm': 'advanced',
            'confidence': 0.95,
            'details': 'Applied advanced processing algorithms'
        }

    async def _process_standard(self, data: Dict[str, Any]) -> Dict:
        """Standard processing logic"""
        await asyncio.sleep(0.05)  # Simulate processing time
        return {
            'algorithm': 'standard',
            'confidence': 0.75,
            'details': 'Applied standard processing'
        }
```

### Advanced Step Patterns

#### Error Handling Step

```python
class RobustProcessingStep(Step):
    """Step with comprehensive error handling"""

    async def run(self, data: Dict[str, Any]) -> Any:
        try:
            # Validate inputs
            required_fields = self.config.get('required_fields', [])
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Required field '{field}' missing from input data")

            # Perform processing
            result = await self._safe_processing(data)

            return {
                'result': result,
                'status': 'success',
                'errors': []
            }

        except ValueError as e:
            # Handle validation errors
            return {
                'error': str(e),
                'error_type': 'validation',
                'status': 'failed'
            }

        except Exception as e:
            # Handle unexpected errors
            return {
                'error': str(e),
                'error_type': 'processing',
                'status': 'failed'
            }

    async def _safe_processing(self, data: Dict[str, Any]) -> Any:
        """Processing logic with error handling"""
        # Implementation here
        pass
```

#### Batch Processing Step

```python
class BatchProcessingStep(Step):
    """Process data in batches for better performance"""

    async def run(self, data: Dict[str, Any]) -> Any:
        items = data.get('items', [])
        batch_size = self.config.get('batch_size', 100)

        results = []
        errors = []

        # Process in batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            try:
                batch_result = await self._process_batch(batch)
                results.extend(batch_result)
            except Exception as e:
                errors.append({
                    'batch_start': i,
                    'batch_size': len(batch),
                    'error': str(e)
                })

        return {
            'processed_items': results,
            'total_processed': len(results),
            'errors': errors,
            'status': 'success' if not errors else 'partial_success'
        }

    async def _process_batch(self, batch: list) -> list:
        """Process a single batch of items"""
        # Implement batch processing logic
        return [{'processed': item} for item in batch]
```

## Creating Pipelines

### Pipeline Configuration

```json
{
    "name": "Custom Data Processing Pipeline",
    "description": "Process data through multiple transformation stages",
    "version": "2.0.0",
    "parameters": {
        "input_source": "api",
        "output_format": "json",
        "enable_validation": true,
        "quality_threshold": 0.8
    },
    "steps": [
        {
            "id": "data_loader",
            "name": "Load Input Data",
            "step_class": "DataLoaderStep",
            "module": "steps.data_steps",
            "config": {
                "source_type": "{{ parameters.input_source }}",
                "validation_enabled": "{{ parameters.enable_validation }}"
            }
        },
        {
            "id": "data_cleaner",
            "name": "Clean Data",
            "step_class": "DataCleanerStep",
            "module": "steps.data_steps",
            "inputs": {
                "raw_data": "{{ data_loader.loaded_data }}"
            }
        },
        {
            "id": "quality_checker",
            "name": "Check Data Quality",
            "step_class": "QualityCheckerStep",
            "module": "steps.analysis_steps",
            "inputs": {
                "cleaned_data": "{{ data_cleaner.cleaned_data }}"
            },
            "config": {
                "threshold": "{{ parameters.quality_threshold }}"
            }
        },
        {
            "id": "advanced_processor",
            "name": "Advanced Processing",
            "step_class": "AdvancedProcessorStep",
            "module": "steps.analysis_steps",
            "inputs": {
                "data": "{{ quality_checker.validated_data }}"
            }
        },
        {
            "id": "standard_processor",
            "name": "Standard Processing",
            "step_class": "StandardProcessorStep",
            "module": "steps.analysis_steps",
            "inputs": {
                "data": "{{ quality_checker.validated_data }}"
            }
        },
        {
            "id": "output_formatter",
            "name": "Format Output",
            "step_class": "OutputFormatterStep",
            "module": "steps.output_steps",
            "inputs": {
                "processed_data": "{{ advanced_processor.result || standard_processor.result }}"
            },
            "config": {
                "format": "{{ parameters.output_format }}"
            }
        }
    ],
    "flow": {
        "start_at": "data_loader",
        "paths": [
            {
                "from": "data_loader",
                "to": "data_cleaner",
                "condition": {"type": "always"}
            },
            {
                "from": "data_cleaner",
                "to": "quality_checker",
                "condition": {"type": "always"}
            },
            {
                "from": "quality_checker",
                "to": "advanced_processor",
                "condition": {
                    "type": "expression",
                    "config": {
                        "source": "result.quality_score",
                        "operator": "greater_than",
                        "value": 0.8
                    }
                }
            },
            {
                "from": "quality_checker",
                "to": "standard_processor",
                "condition": {
                    "type": "expression",
                    "config": {
                        "source": "result.quality_score",
                        "operator": "less_than_or_equal",
                        "value": 0.8
                    }
                }
            },
            {
                "from": "advanced_processor",
                "to": "output_formatter",
                "condition": {"type": "always"}
            },
            {
                "from": "standard_processor",
                "to": "output_formatter",
                "condition": {"type": "always"}
            }
        ]
    },
    "outputs": {
        "final_result": "{{ output_formatter.formatted_output }}",
        "processing_metadata": {
            "quality_score": "{{ quality_checker.quality_score }}",
            "processing_type": "{{ advanced_processor.processing_type || standard_processor.processing_type }}",
            "total_records": "{{ output_formatter.record_count }}"
        }
    }
}
```

### Pipeline Execution

```python
# main.py
import asyncio
import os
from pathlib import Path

from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR
from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.core import ExecutionContext

async def main():
    # Setup database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./app_data.db')
    db_manager = DatabaseManager(database_url)

    # Initialize with ia_modules' migrations, then the app's own
    migration_dirs = [str(MIGRATIONS_DIR), './migrations']
    await db_manager.initialize(apply_schema=True, app_migration_paths=migration_dirs)

    # Setup services
    services = ServiceRegistry()
    services.register('database', db_manager)

    # Setup HTTP client if needed
    import aiohttp
    async with aiohttp.ClientSession() as session:
        services.register('http', session)

        # Create execution context
        execution_context = ExecutionContext(
            execution_id='job-123',
            pipeline_id='custom_processing',
            user_id='user-789'
        )

        # Execute pipeline
        result = await run_pipeline_from_json(
            pipeline_file='./pipelines/custom_processing.json',
            input_data={
                'source_data': './data/input.csv',
                'processing_mode': 'batch'
            },
            services=services,
            execution_context=execution_context
        )

        print("Pipeline execution completed!")
        print(f"Final result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Database Integration

### Database Setup

```python
# config/database.py
import os
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR

class DatabaseConfig:
    @staticmethod
    def get_database_manager():
        """Get configured database manager"""

        # Environment-based configuration
        env = os.getenv('ENVIRONMENT', 'development')

        if env == 'development':
            database_url = 'sqlite:///./dev_data.db'
        elif env == 'testing':
            database_url = 'sqlite:///:memory:'
        elif env == 'production':
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL environment variable required for production")
        else:
            raise ValueError(f"Unknown environment: {env}")

        return DatabaseManager(database_url)

    @staticmethod
    async def initialize_database():
        """Initialize database with migrations"""
        db_manager = DatabaseConfig.get_database_manager()

        # Define migration paths
        migration_paths = [
            str(MIGRATIONS_DIR),  # ia_modules' own tables
            './migrations',  # Application migrations
            './custom_migrations'  # Custom migrations
        ]

        success = await db_manager.initialize(
            apply_schema=True,
            app_migration_paths=migration_paths
        )

        if not success:
            raise RuntimeError("Database initialization failed")

        return db_manager
```

### Custom Migration

```sql
-- migrations/V003__add_pipeline_results_table.sql

-- Create table for storing pipeline execution results
CREATE TABLE IF NOT EXISTS pipeline_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    pipeline_name TEXT NOT NULL,
    input_data TEXT,  -- JSON
    output_data TEXT, -- JSON
    execution_time_ms INTEGER,
    status TEXT CHECK (status IN ('success', 'failed', 'partial')) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_pipeline_results_execution_id ON pipeline_results(execution_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_pipeline_name ON pipeline_results(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_status ON pipeline_results(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_created_at ON pipeline_results(created_at);

-- Create trigger for updated_at
CREATE TRIGGER IF NOT EXISTS update_pipeline_results_updated_at
    AFTER UPDATE ON pipeline_results
    FOR EACH ROW
    BEGIN
        UPDATE pipeline_results SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
```

### Database-Aware Steps

```python
class PersistentAnalysisStep(Step):
    """Step that persists analysis results to database

    Note: execution_id should be passed via context or stored in step config
    """

    async def run(self, data: Dict[str, Any]) -> Any:
        db = self.get_db()
        if not db:
            raise RuntimeError("Database service required for persistent analysis")

        # Perform analysis
        analysis_result = await self._perform_analysis(data)

        # Get execution_id from data context (passed from Pipeline)
        execution_id = data.get('_execution_id', 'unknown')

        try:
            db.execute("""
                INSERT INTO analysis_results (
                    execution_id, step_name, input_summary, analysis_data,
                    confidence_score, created_at
                ) VALUES (:execution_id, :step_name, :input_summary, :analysis_data,
                          :confidence_score, CURRENT_TIMESTAMP)
            """, {
                'execution_id': execution_id,
                'step_name': self.name,
                'input_summary': str(data)[:500],  # Truncated summary
                'analysis_data': json.dumps(analysis_result),
                'confidence_score': analysis_result.get('confidence', 0.0),
            })

            # Retrieve historical data for comparison. nexusql's DatabaseManager has no
            # fetch_all(); execute() returns the rows as a list of dicts.
            historical_data = db.execute("""
                SELECT analysis_data, confidence_score, created_at
                FROM analysis_results
                WHERE step_name = :step_name
                ORDER BY created_at DESC
                LIMIT 10
            """, {'step_name': self.name})

            return {
                'analysis_result': analysis_result,
                'historical_comparison': self._compare_with_history(analysis_result, historical_data),
                'database_stored': True,
                'status': 'success'
            }

        except Exception as e:
            return {
                'analysis_result': analysis_result,
                'database_error': str(e),
                'database_stored': False,
                'status': 'partial_success'
            }

    async def _perform_analysis(self, data: Dict[str, Any]) -> Dict:
        """Perform the actual analysis"""
        # Implementation depends on specific analysis requirements
        return {
            'score': 0.85,
            'confidence': 0.92,
            'details': 'Analysis completed successfully'
        }

    def _compare_with_history(self, current_result: Dict, historical_data: List[Dict]) -> Dict:
        """Compare current result with historical data"""
        if not historical_data:
            return {'comparison': 'no_history'}

        # Simple comparison logic
        historical_scores = [json.loads(row['analysis_data']).get('score', 0) for row in historical_data]
        avg_historical_score = sum(historical_scores) / len(historical_scores)

        current_score = current_result.get('score', 0)

        return {
            'current_score': current_score,
            'historical_average': avg_historical_score,
            'performance': 'above_average' if current_score > avg_historical_score else 'below_average',
            'improvement': current_score - avg_historical_score
        }
```

## Service Integration

### Custom Services

```python
# services/custom_services.py
import aiohttp
from typing import Dict, Any

class HTTPService:
    """HTTP client service for API calls"""

    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self._session = None

    async def initialize(self):
        """Initialize HTTP session"""
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

    async def cleanup(self):
        """Cleanup HTTP session"""
        if self._session:
            await self._session.close()

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make GET request"""
        if not self._session:
                    full_url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}" if self.base_url else url
        return await self._session.get(full_url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make POST request"""
        if not self._session:
                    full_url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}" if self.base_url else url
        return await self._session.post(full_url, **kwargs)

class CacheService:
    """Simple in-memory cache service"""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._cache = {}
        self._timestamps = {}

    def get(self, key: str) -> Any:
        """Get value from cache"""
        import time

        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl:
                return self._cache[key]
            else:
                # Expired
                del self._cache[key]
                del self._timestamps[key]

        return None

    def set(self, key: str, value: Any):
        """Set value in cache"""
        import time

        self._cache[key] = value
        self._timestamps[key] = time.time()

    def clear(self):
        """Clear entire cache"""
        self._cache.clear()
        self._timestamps.clear()

class NotificationService:
    """Service for sending notifications"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    async def send_notification(self, message: str, level: str = 'info'):
        """Send notification"""
        if not self.webhook_url:
            print(f"NOTIFICATION [{level.upper()}]: {message}")
            return

        # Implementation for webhook notifications
        import aiohttp

        payload = {
            'message': message,
            'level': level,
            'timestamp': datetime.now().isoformat()
        }

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(self.webhook_url, json=payload)
            except Exception as e:
                print(f"Failed to send notification: {e}")
```

### Service Configuration

```python
# main.py - Service setup
async def setup_services() -> ServiceRegistry:
    """Setup and configure all services"""
    services = ServiceRegistry()

    # Database service
    db_manager = await DatabaseConfig.initialize_database()
    services.register('database', db_manager)

    # HTTP service
    http_service = HTTPService(base_url="https://api.example.com", timeout=60)
        services.register('http', http_service)

    # Cache service
    cache_service = CacheService(ttl=1800)  # 30 minutes
    services.register('cache', cache_service)

    # Notification service
    notification_service = NotificationService(
        webhook_url=os.getenv('NOTIFICATION_WEBHOOK_URL')
    )
    services.register('notifications', notification_service)

    return services
```

### Using Services in Steps

```python
class EnhancedAPIStep(Step):
    """Step demonstrating multiple service usage"""

    async def run(self, data: Dict[str, Any]) -> Any:
        # Get services
        http = self.get_http()
        cache_service = self.services.get('cache') if self.services else None
        notification_service = self.services.get('notifications') if self.services else None

        # Check cache first
        cache_key = f"api_data_{data.get('id', 'unknown')}"
        cached_result = cache_service.get(cache_key) if cache_service else None

        if cached_result:
            if notification_service:
                await notification_service.send_notification(f"Using cached data for {cache_key}")

            return {
                'result': cached_result,
                'source': 'cache',
                'status': 'success'
            }

        # Make API call
        try:
            api_endpoint = self.config.get('endpoint', '/data')
            response = await http.get(api_endpoint, params=data)

            if response.status == 200:
                result = await response.json()

                # Cache the result
                if cache_service:
                    cache_service.set(cache_key, result)

                # Send success notification
                if notification_service:
                    await notification_service.send_notification(
                        f"API call successful for {api_endpoint}",
                        level='info'
                    )

                return {
                    'result': result,
                    'source': 'api',
                    'status': 'success'
                }
            else:
                error_msg = f"API call failed with status {response.status}"

                if notification_service:
                    await notification_service.send_notification(error_msg, level='error')

                return {
                    'error': error_msg,
                    'status': 'failed'
                }

        except Exception as e:
            error_msg = f"API call exception: {str(e)}"

            if notification_service:
                await notification_service.send_notification(error_msg, level='error')

            return {
                'error': error_msg,
                'status': 'failed'
            }
```

## Testing Your Code

### Test Structure

```python
# tests/test_my_steps.py
import pytest
import tempfile
from unittest.mock import Mock, AsyncMock

from ia_modules.pipeline.services import ServiceRegistry
from steps.my_custom_steps import DataTransformStep, DatabaseWriterStep

@pytest.fixture
def mock_service_registry():
    """Provide mock service registry"""
    services = ServiceRegistry()

    # Mock database
    mock_db = Mock()
    mock_db.execute = Mock()
    services.register('database', mock_db)

    # Mock HTTP client
    mock_http = AsyncMock()
    services.register('http', mock_http)

    return services

@pytest.mark.asyncio
async def test_data_transform_step():
    """Test data transformation step"""
    step = DataTransformStep("transform_test", {
        'transform_type': 'uppercase',
        'field_name': 'text'
    })

    input_data = {'text': 'hello world'}
    result = await step.work(input_data)

    assert result['transformed_text'] == 'HELLO WORLD'
    assert result['original_text'] == 'hello world'
    assert result['status'] == 'success'

@pytest.mark.asyncio
async def test_database_writer_step(mock_service_registry):
    """Test database writer step"""
    step = DatabaseWriterStep("db_writer", {'table_name': 'test_table'})
    step.set_services(mock_service_registry)

    input_data = {'transformed_text': 'test content'}
    result = await step.work(input_data)

    # Verify database was called
    mock_db = mock_service_registry.get('database')
    mock_db.execute.assert_called_once()

    assert result['status'] == 'success'
    assert result['table'] == 'test_table'
```

### Pipeline Integration Tests

```python
# tests/test_pipeline_integration.py
import pytest
import json
import tempfile
from pathlib import Path

from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.core import ExecutionContext

@pytest.mark.asyncio
async def test_full_pipeline_execution():
    """Test complete pipeline execution"""

    # Create test pipeline configuration
    pipeline_config = {
        "name": "Test Pipeline",
        "version": "1.0",
        "steps": [
            {
                "id": "transform_step",
                "step_class": "DataTransformStep",
                "module": "steps.my_custom_steps",
                "config": {
                    "transform_type": "uppercase",
                    "field_name": "message"
                }
            }
        ],
        "flow": {
            "start_at": "transform_step",
            "paths": []
        }
    }

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(pipeline_config, tmp)
        pipeline_file = tmp.name

    try:
        # Create execution context
        execution_context = ExecutionContext(
            execution_id='test-123',
            pipeline_id='test-pipeline',
            user_id='test-user'
        )

        # Execute pipeline
        result = await run_pipeline_from_json(
            pipeline_file=pipeline_file,
            input_data={'message': 'test message'},
            execution_context=execution_context
        )

        # Verify results
        assert 'transform_step' in result
        assert result['transform_step']['transformed_text'] == 'TEST MESSAGE'

    finally:
        # Cleanup
        Path(pipeline_file).unlink()
```

## Contributing Guidelines

### Development Workflow

1. **Fork and Clone**
   ```bash
   git clone <your-fork-url>
   cd ia_modules
   git remote add upstream <original-repo-url>
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Development Setup**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -e .
   pip install -e ".[dev]"
   ```

4. **Make Changes**
   - Write code following the established patterns
   - Add comprehensive tests
   - Update documentation

5. **Quality Checks**
   ```bash
   # Format code
   black .

   # Lint code
   flake8 .

   # Run tests
   pytest tests/ -v --cov=ia_modules

   # Type checking (if using mypy)
   mypy ia_modules/
   ```

6. **Commit and Push**
   ```bash
   git add .
   git commit -m "Add feature: description of changes"
   git push origin feature/your-feature-name
   ```

7. **Create Pull Request**
   - Provide clear description of changes
   - Include tests and documentation updates
   - Reference any related issues

### Code Standards

#### Python Style
- Follow PEP 8 style guide
- Use Black for code formatting
- Maximum line length: 88 characters
- Use type hints where appropriate

#### Documentation
- Document all public functions and classes
- Use Google-style docstrings
- Include usage examples in docstrings
- Update README.md for significant changes

#### Testing
- Write tests for all new functionality
- Maintain minimum 80% code coverage
- Use descriptive test names
- Include both positive and negative test cases

### Example Contribution

```python
# ia_modules/pipeline/enhanced_features.py
from typing import Dict, Any, List
from .core import Step

class ParallelProcessingStep(Step):
    """
    Step that processes data in parallel batches.

    This step divides input data into chunks and processes them concurrently
    for improved performance on large datasets.

    Configuration:
        batch_size (int): Number of items per batch (default: 100)
        max_workers (int): Maximum concurrent workers (default: 4)

    Example:
        ```python
        step = ParallelProcessingStep("parallel_proc", {
            "batch_size": 50,
            "max_workers": 2
        })
        ```
    """

    async def run(self, data: Dict[str, Any]) -> Any:
        """
        Process data in parallel batches.

        Args:
            data: Input data containing 'items' list to process

        Returns:
            Dict containing processed results and metadata

        Raises:
            ValueError: If 'items' not found in input data
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        items = data.get('items')
        if not items:
            raise ValueError("Input data must contain 'items' list")

        batch_size = self.config.get('batch_size', 100)
        max_workers = self.config.get('max_workers', 4)

        # Create batches
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor, self._process_batch, batch)
                for batch in batches
            ]

            batch_results = await asyncio.gather(*tasks)

        # Combine results
        all_results = []
        for batch_result in batch_results:
            all_results.extend(batch_result)

        return {
            'processed_items': all_results,
            'total_items': len(items),
            'batch_count': len(batches),
            'batch_size': batch_size,
            'status': 'success'
        }

    def _process_batch(self, batch: List[Any]) -> List[Dict]:
        """Process a single batch of items."""
        return [{'item': item, 'processed': True} for item in batch]
```

## Deployment Strategies

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install ia_modules in development mode
RUN pip install -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Command to run application
CMD ["python", "main.py"]
```

### Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/appdb
      - ENVIRONMENT=production
    depends_on:
      - db
    volumes:
      - ./pipelines:/app/pipelines
      - ./migrations:/app/migrations

  db:
    image: postgres:13
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=appdb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### Production Configuration

```python
# config/production.py
import os
from nexusql import DatabaseManager

class ProductionConfig:
    # Database configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    DATABASE_POOL_SIZE = int(os.getenv('DATABASE_POOL_SIZE', '10'))
    DATABASE_TIMEOUT = int(os.getenv('DATABASE_TIMEOUT', '30'))

    # Pipeline configuration
    PIPELINE_DIR = os.getenv('PIPELINE_DIR', './pipelines')
    MIGRATION_DIR = os.getenv('MIGRATION_DIR', './migrations')

    # Logging configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Performance settings
    MAX_CONCURRENT_PIPELINES = int(os.getenv('MAX_CONCURRENT_PIPELINES', '5'))
    STEP_TIMEOUT = int(os.getenv('STEP_TIMEOUT', '300'))  # 5 minutes

    @classmethod
    def validate(cls):
        """Validate production configuration"""
        required_vars = ['DATABASE_URL']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
```

## Troubleshooting

### Common Issues

#### Import Errors
```python
# Error: ModuleNotFoundError: No module named 'my_steps'
# Solution: Ensure proper PYTHONPATH or use absolute imports

# Wrong:
from my_steps import CustomStep

# Right:
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from my_steps import CustomStep
```

#### Database Connection Issues
```python
# Error: Database connection failed
# Solution: Check database URL and permissions

async def diagnose_database():
    """Diagnose database connection issues"""
    try:
        db = DatabaseManager(database_url)
        success = db.connect()
        if not success:
            print("❌ Database connection failed")
            print(f"URL: {database_url}")
            print("Check: URL format, file permissions, network connectivity")
        else:
            print("✅ Database connection successful")

            # Test query
            result = db.fetch_one("SELECT 1 as test")
            if result:
                print("✅ Database queries working")
            else:
                print("❌ Database queries failing")

    except Exception as e:
        print(f"❌ Database error: {e}")
```

#### Template Resolution Issues
```python
# Error: Template parameter not found
# Solution: Check template syntax and context

def debug_template_resolution():
    """Debug template parameter resolution"""
    from ia_modules.pipeline.core import TemplateParameterResolver

    context = {
        'parameters': {'param1': 'value1'},
        'steps': {'step1': {'result': {'data': 'test'}}},
        'pipeline_input': {'input_field': 'input_value'}
    }

    config = {'field': '{steps.step1.result.missing_field}'}

    # Extract parameters to see what's available
    params = TemplateParameterResolver.extract_template_parameters(config)
    print(f"Template parameters found: {params}")

    # Try resolution
    resolved = TemplateParameterResolver.resolve_parameters(config, context)
    print(f"Resolved config: {resolved}")
```

### Logging and Debugging

```python
# Enhanced logging setup
import logging

def setup_logging(level='INFO'):
    """Setup comprehensive logging"""

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler('ia_modules.log')
    file_handler.setFormatter(formatter)

    # Configure loggers
    loggers = ['ia_modules', 'ia_modules.pipeline', 'ia_modules.database']

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, level.upper()))
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logging.getLogger('ia_modules')

# Usage in main application
logger = setup_logging('DEBUG')
logger.info("Application starting...")
```

## Performance Optimization

### Pipeline Performance

```python
from ia_modules.pipeline.runner import run_pipeline_from_json
from ia_modules.pipeline.core import ExecutionContext

class OptimizedPipeline:
    """Pipeline with performance optimizations"""

    def __init__(self):
        self.metrics = {
            'step_times': {},
            'memory_usage': {},
            'cache_hits': 0,
            'cache_misses': 0
        }

    async def run_with_metrics(self, pipeline_file: str, input_data: dict, execution_context: ExecutionContext):
        """Run pipeline with performance metrics"""
        import time
        import psutil

        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss

        try:
            result = await run_pipeline_from_json(pipeline_file, input_data, execution_context)

            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss

            self.metrics.update({
                'total_time': end_time - start_time,
                'memory_delta': end_memory - start_memory,
                'success': True
            })

            return result

        except Exception as e:
            self.metrics['error'] = str(e)
            self.metrics['success'] = False
            raise

    def get_performance_report(self) -> dict:
        """Get performance metrics report"""
        return {
            'execution_metrics': self.metrics,
            'optimization_suggestions': self._get_optimization_suggestions()
        }

    def _get_optimization_suggestions(self) -> list:
        """Generate optimization suggestions based on metrics"""
        suggestions = []

        if self.metrics.get('total_time', 0) > 60:
            suggestions.append("Consider parallel processing for long-running pipelines")

        if self.metrics.get('memory_delta', 0) > 100 * 1024 * 1024:  # 100MB
            suggestions.append("High memory usage - consider batch processing")

        cache_ratio = self.metrics.get('cache_hits', 0) / max(
            self.metrics.get('cache_hits', 0) + self.metrics.get('cache_misses', 0), 1
        )
        if cache_ratio < 0.3:
            suggestions.append("Low cache hit ratio - review caching strategy")

        return suggestions
```

This developer guide provides comprehensive coverage of building, testing, and deploying applications with the IA Modules framework. Use it as a reference for development best practices and troubleshooting common issues.