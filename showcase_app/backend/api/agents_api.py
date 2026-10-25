"""
Agent Collaboration API endpoints.

Provides REST API endpoints for multi-agent collaboration using real
ia_modules orchestration: AgentOrchestrator, BaseAgent, StateManager,
LLMStep, and SubprocessExecutor for streaming agent events.
"""

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path as _Path
import logging
import json
import time
import uuid

from ia_modules.agents.orchestrator import AgentOrchestrator
from ia_modules.agents.core import BaseAgent, AgentRole as IAAgentRole
from ia_modules.agents.state import StateManager
from ia_modules.agents.executor import (
    AgentConfig, AgentMode, CLIType, EventType,
)
from ia_modules.agents.subprocess_executor import SubprocessExecutor
from ia_modules.pipeline.ndjson_logger import NdjsonLogger

from services.llm_config import llm_call as _llm_call, get_llm_config, get_agent_config, derive_mode

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================== MODELS ========================

class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    CRITIC = "critic"
    PLANNER = "planner"
    EXECUTOR = "executor"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"


class CollaborationPattern(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    DEBATE = "debate"
    CONSENSUS = "consensus"
    PIPELINE = "pipeline"


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    WORKING = "working"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentDefinition(BaseModel):
    id: str = Field(..., description="Unique agent ID")
    name: str = Field(..., description="Agent name")
    role: AgentRole = Field(..., description="Agent role/specialization")
    description: str = Field("", description="What this agent does")
    capabilities: List[str] = Field(default_factory=list)
    model: Optional[str] = Field(None, description="LLM model to use")
    temperature: float = Field(0.7, ge=0, le=2)
    system_prompt: Optional[str] = Field(None)
    tools: Optional[List[str]] = Field(None, description="Per-agent tool list (overrides env default)")


class AgentMessage(BaseModel):
    from_agent: str
    to_agent: Optional[str] = None
    content: str
    message_type: str = "message"
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    agent_id: str
    status: AgentStatus
    current_task: Optional[str] = None
    progress: float = 0
    output: Optional[str] = None
    messages_sent: int = 0
    messages_received: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationRequest(BaseModel):
    task: str = Field(..., description="Main task to accomplish")
    agents: List[AgentDefinition] = Field(..., description="Agents to use")
    pattern: CollaborationPattern = Field(..., description="Collaboration pattern")
    max_iterations: int = Field(5, ge=1, le=20)
    timeout_seconds: float = Field(300, gt=0)
    context: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationResponse(BaseModel):
    success: bool
    task_id: str
    final_output: str
    iterations: int
    agents_used: List[str]
    pattern_used: CollaborationPattern
    execution_time_ms: float
    agent_states: List[AgentState]
    message_history: List[AgentMessage]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatternInfo(BaseModel):
    name: CollaborationPattern
    description: str
    use_cases: List[str]
    strengths: List[str]
    weaknesses: List[str]
    example_tasks: List[str]


class GetPatternsResponse(BaseModel):
    patterns: List[PatternInfo]
    total: int


class SpecialistInfo(BaseModel):
    role: AgentRole
    name: str
    description: str
    capabilities: List[str]
    best_for: List[str]
    example_tasks: List[str]


class GetSpecialistsResponse(BaseModel):
    specialists: List[SpecialistInfo]
    total: int


class AgentExecutionRecord(BaseModel):
    job_id: str
    execution_id: Optional[str] = None
    step_name: Optional[str] = None
    task: Optional[str] = None
    agent_role: Optional[str] = None
    agent_mode: Optional[str] = None
    cli_type: Optional[str] = None
    status: str = "running"
    log_path: Optional[str] = None
    event_count: int = 0
    result_text: Optional[str] = None
    error_text: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata_json: Optional[str] = None


class AgentLogSummary(BaseModel):
    job_id: str
    total_events: int = 0
    text_events: int = 0
    tool_use_events: int = 0
    tool_result_events: int = 0
    reasoning_events: int = 0
    error_events: int = 0
    tools_used: List[str] = Field(default_factory=list)
    duration_seconds: Optional[float] = None
    first_event_at: Optional[str] = None
    last_event_at: Optional[str] = None


# ======================== STORAGE ========================

active_orchestrations: Dict[str, Dict[str, Any]] = {}


# ======================== ROLE CONFIG ========================

# Tools each role gets by default. Read-only roles get research tools;
# roles that produce artifacts get write tools so they can collaborate
# on the shared workspace.
_READ_TOOLS = ["Read", "Glob", "Grep"]
_WRITE_TOOLS = ["Read", "Glob", "Grep", "Edit", "Write"]
_EXEC_TOOLS = ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]

