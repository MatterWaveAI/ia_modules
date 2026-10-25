"""API endpoints for microVM management"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MicroVMApi:
    """API endpoints for microVM management"""

    def __init__(self, microvm_service):
        self.microvm_service = microvm_service
        self.router = APIRouter()
        self._setup_routes()

    def _setup_routes(self):
        @self.router.post("/microvm/launch")
        async def launch_vm(vm_config: Dict[str, Any], agent_config: Dict[str, Any]):
            """Launch a new microVM"""
            try:
                result = await self.microvm_service.launch_vm(vm_config, agent_config)
                return {"status": "success", "data": result}
            except Exception as e:
                logger.error(f"Failed to launch VM: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/microvm/{vm_id}/execute")
        async def execute_task(vm_id: str, task_data: Dict[str, Any]):
            """Execute task in VM agent"""
            try:
                result = await self.microvm_service.execute_agent_task(vm_id, task_data)
                return {"status": "success", "data": result}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"Failed to execute task in VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/microvm/{vm_id}/metrics")
        async def get_vm_metrics(vm_id: str):
            """Get VM resource metrics"""
            try:
                metrics = await self.microvm_service.monitor_vm_resources(vm_id)
                if not metrics:
                    raise HTTPException(status_code=404, detail=f"VM {vm_id} not found")
                return {"status": "success", "data": metrics}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get metrics for VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.delete("/microvm/{vm_id}")
        async def terminate_vm(vm_id: str, background_tasks: BackgroundTasks):
            """Terminate VM"""
            try:
                # Run termination in background to avoid blocking
                background_tasks.add_task(self.microvm_service.terminate_vm, vm_id)
                return {"status": "success", "message": f"VM {vm_id} termination initiated"}
            except Exception as e:
                logger.error(f"Failed to terminate VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/microvm")
        async def list_vms():
            """List active VMs"""
            try:
                vms = await self.microvm_service.list_active_vms()
                return {"status": "success", "data": vms}
            except Exception as e:
                logger.error(f"Failed to list VMs: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/microvm/{vm_id}/checkpoints")
        async def get_vm_checkpoints(vm_id: str):
            """Get checkpoints for a VM"""
            try:
                checkpoints = await self.microvm_service.checkpoint_service.list_checkpoints(vm_id)
                return {"status": "success", "data": checkpoints}
            except Exception as e:
                logger.error(f"Failed to get checkpoints for VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/microvm/{vm_id}/resume")
        async def resume_vm(vm_id: str, checkpoint_id: str):
            """Resume VM from checkpoint"""
            try:
                result = await self.microvm_service.checkpoint_service.resume_from_checkpoint(checkpoint_id)
                return {"status": "success", "data": result}
            except Exception as e:
                logger.error(f"Failed to resume VM {vm_id} from checkpoint {checkpoint_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))