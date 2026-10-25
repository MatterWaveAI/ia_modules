"""Guardrails API endpoints"""

from fastapi import APIRouter, HTTPException, Request
from models import (
    GuardrailsTestInputRequest,
    GuardrailsTestOutputRequest,
    GuardrailsPipelineRequest,
    GuardrailsTestResponse,
    GuardrailsPipelineResponse,
    GuardrailsRailsListResponse,
)

router = APIRouter()


def get_guardrails_service(request: Request):
    """Dependency to get guardrails service"""
    return request.app.state.services.guardrails_service


@router.get("/rails", response_model=GuardrailsRailsListResponse)
async def list_rails(request: Request):
    """List all available guardrail types and their metadata"""
    service = get_guardrails_service(request)
    catalog = service.list_available_rails()
    return GuardrailsRailsListResponse(rails=catalog)


@router.post("/test-input", response_model=GuardrailsTestResponse)
async def test_input_rail(data: GuardrailsTestInputRequest, request: Request):
    """Test an input rail against provided text"""
    service = get_guardrails_service(request)
    try:
        result = await service.test_input_rail(
            text=data.text,
            rail_type=data.rail_type,
            options=data.options,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return GuardrailsTestResponse(**result)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-output", response_model=GuardrailsTestResponse)
async def test_output_rail(data: GuardrailsTestOutputRequest, request: Request):
    """Test an output rail against provided text"""
    service = get_guardrails_service(request)
    try:
        result = await service.test_output_rail(
            text=data.text,
            rail_type=data.rail_type,
            options=data.options,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return GuardrailsTestResponse(**result)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=GuardrailsPipelineResponse)
async def run_guardrails_pipeline(data: GuardrailsPipelineRequest, request: Request):
    """Run a full guardrails pipeline with multiple rails"""
    service = get_guardrails_service(request)
    try:
        result = await service.run_guardrails_pipeline(
            text=data.text,
            config={
                "input_rails": data.input_rails,
                "output_rails": data.output_rails,
                "options": data.options,
            },
        )
        return GuardrailsPipelineResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