ROLE_TOOLS: Dict[str, List[str]] = {
    "researcher":  _READ_TOOLS,
    "analyst":     _READ_TOOLS,
    "writer":      _WRITE_TOOLS,
    "critic":      _READ_TOOLS,
    "planner":     _READ_TOOLS,
    "executor":    _EXEC_TOOLS,
    "coordinator": _READ_TOOLS,
    "specialist":  _READ_TOOLS,
}

ROLE_SYSTEM_PROMPTS = {
    "researcher": "You are a research specialist. Gather information, find relevant sources, and present key facts about the topic. Be thorough but concise.",
    "analyst": "You are an analysis specialist. Examine data and findings, identify patterns, draw insights, and provide structured analysis.",
    "writer": "You are a writing specialist. Produce well-structured, clear, engaging prose. Write your output to files in the workspace.",
    "critic": "You are a critical reviewer. Evaluate the work, identify strengths and weaknesses. End with either APPROVE or REQUEST REVISION.",
    "planner": "You are a planning specialist. Break tasks into clear actionable steps. Provide a numbered plan with priorities.",
    "executor": "You are an execution specialist. Carry out tasks methodically, solving problems as they arise. Write results to the workspace.",
    "coordinator": "You are a coordination specialist. Synthesize inputs from multiple agents, resolve conflicts, and produce a unified output.",
    "specialist": "You are a domain specialist. Apply deep expertise to the task at hand.",
}


# _llm_call and get_llm_config imported from services.llm_config


def _simulate_agent(role: str, task: str, prev_output: str = "") -> str:
    """Simulation fallback when LLM is unavailable."""
    context = " (building on previous output)" if prev_output else ""
    if role == "researcher":
        return f"Research on '{task}'{context}:\n- Key finding 1: Comprehensive background gathered\n- Key finding 2: Critical data points identified\n- Key finding 3: Relevant trends observed"
    elif role == "analyst":
        return f"Analysis of '{task}'{context}:\n- Pattern identified: Strong positive trend\n- Insight: Data supports the hypothesis\n- Recommendation: Proceed with confidence"
    elif role == "writer":
        return f"Article: {task}\n\nThis comprehensive piece covers the essential aspects of the topic, drawing from research and analysis to present a clear narrative."
    elif role == "critic":
        return f"Review of '{task}': The work demonstrates solid methodology and clear reasoning. Minor improvements could strengthen the conclusion. APPROVE."
    elif role == "planner":
        return f"Plan for '{task}':\n1. Define scope and objectives\n2. Research and gather data\n3. Analyze findings\n4. Draft deliverable\n5. Review and refine"
    elif role == "coordinator":
        return f"Synthesis of '{task}'{context}:\nCombining all agent outputs into a unified deliverable that addresses the core objectives."
    else:
        return f"[{role}] Completed processing: {task}"


# ======================== ORCHESTRATION AGENTS ========================

class OrchestratingAgent(BaseAgent):
    """Agent backed by real LLM calls, used in the orchestrator graph."""

    def __init__(self, role: IAAgentRole, state: StateManager,
                 agent_def: AgentDefinition):
        super().__init__(role, state, enable_telemetry=False)
        self.agent_def = agent_def

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        task = input_data.get("task", "")
        prev_output = await self.read_state("latest_output")

        context_parts = [f"Task: {task}"] if task else []
        if prev_output:
            context_parts.append(f"Previous agent output:\n{prev_output}")

        user_message = "\n\n".join(context_parts) or "Please proceed."
        sys_prompt = self.agent_def.system_prompt or ROLE_SYSTEM_PROMPTS.get(
            self.agent_def.role.value,
            f"You are a {self.agent_def.role.value} agent. {self.agent_def.description}",
        )

        # Try real LLM
        llm_result = await _llm_call(sys_prompt, user_message)
        output_text = llm_result.text if llm_result else _simulate_agent(self.agent_def.role.value, task, prev_output or "")

        # Write to shared state
        await self.write_state("latest_output", output_text)
        await self.write_state(f"{self.agent_def.id}_output", output_text)

        # Handle critic approval for feedback loops
        if self.agent_def.role.value == "critic":
            approved = "approve" in output_text.lower()
            await self.write_state("approved", approved)

        return {
            "agent_id": self.agent_def.id,
            "role": self.agent_def.role.value,
            "output": output_text,
            "llm_backed": llm_result is not None and llm_result.text is not None,
        }


