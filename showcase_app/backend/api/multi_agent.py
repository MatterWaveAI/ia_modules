"""
Multi-Agent API Endpoints

Demonstrates multi-agent orchestration, communication tracking,
and workflow visualization.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime, UTC
import json
from services.multi_agent_service import MultiAgentService

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, workflow_id: str):
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
        self.active_connections[workflow_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, workflow_id: str):
        if workflow_id in self.active_connections:
            self.active_connections[workflow_id].remove(websocket)
            if not self.active_connections[workflow_id]:
                del self.active_connections[workflow_id]
    
    async def broadcast(self, workflow_id: str, message: dict):
        if workflow_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[workflow_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for connection in dead_connections:
                self.disconnect(connection, workflow_id)

manager = ConnectionManager()

# Service instance with WebSocket callback
multi_agent_service = MultiAgentService()


async def broadcast_workflow_event_impl(workflow_id: str, event_type: str, data: dict):
    """Broadcast workflow events via WebSocket"""
    message = {
        "type": event_type,
        "workflow_id": workflow_id,
        "timestamp": data.get("timestamp"),
        "data": data
    }
    await manager.broadcast(workflow_id, message)


# Set WebSocket callback on service
multi_agent_service.set_websocket_callback(broadcast_workflow_event_impl)


# ==================== REQUEST MODELS ====================

class AgentConfig(BaseModel):
    """Agent configuration"""
    id: str = Field(..., description="Unique agent ID in workflow")
    role: str = Field(..., description="Agent role (planner, coder, etc.)")
    description: str = Field(default="", description="Agent description")


class EdgeConfig(BaseModel):
    """Edge configuration"""
    from_: str = Field(..., alias="from", description="Source agent ID")
    to: str = Field(..., description="Target agent ID")
    condition: Optional[str] = Field(default=None, description="Condition name")
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class FeedbackLoopConfig(BaseModel):
    """Feedback loop configuration"""
    from_: str = Field(..., alias="from", description="Source agent ID")
    to: str = Field(..., description="Target agent ID")
    max_iterations: int = Field(default=3, description="Max loop iterations")


class WorkflowRequest(BaseModel):
    """Request to create workflow"""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    agents: List[AgentConfig] = Field(..., description="Agents in workflow")
    edges: List[EdgeConfig] = Field(..., description="Connections between agents")
    feedback_loops: Optional[List[FeedbackLoopConfig]] = Field(default=None)


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute workflow"""
    start_agent: str = Field(..., description="Starting agent ID")
    initial_data: Dict[str, Any] = Field(default_factory=dict, description="Initial data")


# ==================== ENDPOINTS ====================

