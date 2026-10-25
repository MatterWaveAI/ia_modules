"""Event replay service for debugging and analysis"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ReplayService:
    """Service for replaying pipeline executions using ia_modules"""

    def __init__(self, reliability_metrics=None, pipeline_service=None):
        """
        Initialize replay service
        
        Args:
            reliability_metrics: ReliabilityMetrics instance from ia_modules
            pipeline_service: PipelineService for re-execution
        """
        self.reliability_metrics = reliability_metrics
        self.pipeline_service = pipeline_service
        
        # Initialize replayer if reliability metrics available
        self.replayer = None
        if reliability_metrics and hasattr(reliability_metrics, 'storage'):
            try:
                from ia_modules.reliability.replay import Replayer, ReplayResult
                self.replayer = Replayer(reliability_metrics.storage)
                self.ReplayResult = ReplayResult
                logger.info("Event replayer initialized")
            except Exception as e:
                logger.warning(f"Could not initialize event replayer: {e}")

    async def replay_execution(
        self,
        job_id: str,
        use_cached: bool = False
    ) -> Dict[str, Any]:
        """
        Replay a pipeline execution
        
        Args:
            job_id: Original execution ID
            use_cached: Whether to use cached intermediate results
            
        Returns:
            Replay result with comparison
        """
        if not self.pipeline_service:
            raise ValueError("Pipeline service not available")

        try:
            # Get original execution
            original = await self.pipeline_service.get_execution(job_id)
            
            if not original:
                raise ValueError(f"Execution {job_id} not found")

            logger.info(f"Replaying execution {job_id}")
            
            # Re-execute the pipeline
            new_job_id = await self.pipeline_service.execute_pipeline(
                pipeline_id=original["pipeline_id"],
                input_data=original.get("input_data", {}),
                checkpoint_enabled=False  # Don't checkpoint replays
            )

            # Wait for completion (with timeout)
            import asyncio
            for _ in range(60):  # 60 seconds timeout
                await asyncio.sleep(1)
                replay_exec = await self.pipeline_service.get_execution(new_job_id)
                if replay_exec and replay_exec["status"] in ["completed", "failed"]:
                    break

            replay_exec = await self.pipeline_service.get_execution(new_job_id)

            # Compare results
            comparison = self._compare_executions(original, replay_exec)

            return {
                "original_job_id": job_id,
                "replay_job_id": new_job_id,
                "original": {
                    "status": original["status"],
                    "output": original.get("output_data"),
                    "duration_ms": original.get("duration_ms"),
                    "steps": len(original.get("steps", []))
                },
                "replay": {
                    "status": replay_exec["status"],
                    "output": replay_exec.get("output_data"),
                    "duration_ms": replay_exec.get("duration_ms"),
                    "steps": len(replay_exec.get("steps", []))
                },
                "comparison": comparison,
                "replayed_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error replaying execution: {e}", exc_info=True)
            raise

    async def get_replay_history(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get history of replays for an execution
        
        Args:
            job_id: Original execution ID
            
        Returns:
            List of replay records
        """
        if not self.replayer:
            logger.warning("Event replayer not available")
            return []

        try:
            if hasattr(self.replayer, 'get_replay_history'):
                history = await self.replayer.get_replay_history(job_id)
                return [self._replay_to_dict(r) for r in history]
            
            # Fallback: query database
            if hasattr(self.replayer, 'storage') and hasattr(self.replayer.storage, 'db_manager'):
                query = """
                    SELECT replay_id, original_job_id, replay_job_id,
                           success, differences, replayed_at
                    FROM replay_history
                    WHERE original_job_id = :job_id
                    ORDER BY replayed_at DESC
                """
                result = await self.replayer.storage.db_manager.execute(
                    query,
                    {"job_id": job_id}
                )
                return [dict(row) for row in result]
            
            return []
        except Exception as e:
            logger.error(f"Error getting replay history: {e}")
            return []

    def _compare_executions(
        self,
        original: Dict[str, Any],
        replay: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare two executions and identify differences"""
        differences = []

        # Compare status
        if original["status"] != replay["status"]:
            differences.append({
                "field": "status",
                "original": original["status"],
                "replay": replay["status"]
            })

        # Compare output
        orig_output = original.get("output_data")
        replay_output = replay.get("output_data")
        
        if orig_output != replay_output:
            differences.append({
                "field": "output",
                "original": orig_output,
                "replay": replay_output,
                "match": False
            })
        
        # Compare step count
        orig_steps = len(original.get("steps", []))
        replay_steps = len(replay.get("steps", []))
        
        if orig_steps != replay_steps:
            differences.append({
                "field": "step_count",
                "original": orig_steps,
                "replay": replay_steps
            })

        # Compare duration (allow 10% variance)
        orig_duration = original.get("duration_ms", 0)
        replay_duration = replay.get("duration_ms", 0)
        
        if orig_duration > 0 and replay_duration > 0:
            variance = abs(orig_duration - replay_duration) / orig_duration
            if variance > 0.10:  # More than 10% difference
                differences.append({
                    "field": "duration",
                    "original": orig_duration,
                    "replay": replay_duration,
                    "variance_percent": variance * 100
                })

        return {
            "identical": len(differences) == 0,
            "difference_count": len(differences),
            "differences": differences,
            "output_match": orig_output == replay_output,
            "status_match": original["status"] == replay["status"]
        }

    def _replay_to_dict(self, replay) -> Dict:
        """Convert replay object to dictionary"""
        if isinstance(replay, dict):
            return replay

        return {
            "replay_id": getattr(replay, "replay_id", None),
            "original_job_id": getattr(replay, "original_job_id", None),
            "replay_job_id": getattr(replay, "replay_job_id", None),
            "success": getattr(replay, "success", False),
            "differences": getattr(replay, "differences", []),
            "replayed_at": getattr(replay, "replayed_at", None)
        }