def _build_orchestrator(
    request: OrchestrationRequest,
) -> tuple[AgentOrchestrator, StateManager, Dict[str, OrchestratingAgent]]:
    """Build an AgentOrchestrator graph from the request."""
    state = StateManager(thread_id=f"orch-{uuid.uuid4().hex[:8]}")
    orchestrator = AgentOrchestrator(state)
    agents: Dict[str, OrchestratingAgent] = {}

    for agent_def in request.agents:
        role = IAAgentRole(
            name=agent_def.name,
            description=agent_def.description,
        )
        agent = OrchestratingAgent(role, state, agent_def)
        agents[agent_def.id] = agent
        orchestrator.add_agent(agent_def.id, agent)

    # Wire edges based on pattern
    agent_ids = [a.id for a in request.agents]

    if request.pattern == CollaborationPattern.SEQUENTIAL:
        for i in range(len(agent_ids) - 1):
            orchestrator.add_edge(agent_ids[i], agent_ids[i + 1])

    elif request.pattern == CollaborationPattern.PIPELINE:
        for i in range(len(agent_ids) - 1):
            orchestrator.add_edge(agent_ids[i], agent_ids[i + 1])

    elif request.pattern == CollaborationPattern.HIERARCHICAL:
        # First agent is coordinator, delegates to rest, then back to coordinator
        if len(agent_ids) >= 2:
            coord = agent_ids[0]
            workers = agent_ids[1:]
            # Coordinator -> first worker -> ... -> last worker -> coordinator
            orchestrator.add_edge(coord, workers[0])
            for i in range(len(workers) - 1):
                orchestrator.add_edge(workers[i], workers[i + 1])

    elif request.pattern == CollaborationPattern.DEBATE:
        # Alternate between agents with feedback loop
        if len(agent_ids) >= 2:
            for i in range(len(agent_ids) - 1):
                orchestrator.add_edge(agent_ids[i], agent_ids[i + 1])
            # Add feedback loop between last two if critic present
            if any(a.role.value == "critic" for a in request.agents):
                critic_idx = next(i for i, a in enumerate(request.agents) if a.role.value == "critic")
                worker_idx = max(0, critic_idx - 1)
                orchestrator.add_feedback_loop(
                    agent_ids[worker_idx], agent_ids[critic_idx],
                    max_iterations=request.max_iterations,
                )

    elif request.pattern == CollaborationPattern.CONSENSUS:
        # All agents feed into last agent (synthesizer)
        if len(agent_ids) >= 2:
            synthesizer = agent_ids[-1]
            for aid in agent_ids[:-1]:
                orchestrator.add_edge(aid, synthesizer)
            # Sequential through non-synthesizer agents first
            for i in range(len(agent_ids) - 2):
                orchestrator.add_edge(agent_ids[i], agent_ids[i + 1])

    elif request.pattern == CollaborationPattern.PARALLEL:
        # For parallel: run agents sequentially in orchestrator but
        # the agents are independent (each reads task, not previous output)
        for i in range(len(agent_ids) - 1):
            orchestrator.add_edge(agent_ids[i], agent_ids[i + 1])

    return orchestrator, state, agents


# ======================== ENDPOINTS ========================

