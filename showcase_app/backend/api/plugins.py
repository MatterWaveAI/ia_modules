"""Plugin management API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List
from models import PluginResponse, PluginDetailResponse, PluginExecuteRequest, PluginExecuteResponse, PluginLoadRequest, PluginLoadResponse

router = APIRouter()


def get_plugin_service(request: Request):
    """Dependency to get plugin service"""
    return request.app.state.services.plugin_service


@router.get("", response_model=List[PluginResponse])
async def list_plugins(service=Depends(get_plugin_service)):
    """List all registered plugins"""
    plugins = service.list_plugins()
    return plugins


@router.get("/{name}", response_model=PluginDetailResponse)
async def get_plugin(name: str, service=Depends(get_plugin_service)):
    """Get plugin details by name"""
    plugin = service.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return plugin


@router.post("/{name}/execute", response_model=PluginExecuteResponse)
async def execute_plugin(name: str, data: PluginExecuteRequest, service=Depends(get_plugin_service)):
    """Execute a plugin with parameters"""
    plugin = service.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    try:
        result = await service.execute_plugin(name, data.params)
        return PluginExecuteResponse(
            plugin=name,
            type=result["type"],
            result=result.get("result"),
            error=result.get("error"),
            success=True
        )
    except Exception as e:
        return PluginExecuteResponse(
            plugin=name,
            type="unknown",
            result=None,
            error=str(e),
            success=False
        )


@router.post("/load", response_model=PluginLoadResponse)
async def load_plugin(data: PluginLoadRequest, service=Depends(get_plugin_service)):
    """Load a plugin from a file path"""
    try:
        result = service.load_plugin(data.path)
        return PluginLoadResponse(
            loaded_count=result["loaded_count"],
            path=result["path"],
            success=True,
            message=f"Loaded {result['loaded_count']} plugin(s) from {result['path']}"
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}")
async def unload_plugin(name: str, service=Depends(get_plugin_service)):
    """Unload a plugin by name"""
    success = service.unload_plugin(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return {"message": f"Plugin '{name}' unloaded successfully"}
