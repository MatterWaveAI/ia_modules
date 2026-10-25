"""
API endpoints for managing pipeline step modules (Python code)

Provides CRUD operations for viewing and editing step code stored in database.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import logging

from nexusql import DatabaseInterface

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipelines", tags=["step_modules"])


# Dependency to get database from app state
async def get_db(request: Request) -> DatabaseInterface:
    """Get database instance from app state"""
    if hasattr(request.app.state, 'services') and request.app.state.services.db_manager:
        return request.app.state.services.db_manager
    raise HTTPException(status_code=503, detail="Database not available")


class StepModuleResponse(BaseModel):
    """Response model for step module"""
    id: str
    pipeline_id: str
    step_id: str
    module_path: str
    class_name: str
    source_code: str
    file_path: Optional[str]
    content_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StepModuleUpdateRequest(BaseModel):
    """Request model for updating step module"""
    source_code: str


class StepModuleListResponse(BaseModel):
    """Response model for listing step modules"""
    id: str
    step_id: str
    module_path: str
    class_name: str
    file_path: Optional[str]
    content_hash: str
    created_at: datetime
    updated_at: datetime


@router.get("/{pipeline_id}/steps/{step_id}/code", response_model=StepModuleResponse)
async def get_step_code(
    pipeline_id: str,
    step_id: str,
    db: DatabaseInterface = Depends(get_db)
):
    """Get step module source code from database

    Args:
        pipeline_id: ID of the pipeline
        step_id: ID of the step within the pipeline
        db: Database interface

    Returns:
        Step module with source code

    Raises:
        HTTPException: 404 if step module not found
    """
    query = """
    SELECT id, pipeline_id, step_id, module_path, class_name, source_code,
           file_path, content_hash, is_active, created_at, updated_at
    FROM pipeline_step_modules
    WHERE pipeline_id = :pipeline_id
      AND step_id = :step_id
      AND is_active = :is_active
    """

    result = db.fetch_one(query, {
        'pipeline_id': pipeline_id,
        'step_id': step_id,
        'is_active': True
    })

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Step module not found for pipeline {pipeline_id}, step {step_id}"
        )

    return StepModuleResponse(**result)


@router.put("/{pipeline_id}/steps/{step_id}/code")
async def update_step_code(
    pipeline_id: str,
    step_id: str,
    update_data: StepModuleUpdateRequest,
    db: DatabaseInterface = Depends(get_db)
):
    """Update step module source code in database

    Args:
        pipeline_id: ID of the pipeline
        step_id: ID of the step within the pipeline
        update_data: New source code
        db: Database interface

    Returns:
        Success response with new content hash

    Raises:
        HTTPException: 404 if step module not found, 500 if update fails
    """
    source_code = update_data.source_code

    # Validate that step module exists
    check_query = """
    SELECT id FROM pipeline_step_modules
    WHERE pipeline_id = :pipeline_id
      AND step_id = :step_id
      AND is_active = :is_active
    """

    check_result = db.fetch_one(check_query, {
        'pipeline_id': pipeline_id,
        'step_id': step_id,
        'is_active': True
    })

    if not check_result:
        raise HTTPException(
            status_code=404,
            detail=f"Step module not found for pipeline {pipeline_id}, step {step_id}"
        )

    # Calculate new hash
    content_hash = hashlib.md5(source_code.encode()).hexdigest()

    # Update database
    update_query = """
    UPDATE pipeline_step_modules
    SET source_code = :source_code,
        content_hash = :content_hash,
        updated_at = CURRENT_TIMESTAMP
    WHERE pipeline_id = :pipeline_id
      AND step_id = :step_id
    """

    result = await db.execute_async(update_query, {
        'source_code': source_code,
        'content_hash': content_hash,
        'pipeline_id': pipeline_id,
        'step_id': step_id
    })

    if not result.success:
        logger.error(f"Failed to update step code: {result}")
        raise HTTPException(status_code=500, detail="Failed to update step code")

    # Clear step class cache to force reload
    try:
        from ia_modules.pipeline.db_step_loader import _step_class_cache
        cache_keys_to_remove = [k for k in _step_class_cache.keys() if step_id in k]
        for key in cache_keys_to_remove:
            del _step_class_cache[key]
        logger.info(f"Cleared {len(cache_keys_to_remove)} cached step classes")
    except Exception as e:
        logger.warning(f"Failed to clear step cache: {e}")

    return {
        "success": True,
        "content_hash": content_hash,
        "message": "Step code updated successfully"
    }


@router.get("/{pipeline_id}/steps", response_model=List[StepModuleListResponse])
async def list_pipeline_steps(
    pipeline_id: str,
    db: DatabaseInterface = Depends(get_db)
):
    """List all step modules for a pipeline

    Args:
        pipeline_id: ID of the pipeline
        db: Database interface

    Returns:
        List of step modules (without full source code for performance)
    """
    query = """
    SELECT id, step_id, module_path, class_name,
           file_path, content_hash, created_at, updated_at
    FROM pipeline_step_modules
    WHERE pipeline_id = :pipeline_id AND is_active = :is_active
    ORDER BY step_id
    """

    result = db.fetch_all(query, {
        'pipeline_id': pipeline_id,
        'is_active': True
    })

    if result:
        return [StepModuleListResponse(**row) for row in result]

    return []


@router.delete("/{pipeline_id}/steps/{step_id}/code")
async def delete_step_code(
    pipeline_id: str,
    step_id: str,
    db: DatabaseInterface = Depends(get_db)
):
    """Soft delete a step module (mark as inactive)

    Args:
        pipeline_id: ID of the pipeline
        step_id: ID of the step within the pipeline
        db: Database interface

    Returns:
        Success response

    Raises:
        HTTPException: 404 if step module not found
    """
    # Check if exists
    check_query = """
    SELECT id FROM pipeline_step_modules
    WHERE pipeline_id = :pipeline_id
      AND step_id = :step_id
      AND is_active = :is_active
    """

    check_result = db.fetch_one(check_query, {
        'pipeline_id': pipeline_id,
        'step_id': step_id,
        'is_active': True
    })

    if not check_result:
        raise HTTPException(
            status_code=404,
            detail=f"Step module not found for pipeline {pipeline_id}, step {step_id}"
        )

    # Soft delete
    delete_query = """
    UPDATE pipeline_step_modules
    SET is_active = 0,
        updated_at = CURRENT_TIMESTAMP
    WHERE pipeline_id = :pipeline_id
      AND step_id = :step_id
    """

    result = await db.execute_async(delete_query, {
        'pipeline_id': pipeline_id,
        'step_id': step_id
    })

    if not result.success:
        raise HTTPException(status_code=500, detail="Failed to delete step module")

    return {"success": True, "message": "Step module deleted successfully"}


@router.post("/{pipeline_id}/steps/{step_id}/validate")
async def validate_step_code(
    pipeline_id: str,
    step_id: str,
    update_data: StepModuleUpdateRequest,
    db: DatabaseInterface = Depends(get_db)
):
    """Validate step code without saving

    Args:
        pipeline_id: ID of the pipeline
        step_id: ID of the step
        update_data: Source code to validate
        db: Database interface

    Returns:
        Validation result with any errors
    """
    from ia_modules.pipeline.db_step_loader import DatabaseStepLoader

    try:
        loader = DatabaseStepLoader(db, enable_cache=False)
        # Just validate, don't load from DB
        loader._validate_source_code(update_data.source_code)

        return {
            "valid": True,
            "message": "Code validation passed"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "message": "Code validation failed"
        }