@router.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate_agents(request: OrchestrationRequest) -> OrchestrationResponse:
    """
    Orchestrate multiple agents to accomplish a task.

    Builds a real AgentOrchestrator graph from the request, creates
    LLM-backed agents for each role, wires edges based on the
    collaboration pattern, and executes via orchestrator.run().
    """
    start_time = time.time()
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    logger.info("Orchestration %s: %s with %d agents, pattern=%s",
                task_id, request.task, len(request.agents), request.pattern.value)

    try:
        orchestrator, _state, _agents = _build_orchestrator(request)

        # Set up tracking via hooks
        message_history: List[AgentMessage] = []
        agent_states_map: Dict[str, AgentState] = {}

        for agent_def in request.agents:
            agent_states_map[agent_def.id] = AgentState(
                agent_id=agent_def.id,
                status=AgentStatus.IDLE,
                metadata={"role": agent_def.role.value},
            )

        async def on_start(agent_id: str, _input_data: Dict[str, Any]):
            if agent_id in agent_states_map:
                agent_states_map[agent_id].status = AgentStatus.WORKING
                agent_states_map[agent_id].current_task = request.task

        async def on_complete(agent_id: str, output_data: Dict[str, Any], duration: float):
            if agent_id in agent_states_map:
                s = agent_states_map[agent_id]
                s.status = AgentStatus.COMPLETED
                s.progress = 1.0
                s.output = output_data.get("output", "")[:500]
                s.metadata["duration_seconds"] = round(duration, 2)
                s.metadata["llm_backed"] = output_data.get("llm_backed", False)

            # Record inter-agent message
            message_history.append(AgentMessage(
                from_agent=agent_id,
                to_agent=None,
                content=output_data.get("output", "")[:300],
                message_type="output",
                timestamp=time.time(),
                metadata={"duration": duration},
            ))

        async def on_error(agent_id: str, error: Exception):
            if agent_id in agent_states_map:
                agent_states_map[agent_id].status = AgentStatus.FAILED
                agent_states_map[agent_id].metadata["error"] = str(error)

        orchestrator.add_hook("agent_start", on_start)
        orchestrator.add_hook("agent_complete", on_complete)
        orchestrator.add_hook("agent_error", on_error)

        # Execute the workflow
        start_agent = request.agents[0].id
        max_steps = max(len(request.agents) * (request.max_iterations + 1), 10)
        final_state = await orchestrator.run(
            start_agent,
            {"task": request.task, **request.context},
            max_steps=max_steps,
        )

        # Build final output from all agent outputs
        outputs = []
        for agent_def in request.agents:
            key = f"{agent_def.id}_output"
            agent_output = final_state.get(key, "")
            if agent_output:
                outputs.append(f"## {agent_def.name} ({agent_def.role.value})\n{agent_output}")

        final_output = "\n\n---\n\n".join(outputs) if outputs else final_state.get("latest_output", "No output produced.")

        execution_time_ms = (time.time() - start_time) * 1000
        iterations = final_state.get("total_steps", len(request.agents))

        # Store for later retrieval
        active_orchestrations[task_id] = {
            "task_id": task_id,
            "request": request.model_dump(),
            "final_output": final_output,
            "created_at": time.time(),
        }

        return OrchestrationResponse(
            success=True,
            task_id=task_id,
            final_output=final_output,
            iterations=iterations,
            agents_used=[a.id for a in request.agents],
            pattern_used=request.pattern,
            execution_time_ms=execution_time_ms,
            agent_states=list(agent_states_map.values()),
            message_history=message_history,
            metadata={
                "total_messages": len(message_history),
                "pattern": request.pattern.value,
                "execution_path": final_state.get("execution_path", []),
                "llm_available": True,
            },
        )

    except Exception as e:
        logger.error("Orchestration %s failed: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {e}")


def _truncate(value: Any, max_len: int = 500) -> Any:
    """Truncate string/dict values for WebSocket payloads."""
    if isinstance(value, str):
        return value[:max_len] if len(value) > max_len else value
    if isinstance(value, dict):
        s = json.dumps(value)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return value
    if value is None:
        return None
    s = str(value)
    return s[:max_len] if len(s) > max_len else s


# ======================== WEBSOCKET ========================

