"""
Human-in-the-Loop (HITL) API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

from ia_modules.pipeline.hitl_manager import HITLManager, HITLInteraction

router = APIRouter()


def get_db_manager(request: Request):
    """Dependency to get database manager"""
    return request.app.state.services.db_manager


class HITLResponseRequest(BaseModel):
    """Request model for responding to HITL interaction"""
    human_input: Dict[str, Any]
    responded_by: Optional[str] = None


class HITLInteractionResponse(BaseModel):
    """Response model for HITL interaction"""
    interaction_id: str
    execution_id: str
    pipeline_id: str
    step_id: str
    step_name: str
    status: str
    ui_schema: Dict[str, Any]
    prompt: str
    context_data: Dict[str, Any]
    human_input: Optional[Dict[str, Any]]
    responded_by: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    completed_at: Optional[datetime]


@router.get("/pending", response_model=List[HITLInteractionResponse])
async def get_pending_interactions(
    execution_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db_manager=Depends(get_db_manager)
):
    """
    Get all pending HITL interactions.

    Can be filtered by execution_id, pipeline_id, or user_id (assigned user).
    """
    hitl_manager = HITLManager(db_manager)

    interactions = await hitl_manager.get_pending_interactions(
        execution_id=execution_id,
        pipeline_id=pipeline_id,
        user_id=user_id
    )

    return [_interaction_to_response(i) for i in interactions]


@router.get("/{interaction_id}", response_model=HITLInteractionResponse)
async def get_interaction(
    interaction_id: str,
    db_manager=Depends(get_db_manager)
):
    """Get a specific HITL interaction by ID"""
    hitl_manager = HITLManager(db_manager)

    interaction = await hitl_manager.get_interaction(interaction_id)

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    return _interaction_to_response(interaction)


@router.post("/{interaction_id}/respond")
async def respond_to_interaction(
    interaction_id: str,
    request: HITLResponseRequest,
    req: Request,
    db_manager=Depends(get_db_manager)
):
    """
    Submit human response to a HITL interaction.

    This will mark the interaction as completed and resume pipeline execution.
    """
    hitl_manager = HITLManager(db_manager)

    # Get interaction details before responding
    interaction = await hitl_manager.get_interaction(interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    execution_id = interaction.execution_id

    # Record the human response
    success = await hitl_manager.respond_to_interaction(
        interaction_id=interaction_id,
        human_input=request.human_input,
        responded_by=request.responded_by
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Interaction not found, already completed, or expired"
        )

    # Resume the pipeline execution with the human input
    try:
        pipeline_service = req.app.state.services.pipeline_service
        await pipeline_service.resume_from_hitl(
            execution_id=execution_id,
            interaction_id=interaction_id,
            human_input=request.human_input
        )
    except Exception as e:
        # Log error but don't fail the response - interaction is already recorded
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to resume pipeline after HITL response: {e}")

    return {
        "status": "success",
        "message": "Response recorded and pipeline resumed",
        "interaction_id": interaction_id,
        "execution_id": execution_id
    }


@router.post("/{interaction_id}/cancel")
async def cancel_interaction(
    interaction_id: str,
    db_manager=Depends(get_db_manager)
):
    """Cancel a pending HITL interaction"""
    hitl_manager = HITLManager(db_manager)

    success = await hitl_manager.cancel_interaction(interaction_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Interaction not found or already completed"
        )

    return {
        "status": "success",
        "message": "Interaction cancelled",
        "interaction_id": interaction_id
    }


@router.post("/cleanup-expired")
async def cleanup_expired(db_manager=Depends(get_db_manager)):
    """Cleanup expired HITL interactions (admin endpoint)"""
    hitl_manager = HITLManager(db_manager)

    count = await hitl_manager.cleanup_expired_interactions()

    return {
        "status": "success",
        "expired_count": count
    }


def _interaction_to_response(interaction: HITLInteraction) -> HITLInteractionResponse:
    """Convert HITLInteraction to response model"""
    return HITLInteractionResponse(
        interaction_id=interaction.interaction_id,
        execution_id=interaction.execution_id,
        pipeline_id=interaction.pipeline_id,
        step_id=interaction.step_id,
        step_name=interaction.step_name,
        status=interaction.status,
        ui_schema=interaction.ui_schema,
        prompt=interaction.prompt,
        context_data=interaction.context_data,
        human_input=interaction.human_input,
        responded_by=interaction.responded_by,
        created_at=interaction.created_at,
        expires_at=interaction.expires_at,
        completed_at=interaction.completed_at
    )
