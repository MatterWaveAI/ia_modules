"""Pipeline management API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List
from models import PipelineCreate, PipelineUpdate, PipelineResponse, PipelineGraphResponse, GraphNode, GraphEdge

router = APIRouter()


def get_pipeline_service(request: Request):
    """Dependency to get pipeline service"""
    return request.app.state.services.pipeline_service


@router.get("", response_model=List[PipelineResponse])
async def list_pipelines(service=Depends(get_pipeline_service)):
    """List all pipelines"""
    pipelines = await service.list_pipelines()
    return pipelines


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str, service=Depends(get_pipeline_service)):
    """Get pipeline by ID"""
    pipeline = await service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.post("", response_model=PipelineResponse)
async def create_pipeline(data: PipelineCreate, service=Depends(get_pipeline_service)):
    """Create new pipeline"""
    pipeline_id = await service.create_pipeline(data.model_dump())
    pipeline = await service.get_pipeline(pipeline_id)
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    data: PipelineUpdate,
    service=Depends(get_pipeline_service)
):
    """Update pipeline"""
    success = await service.update_pipeline(pipeline_id, data.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline = await service.get_pipeline(pipeline_id)
    return pipeline


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, service=Depends(get_pipeline_service)):
    """Delete pipeline"""
    success = await service.delete_pipeline(pipeline_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return {"message": "Pipeline deleted successfully"}


@router.get("/{pipeline_id}/graph", response_model=PipelineGraphResponse)
async def get_pipeline_graph(pipeline_id: str, service=Depends(get_pipeline_service)):
    """Get pipeline as graph structure for visualization"""
    pipeline = await service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    config = pipeline.get("config", {})
    steps = config.get("steps", [])
    flow = config.get("flow", {})
    
    # Generate nodes from steps
    nodes = []
    for idx, step in enumerate(steps):
        nodes.append(GraphNode(
            id=step.get("id", f"step{idx+1}"),
            type="step",
            label=step.get("name", f"Step {idx+1}"),
            config=step.get("config", {}),
            position={"x": 250, "y": idx * 120}
        ))
    
    edges = []
    paths = flow.get("paths", [])
    
    for path in paths:
        from_step = path.get("from_step", path.get("from"))
        to_step = path.get("to_step", path.get("to"))
        
        if from_step and to_step:
            edges.append(GraphEdge(
                source=from_step,
                target=to_step,
                condition=path.get("condition"),
                label=path.get("condition", {}).get("description") if path.get("condition") else None
            ))
    
    return PipelineGraphResponse(nodes=nodes, edges=edges)