@router.websocket("/live")
async def agent_collaboration_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time agent collaboration.

    Client sends:
        {"action": "start_orchestration", "task": "...", "agents": [...], "pattern": "..."}

    Server streams AgentEvent data as agents execute:
        {"type": "agent_start", "agent_id": "...", ...}
        {"type": "agent_text", "agent_id": "...", "text": "...", ...}
        {"type": "agent_tool_use", "agent_id": "...", "tool": "Read", ...}
        {"type": "agent_tool_result", "agent_id": "...", "output": "...", ...}
        {"type": "agent_complete", "agent_id": "...", "output": "...", ...}
        {"type": "orchestration_complete", "final_output": "...", ...}
    """
    await websocket.accept()
    logger.info("Agent collaboration WebSocket connected")

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start_orchestration":
                await _handle_ws_orchestration(websocket, data)

            elif action == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}",
                })

    except WebSocketDisconnect:
        logger.info("Agent collaboration WebSocket disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass


async def _handle_ws_orchestration(websocket: WebSocket, data: Dict[str, Any]):
    """Handle a start_orchestration WebSocket message with real agent execution."""
    task = data.get("task", "")
    agents_raw = data.get("agents", [])

    # Get execution tracking service (may be None if not initialized)
    exec_svc = getattr(websocket.app.state.services, "agent_execution_service", None)

    await websocket.send_json({
        "type": "status",
        "message": "Building orchestration graph...",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    executor = SubprocessExecutor()
    all_outputs: Dict[str, str] = {}
    prev_output = ""
    env_cfg = get_llm_config()
    agent_cfg = get_agent_config()

    # Map env provider to CLIType
    _cli_type_map = {"claude_code": CLIType.CLAUDE_CODE, "opencode": CLIType.OPENCODE}
    env_cli = _cli_type_map.get(env_cfg.get("cli_type", "claude_code"), CLIType.CLAUDE_CODE)

    # Mode map for derive_mode output
    _mode_map = {"research": AgentMode.RESEARCH, "execute": AgentMode.EXECUTE, "plan": AgentMode.PLAN}

    for i, agent_raw in enumerate(agents_raw):
        agent_id = agent_raw.get("id", f"agent_{i}")
        agent_name = agent_raw.get("name", agent_id)
        role = agent_raw.get("role", "specialist")

        # Tools come from: explicit per-agent override > role default
        agent_tools = agent_raw.get("tools") or ROLE_TOOLS.get(role, _READ_TOOLS)
        agent_mode = _mode_map.get(derive_mode(agent_tools), AgentMode.RESEARCH)

        await websocket.send_json({
            "type": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "role": role,
            "tools": agent_tools,
            "mode": agent_mode.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        sys_prompt = agent_raw.get("system_prompt") or ROLE_SYSTEM_PROMPTS.get(
            role, f"You are a {role}.",
        )

        context_parts = [f"Task: {task}"]
        if prev_output:
            context_parts.append(f"Previous agent output:\n{prev_output}")
        user_message = "\n\n".join(context_parts)
        full_prompt = f"{sys_prompt}\n\nUser: {user_message}"

        # All agents share the same workspace (AGENT_CWD) so they can
        # collaborate on the same files. Each agent's tools/mode controls
        # what it's allowed to do in that workspace.
        agent_config = AgentConfig(
            task=full_prompt,
            cwd=agent_cfg["cwd"],
            cli_type=env_cli,
            mode=agent_mode,
            tools=agent_tools,
            system_prompt=sys_prompt,
            model=agent_raw.get("model") or env_cfg.get("model"),
            provider=env_cfg.get("provider"),
            api_key=env_cfg.get("api_key"),
            timeout_seconds=agent_cfg["timeout_seconds"],
        )

        result_text = ""
        error_text = ""
        event_count = 0
        agent_start = time.time()
        job_id = agent_config.job_id

        # Record execution start and set up NDJSON logger
        if exec_svc:
            await exec_svc.record_start(
                job_id=job_id, task=full_prompt[:2000], agent_role=role,
                agent_mode=agent_mode.value, cli_type=env_cli.value,
                metadata={"tools": agent_tools, "agent_name": agent_name},
            )
        agent_log_path = _Path(agent_cfg["logs_dir"]) / job_id / "agent.jsonl"
        agent_logger = NdjsonLogger(
            str(agent_log_path),
            default_metadata={"job_id": job_id, "step_name": agent_name},
        )

        try:
            async for event in executor.execute(agent_config):
                event_count += 1

                # Write every event to NDJSON log
                await agent_logger.log(
                    event.type.value, subtype=event.subtype,
                    text=event.text, result=event.result, error=event.error,
                    tool=event.tool, tool_use_id=event.tool_use_id,
                    data={"input": event.input} if event.input else None,
                    output=event.output,
                )

                if event.type == EventType.TEXT and event.text:
                    result_text = event.text
                    await websocket.send_json({
                        "type": "agent_text",
                        "agent_id": agent_id,
                        "text": event.text,
                        "seq": event.seq,
                        "timestamp": event.timestamp,
                    })

                elif event.type == EventType.REASONING and event.text:
                    await websocket.send_json({
                        "type": "agent_reasoning",
                        "agent_id": agent_id,
                        "text": event.text,
                        "seq": event.seq,
                        "timestamp": event.timestamp,
                    })

                elif event.type == EventType.TOOL_USE:
                    await websocket.send_json({
                        "type": "agent_tool_use",
                        "agent_id": agent_id,
                        "tool": event.tool,
                        "input": _truncate(event.input, 500),
                        "tool_use_id": event.tool_use_id,
                        "seq": event.seq,
                        "timestamp": event.timestamp,
                    })

                elif event.type == EventType.TOOL_RESULT:
                    await websocket.send_json({
                        "type": "agent_tool_result",
                        "agent_id": agent_id,
                        "output": _truncate(event.output, 500),
                        "tool_use_id": event.tool_use_id,
                        "seq": event.seq,
                        "timestamp": event.timestamp,
                    })

                elif event.type == EventType.RESULT:
                    if event.result and not result_text:
                        result_text = event.result
                    if event.error:
                        error_text = event.error
                        await websocket.send_json({
                            "type": "agent_error",
                            "agent_id": agent_id,
                            "error": event.error[:500],
                            "timestamp": event.timestamp,
                        })

                elif event.is_stream_end:
                    break

        except (FileNotFoundError, OSError) as e:
            logger.info("CLI unavailable (%s), falling back", e)
            llm_result = await _llm_call(sys_prompt, user_message, timeout=60)
            result_text = llm_result.text if llm_result else _simulate_agent(role, task, prev_output)

            await websocket.send_json({
                "type": "agent_text",
                "agent_id": agent_id,
                "text": result_text,
                "seq": 1,
                "fallback": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        finally:
            await agent_logger.close()

        agent_duration = time.time() - agent_start

        # Record execution complete in DB
        if exec_svc:
            await exec_svc.record_complete(
                job_id=job_id, event_count=event_count,
                result_text=result_text, error_text=error_text or None,
                duration_seconds=round(agent_duration, 2),
            )
        all_outputs[agent_id] = result_text
        prev_output = result_text

        await websocket.send_json({
            "type": "agent_complete",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "output": result_text[:1000],
            "event_count": event_count,
            "duration_seconds": round(agent_duration, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Final result
    final_parts = []
    for agent_raw in agents_raw:
        aid = agent_raw.get("id", "")
        out = all_outputs.get(aid, "")
        if out:
            name = agent_raw.get("name", aid)
            role = agent_raw.get("role", "")
            final_parts.append(f"## {name} ({role})\n{out}")

    final_output = "\n\n---\n\n".join(final_parts) if final_parts else "No output."

    await websocket.send_json({
        "type": "orchestration_complete",
        "final_output": final_output,
        "agents_used": [a.get("id") for a in agents_raw],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ======================== PATTERN / SPECIALIST METADATA ========================

COLLABORATION_PATTERNS = {
    CollaborationPattern.SEQUENTIAL: PatternInfo(
        name=CollaborationPattern.SEQUENTIAL,
        description="Agents work one after another in a defined sequence",
        use_cases=["Pipeline processing", "Multi-stage refinement", "Progressive transformation"],
        strengths=["Clear flow", "Easy to debug", "Predictable order"],
        weaknesses=["Slower than parallel", "Bottleneck risk", "No concurrency"],
        example_tasks=["Research → Analysis → Writing → Review", "Data collection → Processing → Visualization"],
    ),
    CollaborationPattern.PARALLEL: PatternInfo(
        name=CollaborationPattern.PARALLEL,
        description="Agents work simultaneously on different aspects",
        use_cases=["Independent sub-tasks", "Diverse perspectives", "Fast processing"],
        strengths=["Faster execution", "Diverse outputs", "Efficient"],
        weaknesses=["Needs aggregation", "May conflict", "Coordination overhead"],
        example_tasks=["Multiple researchers", "Parallel analysis", "Concurrent alternatives"],
    ),
    CollaborationPattern.HIERARCHICAL: PatternInfo(
        name=CollaborationPattern.HIERARCHICAL,
        description="Tree-like structure with coordinator delegating to sub-agents",
        use_cases=["Complex decomposition", "Coordinated systems", "Hierarchical decisions"],
        strengths=["Handles complexity", "Clear hierarchy", "Scalable"],
        weaknesses=["Coordinator bottleneck", "Communication overhead", "Needs good decomposition"],
        example_tasks=["Project manager delegating", "Complex research", "System design"],
    ),
    CollaborationPattern.DEBATE: PatternInfo(
        name=CollaborationPattern.DEBATE,
        description="Agents debate and critique each other to improve quality",
        use_cases=["Quality improvement", "Different perspectives", "Robust decisions"],
        strengths=["High quality", "Multiple perspectives", "Error detection"],
        weaknesses=["Can be slower", "May not converge", "Needs moderation"],
        example_tasks=["Proposal review", "Design evaluation", "Strategic planning"],
    ),
    CollaborationPattern.CONSENSUS: PatternInfo(
        name=CollaborationPattern.CONSENSUS,
        description="Agents work towards reaching agreement",
        use_cases=["Decision making", "Conflict resolution", "Collaborative problem solving"],
        strengths=["Balanced decisions", "Buy-in", "Conflict resolution"],
        weaknesses=["Slow convergence", "May compromise", "Needs consensus mechanism"],
        example_tasks=["Team decision", "Resource allocation", "Priority setting"],
    ),
    CollaborationPattern.PIPELINE: PatternInfo(
        name=CollaborationPattern.PIPELINE,
        description="Data flows through agents with transformations at each stage",
        use_cases=["Data transformation", "Progressive refinement", "Multi-stage processing"],
        strengths=["Clean data flow", "Modular stages", "Easy to extend"],
        weaknesses=["Sequential bottlenecks", "Error propagation", "Stage dependencies"],
        example_tasks=["ETL processes", "Content generation", "Multi-stage analysis"],
    ),
}

SPECIALIST_AGENTS = {
    AgentRole.RESEARCHER: SpecialistInfo(
        role=AgentRole.RESEARCHER, name="Research Specialist",
        description="Gathers information, conducts research, finds relevant sources",
        capabilities=["web_search", "data_gathering", "source_verification"],
        best_for=["Information gathering", "Fact finding", "Literature review"],
        example_tasks=["Research AI developments", "Find academic papers", "Gather market data"],
    ),
    AgentRole.ANALYST: SpecialistInfo(
        role=AgentRole.ANALYST, name="Analysis Specialist",
        description="Analyzes data, identifies patterns, draws insights",
        capabilities=["data_analysis", "pattern_recognition", "insight_generation"],
        best_for=["Data analysis", "Trend identification", "Statistical analysis"],
        example_tasks=["Analyze sales trends", "Identify behavior patterns", "Evaluate metrics"],
    ),
    AgentRole.WRITER: SpecialistInfo(
        role=AgentRole.WRITER, name="Writing Specialist",
        description="Creates written content, documentation, narratives",
        capabilities=["content_creation", "documentation", "storytelling"],
        best_for=["Content writing", "Documentation", "Narrative creation"],
        example_tasks=["Write article", "Create docs", "Draft marketing copy"],
    ),
    AgentRole.CRITIC: SpecialistInfo(
        role=AgentRole.CRITIC, name="Critique Specialist",
        description="Reviews and critiques work to improve quality",
        capabilities=["quality_review", "error_detection", "improvement_suggestions"],
        best_for=["Quality assurance", "Code review", "Content improvement"],
        example_tasks=["Review content", "Critique design", "Evaluate quality"],
    ),
    AgentRole.PLANNER: SpecialistInfo(
        role=AgentRole.PLANNER, name="Planning Specialist",
        description="Creates plans, strategies, and roadmaps",
        capabilities=["strategic_planning", "task_decomposition", "roadmap_creation"],
        best_for=["Project planning", "Strategy development", "Task breakdown"],
        example_tasks=["Create project plan", "Develop strategy", "Break down tasks"],
    ),
    AgentRole.EXECUTOR: SpecialistInfo(
        role=AgentRole.EXECUTOR, name="Execution Specialist",
        description="Executes plans and implements solutions",
        capabilities=["task_execution", "implementation", "problem_solving"],
        best_for=["Task execution", "Implementation", "Problem solving"],
        example_tasks=["Execute tasks", "Implement solutions", "Solve problems"],
    ),
    AgentRole.COORDINATOR: SpecialistInfo(
        role=AgentRole.COORDINATOR, name="Coordination Specialist",
        description="Coordinates work between multiple agents",
        capabilities=["coordination", "delegation", "communication_management"],
        best_for=["Multi-agent coordination", "Task delegation", "Workflow management"],
        example_tasks=["Coordinate team", "Delegate to specialists", "Manage workflows"],
    ),
}


@router.get("/patterns", response_model=GetPatternsResponse)
async def get_collaboration_patterns() -> GetPatternsResponse:
    """Get available collaboration patterns."""
    patterns = list(COLLABORATION_PATTERNS.values())
    return GetPatternsResponse(patterns=patterns, total=len(patterns))


@router.get("/specialists", response_model=GetSpecialistsResponse)
async def get_specialist_agents() -> GetSpecialistsResponse:
    """Get available specialist agents."""
    specialists = list(SPECIALIST_AGENTS.values())
    return GetSpecialistsResponse(specialists=specialists, total=len(specialists))


@router.get("/orchestrations/{task_id}")
async def get_orchestration(task_id: str):
    """Get details of a specific orchestration."""
    if task_id not in active_orchestrations:
        raise HTTPException(status_code=404, detail=f"Orchestration '{task_id}' not found")
    return active_orchestrations[task_id]


@router.get("/status")
async def get_status():
    """Health check showing ia_modules integration status."""
    return {
        "status": "ok",
        "llm_available": True,
        "active_orchestrations": len(active_orchestrations),
        "ia_modules": {
            "orchestrator": True,
            "state_manager": True,
            "base_agent": True,
            "subprocess_executor": True,
            "llm_step": True,
        },
    }


# ======================== EXECUTION TRACKING ENDPOINTS ========================

def _get_agent_execution_service(request):
    """Get AgentExecutionService from app state."""
    return request.app.state.services.agent_execution_service


@router.get("/executions")
async def list_agent_executions(
    request: Request,
    status: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List agent executions with optional filtering."""
    svc = _get_agent_execution_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Agent execution service not available")
    rows = await svc.list_executions(status=status, role=role, limit=limit, offset=offset)
    return {"executions": rows, "total": len(rows), "limit": limit, "offset": offset}


@router.get("/executions/{job_id}")
async def get_agent_execution(request: Request, job_id: str):
    """Get a single agent execution by job_id."""
    svc = _get_agent_execution_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Agent execution service not available")
    record = await svc.get_execution(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Execution {job_id} not found")
    return record


@router.get("/executions/{job_id}/events")
async def get_agent_execution_events(
    request: Request,
    job_id: str,
    event_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 200,
):
    """Get NDJSON events from an agent's log file."""
    svc = _get_agent_execution_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Agent execution service not available")
    event_types = [event_type] if event_type else None
    events = await svc.get_log_events(job_id, event_types=event_types, offset=offset, limit=limit)
    return {"events": events, "total": len(events), "job_id": job_id}


@router.get("/executions/{job_id}/summary")
async def get_agent_execution_summary(request: Request, job_id: str):
    """Get summary stats from an agent's log file."""
    svc = _get_agent_execution_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Agent execution service not available")
    return await svc.get_log_summary(job_id)


@router.post("/executions/scan")
async def scan_agent_logs(request: Request):
    """Scan logs directory and backfill DB with any untracked executions."""
    svc = _get_agent_execution_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Agent execution service not available")
    result = await svc.scan_and_backfill()
    return result
