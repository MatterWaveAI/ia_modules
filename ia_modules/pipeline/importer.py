"""
Shared Pipeline Importer

Moved from the app-level implementation so that multiple consuming
applications can reuse the same importer logic from `ia_modules`.

The constructor accepts an optional `pipelines_dir`. If not provided
the importer will look for a `pipelines/` directory in the current
working directory. Consuming apps should pass an explicit path if
they keep pipelines adjacent to their application package.
"""

import json
import logging
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from nexusql import DatabaseInterface

logger = logging.getLogger(__name__)


class PipelineImportService:
    """Service for importing pipeline definitions from JSON files"""

    def __init__(self, db_provider: DatabaseInterface, pipelines_dir: Optional[str] = None):
        self.db_provider = db_provider
        if pipelines_dir is None:
            # Default to a pipelines folder in the current working directory
            self.pipelines_dir = Path.cwd() / "pipelines"
        else:
            self.pipelines_dir = Path(pipelines_dir)

    async def import_all_pipelines(self, clear_existing: bool = False) -> Dict[str, Any]:
        """Import all pipeline JSON files from the pipelines directory

        Args:
            clear_existing: If True, clear all existing imported pipelines before import

        Returns:
            Dictionary with import statistics
        """
        logger.info(f"Starting pipeline import from: {self.pipelines_dir}")

        # Clear existing imported pipelines if requested
        if clear_existing:
            deleted_count = await self.clear_all_imported_pipelines()
            logger.info(f"Cleared {deleted_count} existing imported pipelines")

        if not self.pipelines_dir.exists():
            logger.warning(f"Pipelines directory does not exist: {self.pipelines_dir}")
            return {"imported": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Scan for pipeline.json files recursively
        json_files = list(self.pipelines_dir.glob("**/pipeline.json"))
        logger.info(f"Found {len(json_files)} pipeline.json files to process")
        for jf in json_files:
            logger.info(f"  FILE: {jf}")

        results = {
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }

        for json_file in json_files:
            try:
                result = await self._import_pipeline_file(json_file)
                results[result["action"]] += 1
                results["details"].append({
                    "file": json_file.name,
                    "action": result["action"],
                    "pipeline_id": result.get("pipeline_id"),
                    "slug": result.get("slug")
                })
            except Exception as e:
                logger.error(f"Failed to import {json_file.name}: {e}")
                results["errors"] += 1
                results["details"].append({
                    "file": json_file.name,
                    "action": "error",
                    "error": str(e)
                })

        logger.info(f"Pipeline import completed: {results['imported']} imported, {results['updated']} updated, {results['skipped']} skipped, {results['errors']} errors")
        return results

    async def _import_pipeline_file(self, file_path: Path) -> Dict[str, Any]:
        """Import a single pipeline JSON file and its step modules"""
        logger.debug(f"Processing pipeline file: {file_path.name}")

        # Load and validate JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            pipeline_data = json.load(f)

        # Validate required fields
        if not isinstance(pipeline_data, dict):
            raise ValueError("Pipeline file must contain a JSON object")

        name = pipeline_data.get('name')
        if not name:
            raise ValueError("Pipeline must have a 'name' field")

        # Generate slug from pipeline name and file path
        slug = self._generate_slug(name, str(file_path))
        logger.info(f"IMPORTING: file={file_path} slug={slug}")

        # Calculate content hash for change detection
        content_hash = self._calculate_content_hash(pipeline_data)

        # Check if pipeline already exists
        existing = await self._get_existing_pipeline(slug)

        if existing:
            # Skip if unchanged
            if existing['content_hash'] == content_hash:
                return {"action": "skipped", "pipeline_id": existing['id'], "slug": slug}

            # Update if changed
            await self._update_pipeline(existing['id'], pipeline_data, content_hash, str(file_path.relative_to(self.pipelines_dir)))
            return {"action": "updated", "pipeline_id": existing['id'], "slug": slug}

        # Create new pipeline
        pipeline_id = await self._create_pipeline(slug, pipeline_data, content_hash, str(file_path.relative_to(self.pipelines_dir)))
        # Import step modules for new pipeline
        await self._import_step_modules(file_path, pipeline_id, pipeline_data)
        logger.info(f"Imported new pipeline: {slug} ({pipeline_id})")
        return {"action": "imported", "pipeline_id": pipeline_id, "slug": slug}

    def _calculate_content_hash(self, pipeline_data: Dict[str, Any]) -> str:
        """Calculate hash of pipeline content for change detection"""
        content_str = json.dumps(pipeline_data, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()

    def _generate_slug(self, name: str, file_path: str) -> str:
        """Generate a URL-safe slug from pipeline name and file path

        Creates a slug in format: sanitized-name-{hash}
        where hash is first 8 chars of md5(file_path) to prevent collisions.

        Args:
            name: Pipeline name
            file_path: File path (used to prevent collisions)

        Returns:
            URL-safe slug (lowercase, hyphens, alphanumeric)

        Examples:
            >>> _generate_slug("Test Pipeline", "path/to/pipeline.json")
            'test-pipeline-a1b2c3d4'
            >>> _generate_slug("My_Test@Pipeline!", "other/path.json")
            'my-test-pipeline-e5f6g7h8'
        """
        # Convert to lowercase
        slug = name.lower()

        # Replace spaces and underscores with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')

        # Remove special characters (keep only alphanumeric and hyphens)
        slug = re.sub(r'[^a-z0-9-]', '', slug)

        # Remove double hyphens
        slug = re.sub(r'-+', '-', slug)

        # Trim leading/trailing hyphens
        slug = slug.strip('-')

        # Add hash of file path to prevent collisions
        # Different paths with same name will get different slugs
        path_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        slug = f"{slug}-{path_hash}"

        return slug

    async def _get_existing_pipeline(self, slug: str) -> Optional[Dict[str, Any]]:
        """Check if pipeline already exists by slug"""
        query = """
        SELECT id, content_hash FROM pipelines
        WHERE slug = :slug
        """
        result = self.db_provider.fetch_one(query, {'slug': slug})

        if result:
            if isinstance(result, dict):
                return result
            elif hasattr(result, 'data') and result.data:
                row = result.data[0] if isinstance(result.data, list) else result.data
                return dict(row)

        return None

    async def _create_pipeline(self, slug: str, pipeline_data: Dict[str, Any], content_hash: str, file_path: str) -> str:
        """Create a new pipeline in the database"""
        import uuid
        pipeline_id = str(uuid.uuid4())

        pipeline_json = json.dumps(pipeline_data)
        name = pipeline_data.get('name', 'Unnamed Pipeline')
        description = pipeline_data.get('description', '')
        version = pipeline_data.get('version', '1.0')

        query = """
        INSERT INTO pipelines (
            id, slug, name, description, version, pipeline_json,
            file_path, content_hash, is_system
        ) VALUES (:id, :slug, :name, :description, :version, :pipeline_json, :file_path, :content_hash, :is_system)
        """

        result = await self.db_provider.execute_async(
            query,
            {
                'id': pipeline_id,
                'slug': slug,
                'name': name,
                'description': description,
                'version': version,
                'pipeline_json': pipeline_json,
                'file_path': file_path,
                'content_hash': content_hash,
                'is_system': False
            }
        )

        # Handle both list and object responses
        if isinstance(result, list):
            # List response is considered success
            pass
        elif not hasattr(result, 'success') or not result.success:
            raise Exception(f"Failed to create pipeline: {result}")

        return pipeline_id

    async def _update_pipeline(self, pipeline_id: str, pipeline_data: Dict[str, Any], content_hash: str, file_path: str):
        """Update an existing pipeline"""
        pipeline_json = json.dumps(pipeline_data)
        name = pipeline_data.get('name', 'Unnamed Pipeline')
        description = pipeline_data.get('description', '')
        version = pipeline_data.get('version', '1.0')

        query = """
        UPDATE pipelines
        SET name = :name, description = :description, version = :version, pipeline_json = :pipeline_json,
            file_path = :file_path, content_hash = :content_hash, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        """

        result = await self.db_provider.execute_async(
            query,
            {
                'name': name,
                'description': description,
                'version': version,
                'pipeline_json': pipeline_json,
                'file_path': file_path,
                'content_hash': content_hash,
                'id': pipeline_id
            }
        )

        # Handle both list and object responses
        if isinstance(result, list):
            # List response is considered success
            pass
        elif not hasattr(result, 'success') or not result.success:
            raise Exception(f"Failed to update pipeline: {result}")

    async def get_pipeline_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get pipeline by slug"""
        query = """
        SELECT id, slug, name, description, version, pipeline_json,
               file_path, is_active, created_at, updated_at
        FROM pipelines
        WHERE slug = :slug AND is_active = TRUE
        """

        row = self.db_provider.fetch_one(query, {'slug': slug})
        if not row:
            return None
        pipeline_data = dict(row)
        pipeline_data['pipeline_config'] = json.loads(pipeline_data['pipeline_json'])
        return pipeline_data

    async def list_imported_pipelines(self) -> List[Dict[str, Any]]:
        """List all imported pipelines"""
        query = """
        SELECT id, slug, name, description, version, file_path,
               created_at, updated_at
        FROM pipelines
        WHERE is_system = :is_system AND is_active = :is_active
        ORDER BY name
        """

        rows = await self.db_provider.execute_async(query, {'is_system': False, 'is_active': True})
        return [dict(row) for row in rows or []]

    async def clear_all_imported_pipelines(self) -> int:
        """Clear all imported (non-system) pipelines

        Returns:
            Number of pipelines deleted
        """
        query = """
        DELETE FROM pipelines
        WHERE is_system = 0
        """

        result = await self.db_provider.execute_async(query)

        # Handle both list and object responses
        if isinstance(result, list):
            return 0  # List response doesn't provide rows_affected
        elif hasattr(result, 'success') and result.success:
            return getattr(result, 'rows_affected', 0)
        else:
            return 0

    async def validate_pipeline_config(self, pipeline_data: Dict[str, Any]) -> bool:
        """Validate pipeline configuration structure"""
        try:
            required_fields = ['name', 'steps']
            for field in required_fields:
                if field not in pipeline_data:
                    logger.error(f"Missing required field: {field}")
                    return False

            steps = pipeline_data.get('steps', [])
            if not isinstance(steps, list) or len(steps) == 0:
                logger.error("Pipeline must have at least one step")
                return False

            for i, step in enumerate(steps):
                required_step_fields = ['id', 'step_class', 'module']
                for field in required_step_fields:
                    if field not in step:
                        logger.error(f"Step {i} missing required field: {field}")
                        return False

            return True

        except Exception as e:
            logger.error(f"Pipeline validation error: {e}")
            return False

    async def _import_step_modules(self, pipeline_file: Path, pipeline_id: str, pipeline_data: Dict[str, Any]):
        """Import Python step modules for a pipeline

        Scans the steps/ directory adjacent to the pipeline JSON file and imports
        all Python files into the database.

        Args:
            pipeline_file: Path to pipeline.json file
            pipeline_id: ID of the pipeline in database
            pipeline_data: Parsed pipeline JSON data
        """

        pipeline_dir = pipeline_file.parent
        steps_dir = pipeline_dir / "steps"

        if not steps_dir.exists() or not steps_dir.is_dir():
            logger.debug(f"No steps directory found for pipeline: {pipeline_file}")
            return

        # Get all Python files in steps directory
        step_files = list(steps_dir.glob("*.py"))
        logger.info(f"Found {len(step_files)} step files to import for pipeline {pipeline_id}")

        imported_count = 0
        for step_file in step_files:
            # Skip __init__.py and __pycache__
            if step_file.name.startswith("__"):
                continue

            try:
                # Read source code
                source_code = step_file.read_text(encoding='utf-8')

                # Find matching step definition in pipeline JSON
                step_info = self._find_step_info_for_file(pipeline_data, step_file)

                if not step_info:
                    logger.warning(f"No matching step found in pipeline JSON for {step_file.name}, skipping")
                    continue

                # Calculate content hash
                content_hash = hashlib.md5(source_code.encode()).hexdigest()

                # Store in database
                await self._create_or_update_step_module(
                    pipeline_id=pipeline_id,
                    step_id=step_info['step_id'],
                    module_path=step_info['module_path'],
                    class_name=step_info['class_name'],
                    source_code=source_code,
                    file_path=str(step_file.relative_to(pipeline_dir)),
                    content_hash=content_hash
                )
                imported_count += 1

            except Exception as e:
                logger.error(f"Failed to import step module {step_file.name}: {e}")

        logger.info(f"Imported {imported_count} step modules for pipeline {pipeline_id}")

    def _find_step_info_for_file(self, pipeline_data: Dict[str, Any], step_file: Path) -> Optional[Dict[str, Any]]:
        """Find step information from pipeline JSON that matches a step file

        Args:
            pipeline_data: Parsed pipeline JSON
            step_file: Path to step Python file

        Returns:
            Dict with step_id, module_path, class_name or None if not found
        """
        steps = pipeline_data.get('steps', [])

        for step in steps:
            module_path = step.get('module', '')
            class_name = step.get('step_class', '')

            # Extract the filename from module path
            # e.g., "tests.pipelines.simple_pipeline.steps.step1" -> "step1"
            if module_path:
                module_parts = module_path.split('.')
                module_filename = module_parts[-1] if module_parts else ''

                # Check if this matches our file
                if module_filename == step_file.stem:
                    return {
                        'step_id': step.get('id', ''),
                        'module_path': module_path,
                        'class_name': class_name
                    }

        return None

    async def _create_or_update_step_module(
        self,
        pipeline_id: str,
        step_id: str,
        module_path: str,
        class_name: str,
        source_code: str,
        file_path: str,
        content_hash: str
    ):
        """Create or update a step module in the database

        Args:
            pipeline_id: ID of the pipeline
            step_id: ID of the step
            module_path: Python module path
            class_name: Name of the step class
            source_code: Python source code
            file_path: Original file path relative to pipeline directory
            content_hash: MD5 hash of source code
        """
        import uuid

        # Check if step module already exists
        query_check = """
        SELECT id, content_hash FROM pipeline_step_modules
        WHERE pipeline_id = :pipeline_id AND step_id = :step_id
        """

        row = self.db_provider.fetch_one(query_check, {
            'pipeline_id': pipeline_id,
            'step_id': step_id
        })

        if row:
            # Update existing
            existing_hash = row['content_hash']

            if existing_hash == content_hash:
                logger.debug(f"Step module {step_id} unchanged, skipping")
                return

            query_update = """
            UPDATE pipeline_step_modules
            SET module_path = :module_path,
                class_name = :class_name,
                source_code = :source_code,
                file_path = :file_path,
                content_hash = :content_hash,
                updated_at = CURRENT_TIMESTAMP
            WHERE pipeline_id = :pipeline_id AND step_id = :step_id
            """

            await self.db_provider.execute_async(query_update, {
                'module_path': module_path,
                'class_name': class_name,
                'source_code': source_code,
                'file_path': file_path,
                'content_hash': content_hash,
                'pipeline_id': pipeline_id,
                'step_id': step_id
            })

            logger.info(f"Updated step module: {step_id} ({class_name})")
        else:
            # Create new
            module_id = str(uuid.uuid4())

            query_insert = """
            INSERT INTO pipeline_step_modules (
                id, pipeline_id, step_id, module_path, class_name,
                source_code, file_path, content_hash, is_active
            ) VALUES (
                :id, :pipeline_id, :step_id, :module_path, :class_name,
                :source_code, :file_path, :content_hash, :is_active
            )
            """

            await self.db_provider.execute_async(query_insert, {
                'id': module_id,
                'pipeline_id': pipeline_id,
                'step_id': step_id,
                'module_path': module_path,
                'class_name': class_name,
                'source_code': source_code,
                'file_path': file_path,
                'content_hash': content_hash,
                'is_active': True
            })

            logger.info(f"Created step module: {step_id} ({class_name})")