@router.post("/workflows")
async def create_workflow(request: WorkflowRequest) -> Dict[str, Any]:
    """
    Create a multi-agent workflow
    
    Builds a graph of agents with edges defining communication flow.
    Supports conditional routing and feedback loops.
    """
    try:
        # Convert Pydantic models to dicts
        agents = [agent.dict() for agent in request.agents]
        edges = [edge.dict(by_alias=True) for edge in request.edges]
        feedback_loops = None
        if request.feedback_loops:
            feedback_loops = [loop.dict(by_alias=True) for loop in request.feedback_loops]
        
        result = await multi_agent_service.create_workflow(
            workflow_id=request.workflow_id,
            agents=agents,
            edges=edges,
            feedback_loops=feedback_loops
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/executions")
async def execute_workflow(workflow_id: str, request: ExecuteWorkflowRequest) -> Dict[str, Any]:
    """
    Execute a multi-agent workflow (creates a new execution)
    
    Runs the workflow starting from the specified agent,
    tracking all agent communications and state changes.
    """
    try:
        result = await multi_agent_service.execute_workflow(
            workflow_id=workflow_id,
            start_agent=request.start_agent,
            initial_data=request.initial_data
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/{workflow_id}/state")
async def get_workflow_state(workflow_id: str) -> Dict[str, Any]:
    """
    Get current state of a workflow
    
    Returns workflow status, agent statistics, and current state snapshot.
    """
    try:
        result = await multi_agent_service.get_workflow_state(workflow_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/{workflow_id}/communications")
async def get_communications(
    workflow_id: str,
    execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get agent communication log
    
    Returns detailed log of all agent activations, messages, and completions.
    If execution_id is provided, returns that specific execution's communications.
    """
    try:
        communications = await multi_agent_service.get_agent_communications(
            workflow_id=workflow_id,
            execution_id=execution_id
        )
        
        return {
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "communications": communications
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows")
async def list_workflows() -> Dict[str, Any]:
    """
    List all workflows
    
    Returns summary of all created workflows.
    """
    try:
        workflows = multi_agent_service.list_workflows()
        return {
            "workflows": workflows,
            "total": len(workflows)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions")
async def list_executions(limit: int = 50) -> Dict[str, Any]:
    """
    List workflow executions
    
    Returns recent workflow executions across all workflows.
    """
    try:
        executions = multi_agent_service.get_execution_history(limit=limit)
        return {
            "executions": executions,
            "total": len(executions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_workflow_templates() -> Dict[str, Any]:
    """
    Get pre-built workflow templates
    
    Returns example multi-agent workflow configurations.
    """
    templates = {
        "simple_sequence": {
            "name": "Simple Sequence",
            "description": "Linear workflow: Planner → Researcher → Writer",
            "agents": [
                {"id": "planner", "role": "planner", "description": "Creates execution plan"},
                {"id": "researcher", "role": "researcher", "description": "Gathers information"},
                {"id": "writer", "role": "writer", "description": "Generates output"}
            ],
            "edges": [
                {"from": "planner", "to": "researcher"},
                {"from": "researcher", "to": "writer"}
            ]
        },
        "feedback_loop": {
            "name": "Feedback Loop",
            "description": "Coder → Critic feedback loop",
            "agents": [
                {"id": "coder", "role": "coder", "description": "Generates code"},
                {"id": "critic", "role": "critic", "description": "Reviews code"}
            ],
            "edges": [
                {"from": "coder", "to": "critic"}
            ],
            "feedback_loops": [
                {"from": "coder", "to": "critic", "max_iterations": 3}
            ]
        },
        "conditional_routing": {
            "name": "Conditional Routing",
            "description": "Router decides between specialist agents",
            "agents": [
                {"id": "router", "role": "router", "description": "Routes to specialist"},
                {"id": "analyst", "role": "analyst", "description": "Data analysis"},
                {"id": "generator", "role": "generator", "description": "Content generation"}
            ],
            "edges": [
                {"from": "router", "to": "analyst", "condition": "needs_analysis"},
                {"from": "router", "to": "generator", "condition": "needs_generation"}
            ]
        },
        "complex_workflow": {
            "name": "Complex Workflow",
            "description": "Multi-stage pipeline with feedback",
            "agents": [
                {"id": "planner", "role": "planner", "description": "Creates plan"},
                {"id": "researcher", "role": "researcher", "description": "Gathers data"},
                {"id": "coder", "role": "coder", "description": "Implements solution"},
                {"id": "tester", "role": "tester", "description": "Tests implementation"},
                {"id": "critic", "role": "critic", "description": "Final review"}
            ],
            "edges": [
                {"from": "planner", "to": "researcher"},
                {"from": "researcher", "to": "coder"},
                {"from": "coder", "to": "tester"},
                {"from": "tester", "to": "critic"}
            ],
            "feedback_loops": [
                {"from": "coder", "to": "tester", "max_iterations": 2}
            ]
        },
        "customer_service": {
            "name": "Customer Service",
            "description": "Intent classifier → Specialist handlers → Response generator",
            "agents": [
                {"id": "intent_classifier", "role": "classifier", "description": "Classifies customer intent"},
                {"id": "technical_support", "role": "technical_support", "description": "Handles technical issues"},
                {"id": "billing_support", "role": "billing_support", "description": "Handles billing inquiries"},
                {"id": "general_support", "role": "general_support", "description": "Handles general questions"},
                {"id": "response_generator", "role": "generator", "description": "Formats final response"}
            ],
            "edges": [
                {"from": "intent_classifier", "to": "technical_support", "condition": "intent=technical"},
                {"from": "intent_classifier", "to": "billing_support", "condition": "intent=billing"},
                {"from": "intent_classifier", "to": "general_support", "condition": "intent=general"},
                {"from": "technical_support", "to": "response_generator"},
                {"from": "billing_support", "to": "response_generator"},
                {"from": "general_support", "to": "response_generator"}
            ]
        },
        "code_review": {
            "name": "Code Review",
            "description": "Multi-perspective code analysis with consensus",
            "agents": [
                {"id": "security_reviewer", "role": "security_analyst", "description": "Reviews security concerns"},
                {"id": "performance_reviewer", "role": "performance_analyst", "description": "Analyzes performance"},
                {"id": "style_reviewer", "role": "style_checker", "description": "Checks code style"},
                {"id": "test_reviewer", "role": "test_analyst", "description": "Evaluates test coverage"},
                {"id": "synthesizer", "role": "synthesizer", "description": "Synthesizes all reviews"}
            ],
            "edges": [
                {"from": "security_reviewer", "to": "synthesizer"},
                {"from": "performance_reviewer", "to": "synthesizer"},
                {"from": "style_reviewer", "to": "synthesizer"},
                {"from": "test_reviewer", "to": "synthesizer"}
            ]
        },
        "content_pipeline": {
            "name": "Content Generation",
            "description": "Research → Draft → Edit → Fact-check pipeline",
            "agents": [
                {"id": "topic_researcher", "role": "researcher", "description": "Researches topic"},
                {"id": "outline_creator", "role": "planner", "description": "Creates content outline"},
                {"id": "draft_writer", "role": "writer", "description": "Writes first draft"},
                {"id": "editor", "role": "editor", "description": "Edits and improves"},
                {"id": "fact_checker", "role": "fact_checker", "description": "Verifies facts"}
            ],
            "edges": [
                {"from": "topic_researcher", "to": "outline_creator"},
                {"from": "outline_creator", "to": "draft_writer"},
                {"from": "draft_writer", "to": "editor"},
                {"from": "editor", "to": "fact_checker"}
            ],
            "feedback_loops": [
                {"from": "draft_writer", "to": "editor", "max_iterations": 2}
            ]
        },
        "data_analysis": {
            "name": "Data Analysis",
            "description": "ETL → Analysis → Visualization → Insight generation",
            "agents": [
                {"id": "data_extractor", "role": "extractor", "description": "Extracts data"},
                {"id": "data_cleaner", "role": "cleaner", "description": "Cleans and validates"},
                {"id": "statistical_analyzer", "role": "analyst", "description": "Statistical analysis"},
                {"id": "ml_analyzer", "role": "ml_analyst", "description": "ML pattern detection"},
                {"id": "visualizer", "role": "visualizer", "description": "Creates visualizations"},
                {"id": "insight_generator", "role": "insight_generator", "description": "Generates insights"}
            ],
            "edges": [
                {"from": "data_extractor", "to": "data_cleaner"},
                {"from": "data_cleaner", "to": "statistical_analyzer"},
                {"from": "data_cleaner", "to": "ml_analyzer"},
                {"from": "statistical_analyzer", "to": "visualizer"},
                {"from": "ml_analyzer", "to": "visualizer"},
                {"from": "visualizer", "to": "insight_generator"}
            ]
        },
        "debate_system": {
            "name": "Debate System",
            "description": "Multiple agents debate to reach consensus",
            "agents": [
                {"id": "moderator", "role": "moderator", "description": "Moderates debate"},
                {"id": "advocate", "role": "advocate", "description": "Argues for position"},
                {"id": "skeptic", "role": "critic", "description": "Challenges arguments"},
                {"id": "analyst", "role": "analyst", "description": "Provides data"},
                {"id": "judge", "role": "judge", "description": "Makes final decision"}
            ],
            "edges": [
                {"from": "moderator", "to": "advocate"},
                {"from": "moderator", "to": "skeptic"},
                {"from": "advocate", "to": "analyst"},
                {"from": "skeptic", "to": "analyst"},
                {"from": "analyst", "to": "judge"}
            ],
            "feedback_loops": [
                {"from": "advocate", "to": "skeptic", "max_iterations": 3}
            ]
        },
        "qa_system": {
            "name": "Q&A System",
            "description": "Question understanding → Multi-source retrieval → Answer synthesis",
            "agents": [
                {"id": "question_analyzer", "role": "analyzer", "description": "Analyzes question"},
                {"id": "knowledge_retriever", "role": "retriever", "description": "Retrieves knowledge"},
                {"id": "web_searcher", "role": "searcher", "description": "Searches web"},
                {"id": "answer_synthesizer", "role": "synthesizer", "description": "Synthesizes answer"},
                {"id": "verifier", "role": "verifier", "description": "Verifies accuracy"}
            ],
            "edges": [
                {"from": "question_analyzer", "to": "knowledge_retriever"},
                {"from": "question_analyzer", "to": "web_searcher"},
                {"from": "knowledge_retriever", "to": "answer_synthesizer"},
                {"from": "web_searcher", "to": "answer_synthesizer"},
                {"from": "answer_synthesizer", "to": "verifier"}
            ]
        },
        "creative_writing": {
            "name": "Creative Writing",
            "description": "Brainstorm → Draft → Critique → Refine loop",
            "agents": [
                {"id": "brainstormer", "role": "brainstormer", "description": "Generates ideas"},
                {"id": "plot_developer", "role": "planner", "description": "Develops plot"},
                {"id": "character_designer", "role": "designer", "description": "Designs characters"},
                {"id": "scene_writer", "role": "writer", "description": "Writes scenes"},
                {"id": "creative_critic", "role": "critic", "description": "Provides feedback"}
            ],
            "edges": [
                {"from": "brainstormer", "to": "plot_developer"},
                {"from": "plot_developer", "to": "character_designer"},
                {"from": "character_designer", "to": "scene_writer"},
                {"from": "scene_writer", "to": "creative_critic"}
            ],
            "feedback_loops": [
                {"from": "scene_writer", "to": "creative_critic", "max_iterations": 2}
            ]
        },
        "research_paper": {
            "name": "Research Paper",
            "description": "Comprehensive research paper generation pipeline",
            "agents": [
                {"id": "literature_reviewer", "role": "researcher", "description": "Reviews literature"},
                {"id": "hypothesis_generator", "role": "theorist", "description": "Generates hypotheses"},
                {"id": "methodology_designer", "role": "methodologist", "description": "Designs methodology"},
                {"id": "data_analyzer", "role": "analyst", "description": "Analyzes data"},
                {"id": "results_writer", "role": "writer", "description": "Writes results"},
                {"id": "peer_reviewer", "role": "reviewer", "description": "Peer review"}
            ],
            "edges": [
                {"from": "literature_reviewer", "to": "hypothesis_generator"},
                {"from": "hypothesis_generator", "to": "methodology_designer"},
                {"from": "methodology_designer", "to": "data_analyzer"},
                {"from": "data_analyzer", "to": "results_writer"},
                {"from": "results_writer", "to": "peer_reviewer"}
            ],
            "feedback_loops": [
                {"from": "results_writer", "to": "peer_reviewer", "max_iterations": 2}
            ]
        }
    }
    
    return {
        "templates": templates
    }


# ==================== WORKFLOW PERSISTENCE ====================

class SaveWorkflowRequest(BaseModel):
    """Request to save workflow"""
    name: str = Field(..., description="Human-readable workflow name")
    description: str = Field(default="", description="Workflow description")


@router.post("/workflows/{workflow_id}/save")
async def save_workflow(workflow_id: str, request: SaveWorkflowRequest) -> Dict[str, Any]:
    """
    Save workflow configuration to persistent storage
    
    Saves the workflow definition (agents, edges, feedback loops) to disk
    for later reuse.
    """
    try:
        result = await multi_agent_service.save_workflow(
            workflow_id=workflow_id,
            name=request.name,
            description=request.description
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/load")
async def load_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Load workflow configuration from persistent storage
    
    Restores a previously saved workflow definition.
    """
    try:
        result = await multi_agent_service.load_workflow(workflow_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/saved")
async def list_saved_workflows() -> Dict[str, Any]:
    """
    List all saved workflows
    
    Returns metadata for all workflows saved to persistent storage.
    """
    try:
        workflows = await multi_agent_service.list_saved_workflows()
        return {
            "workflows": workflows,
            "total": len(workflows)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/workflows/{workflow_id}/saved")
async def delete_saved_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Delete a saved workflow from persistent storage
    
    Permanently removes the workflow file from disk.
    """
    try:
        result = await multi_agent_service.delete_saved_workflow(workflow_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WORKFLOW EXPORT/IMPORT ====================

@router.get("/workflows/{workflow_id}/export")
async def export_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    Export workflow configuration as JSON
    
    Returns the complete workflow definition for backup or sharing.
    """
    if workflow_id not in multi_agent_service.active_workflows:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    try:
        workflow = multi_agent_service.active_workflows[workflow_id]
        orchestrator = workflow["orchestrator"]
        
        # Create export data
        agents_config = []
        for agent_id, agent in workflow["agents"].items():
            agents_config.append({
                "id": agent_id,
                "role": agent.role.name,
                "description": agent.role.description
            })
        
        edges_config = []
        for from_agent, edges in orchestrator.graph.items():
            for edge in edges:
                edge_dict = {
                    "from": from_agent,
                    "to": edge.to
                }
                if edge.condition:
                    edge_dict["condition"] = edge.condition.__name__ if callable(edge.condition) else str(edge.condition)
                edges_config.append(edge_dict)
        
        feedback_loops_config = []
        if hasattr(orchestrator, 'feedback_loops'):
            for loop_id, loop_data in orchestrator.feedback_loops.items():
                feedback_loops_config.append({
                    "from": loop_data.get("from"),
                    "to": loop_data.get("to"),
                    "max_iterations": loop_data.get("max_iterations", 3)
                })
        
        export_data = {
            "workflow_id": workflow_id,
            "name": workflow.get("name", workflow_id),
            "description": workflow.get("description", ""),
            "agents": agents_config,
            "edges": edges_config,
            "feedback_loops": feedback_loops_config,
            "exported_at": datetime.now(UTC).isoformat(),
            "version": "1.0"
        }
        
        return export_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/import")
async def import_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Import workflow configuration from JSON
    
    Creates a new workflow from exported configuration.
    """
    try:
        # Validate required fields
        if "workflow_id" not in workflow_data or "agents" not in workflow_data or "edges" not in workflow_data:
            raise ValueError("Invalid workflow data: missing required fields")
        
        result = await multi_agent_service.create_workflow(
            workflow_id=workflow_data["workflow_id"],
            agents=workflow_data["agents"],
            edges=workflow_data["edges"],
            feedback_loops=workflow_data.get("feedback_loops")
        )
        
        # Update metadata
        if workflow_data["workflow_id"] in multi_agent_service.active_workflows:
            multi_agent_service.active_workflows[workflow_data["workflow_id"]]["name"] = workflow_data.get("name")
            multi_agent_service.active_workflows[workflow_data["workflow_id"]]["description"] = workflow_data.get("description")
        
        return {
            **result,
            "imported_at": datetime.now(UTC).isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WEBSOCKET ====================

@router.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """
    WebSocket endpoint for real-time workflow updates
    
    Streams agent execution events, communications, and status updates
    in real-time to connected clients.
    """
    await manager.connect(websocket, workflow_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle ping/pong for keepalive
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, workflow_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, workflow_id)
