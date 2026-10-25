"""Memory API endpoints for conversation history"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from models import MemoryMessage, MemoryStats, MemorySearchRequest

router = APIRouter()


def get_memory_service(request: Request):
    """Dependency to get memory service"""
    return request.app.state.services.memory_service


@router.get("/{session_id}")
async def get_conversation_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=1000),
    service=Depends(get_memory_service)
):
    """
    Get conversation history for a session/execution
    
    Returns list of messages with role, content, timestamp, metadata
    """
    try:
        messages = await service.get_conversation_history(session_id, limit)
        message_responses = [MemoryMessage(**msg) for msg in messages]
        return {
            "session_id": session_id,
            "messages": message_responses,
            "count": len(message_responses)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/stats", response_model=MemoryStats)
async def get_memory_stats(
    session_id: str,
    service=Depends(get_memory_service)
):
    """
    Get memory statistics for a session
    
    Returns message count, tokens, first/last message timestamps
    """
    try:
        stats = await service.get_memory_stats(session_id)
        return MemoryStats(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memory(
    request: MemorySearchRequest,
    service=Depends(get_memory_service)
):
    """
    Search memory by query (semantic or keyword)
    
    Returns matching messages ranked by relevance
    """
    try:
        results = await service.search_memory(request.query, request.session_id, request.limit)
        return {
            "query": request.query,
            "session_id": request.session_id,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
