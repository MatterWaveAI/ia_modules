"""Checkpoint service for managing pipeline execution checkpoints"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CheckpointService:
    """Service for checkpoint management using ia_modules"""

    def __init__(self, checkpointer=None, pipeline_service=None):
        """
        Initialize checkpoint service
        
        Args:
            checkpointer: Checkpointer instance from ia_modules (Redis or SQL)
            pipeline_service: PipelineService for resuming execution
        """
        self.checkpointer = checkpointer
        self.pipeline_service = pipeline_service
        logger.info(f"Checkpoint service initialized with {type(checkpointer).__name__ if checkpointer else 'no checkpointer'}")

    async def list_checkpoints(self, job_id: str) -> List[Dict[str, Any]]:
        """
        List all checkpoints for a specific execution
        
        Args:
            job_id: Execution job ID (used as pipeline_id in checkpointer)
            
        Returns:
            List of checkpoint dictionaries
        """
        if not self.checkpointer:
            logger.warning("No checkpointer available for checkpoint operations")
            return []

        try:
            # Get checkpoints from checkpointer
            checkpoints = await self._get_checkpoints_from_storage(job_id)
            
            # Format for API response
            formatted = []
            for cp in checkpoints:
                try:
                    formatted.append({
                        "id": cp.get("checkpoint_id") or cp.get("id"),
                        "job_id": job_id,
                        "step_name": cp.get("step_name"),
                        "created_at": cp.get("created_at") or cp.get("timestamp"),
                        "state_size": len(str(cp.get("state", {}))) if cp.get("state") else 0,
                        "metadata": cp.get("metadata", {})
                    })
                except Exception as e:
                    logger.warning(f"Error formatting checkpoint: {e}")
                    continue
            
            logger.info(f"Retrieved {len(formatted)} checkpoints for job {job_id}")
            return formatted

        except Exception as e:
            logger.error(f"Error listing checkpoints for job {job_id}: {e}", exc_info=True)
            return []

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific checkpoint by ID
        
        Args:
            checkpoint_id: Checkpoint ID
            
        Returns:
            Checkpoint dictionary or None
        """
        if not self.checkpointer:
            return None

        try:
            checkpoint = await self._load_checkpoint_from_storage(checkpoint_id)
            
            if not checkpoint:
                return None

            return {
                "id": checkpoint_id,
                "job_id": checkpoint.get("job_id"),
                "step_name": checkpoint.get("step_name"),
                "state": checkpoint.get("state", {}),
                "created_at": checkpoint.get("created_at"),
                "metadata": checkpoint.get("metadata", {})
            }

        except Exception as e:
            logger.error(f"Error getting checkpoint {checkpoint_id}: {e}", exc_info=True)
            return None

    async def get_checkpoint_state(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the state data from a checkpoint
        
        Args:
            checkpoint_id: Checkpoint ID
            
        Returns:
            State dictionary or None
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        return checkpoint.get("state") if checkpoint else None

    async def resume_from_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Resume pipeline execution from a checkpoint
        
        Args:
            checkpoint_id: Checkpoint ID to resume from
            
        Returns:
            New execution details
        """
        if not self.checkpointer or not self.pipeline_service:
            raise ValueError("Checkpoint or pipeline service not available")

        try:
            # Load checkpoint
            checkpoint = await self.get_checkpoint(checkpoint_id)
            
            if not checkpoint:
                raise ValueError(f"Checkpoint {checkpoint_id} not found")

            job_id = checkpoint["job_id"]
            state = checkpoint["state"]
            
            logger.info(f"Resuming execution {job_id} from checkpoint {checkpoint_id}")
            
            # Get original execution
            execution = await self.pipeline_service.get_execution(job_id)
            
            if not execution:
                raise ValueError(f"Original execution {job_id} not found")

            # Create new execution with checkpoint state
            # This is a simplified version - actual implementation depends on how
            # the pipeline runner handles checkpoint resumption
            new_job_id = await self.pipeline_service.execute_pipeline(
                pipeline_id=execution["pipeline_id"],
                input_data=state.get("input_data", execution.get("input_data", {})),
                checkpoint_enabled=True
            )

            return {
                "original_job_id": job_id,
                "new_job_id": new_job_id,
                "resumed_from_checkpoint": checkpoint_id,
                "resumed_at_step": checkpoint["step_name"]
            }

        except Exception as e:
            logger.error(f"Error resuming from checkpoint: {e}", exc_info=True)
            raise

    async def _get_checkpoints_from_storage(self, job_id: str) -> List[Dict]:
        """Get checkpoints from storage backend"""
        if hasattr(self.checkpointer, 'list_checkpoints'):
            checkpoints = await self.checkpointer.list_checkpoints(
                pipeline_id=job_id,
                thread_id="default"
            )
            return [self._checkpoint_to_dict(cp) for cp in checkpoints]
        
        return []

    async def _load_checkpoint_from_storage(self, checkpoint_id: str) -> Optional[Dict]:
        """Load checkpoint from storage backend"""
        if hasattr(self.checkpointer, 'load_checkpoint'):
            cp = await self.checkpointer.load_checkpoint(checkpoint_id)
            if cp:
                return self._checkpoint_to_dict(cp)
        
        return None

    def _checkpoint_to_dict(self, checkpoint) -> Dict:
        """Convert checkpoint object to dictionary"""
        if isinstance(checkpoint, dict):
            return checkpoint

        # Checkpoint objects have to_dict() method
        if hasattr(checkpoint, 'to_dict'):
            cp_dict = checkpoint.to_dict()
            # Normalize field names for API
            return {
                "id": cp_dict.get("checkpoint_id"),
                "checkpoint_id": cp_dict.get("checkpoint_id"),
                "job_id": cp_dict.get("pipeline_id"),  # Map pipeline_id to job_id
                "pipeline_id": cp_dict.get("pipeline_id"),
                "step_name": cp_dict.get("step_name"),
                "step_id": cp_dict.get("step_id"),
                "step_index": cp_dict.get("step_index"),
                "state": cp_dict.get("state", {}),
                "created_at": cp_dict.get("timestamp"),  # Map timestamp to created_at
                "timestamp": cp_dict.get("timestamp"),
                "metadata": cp_dict.get("metadata", {}),
                "status": cp_dict.get("status"),
                "thread_id": cp_dict.get("thread_id")
            }

        # Fallback to attribute access
        return {
            "id": getattr(checkpoint, "checkpoint_id", None),
            "job_id": getattr(checkpoint, "pipeline_id", None),
            "step_name": getattr(checkpoint, "step_name", None),
            "state": getattr(checkpoint, "state", {}),
            "created_at": getattr(checkpoint, "timestamp", None),
            "metadata": getattr(checkpoint, "metadata", {})
        }
