"""
Collaboration Service

Implements four agent collaboration patterns using unified Step primitives:
- AgentOrchestrator + Step + StateManager for multi-agent graph execution
- LLMStep for LLM-backed agent reasoning (spawns CLI subprocess)
- FunctionStep for pure logic (aggregation, synthesis, routing)
- ParallelStep for fan-out (all voters at once, all debaters at once)

Patterns:
1. Consensus  – agents vote on a proposal, iterate until agreement threshold
2. Debate     – proponents vs opponents argue in rounds, moderator judges
3. Hierarchical – leader delegates subtasks to workers, aggregates results
4. Peer-to-peer – peers contribute ideas in rounds, building on each other
"""

from typing import Any, Awaitable, Callable, Dict, List
from datetime import datetime, UTC
import asyncio
import json
import logging
import uuid

from ia_modules.agents.orchestrator import AgentOrchestrator
from ia_modules.agents.state import StateManager
from ia_modules.pipeline.function_step import FunctionStep
from ia_modules.pipeline.llm_step import LLMStep
from ia_modules.pipeline.parallel_step import ParallelStep
from ia_modules.pipeline.services import ServiceRegistry

from services.llm_config import get_llm_config, get_agent_config

logger = logging.getLogger(__name__)

WSCallback = Callable[[Dict[str, Any]], Awaitable[None]]


# ---------------------------------------------------------------------------
# Role perspectives — give each voter a distinct bias so they don't all agree
# ---------------------------------------------------------------------------

_ROLE_PERSPECTIVES = {
    "analyst": "You prioritize data, metrics, and long-term scalability. You are skeptical of changes that lack measurable evidence. ",
    "engineer": "You prioritize developer productivity, code maintainability, and migration risk. You resist changes that add complexity without clear payoff. ",
    "designer": "You prioritize user experience, API ergonomics, and developer happiness. You favor elegant solutions over raw performance. ",
    "pm": "You prioritize shipping speed, business value, and time-to-market. You push back on proposals that slow delivery. ",
    "qa": "You prioritize testability, reliability, and risk mitigation. You are cautious about changes that could introduce regressions. ",
    "researcher-alpha": "You prioritize thoroughness, depth of analysis, and novel insights. ",
    "analyst-beta": "You prioritize practical applicability and cost-effectiveness. ",
    "writer-gamma": "You prioritize clarity, narrative coherence, and audience impact. ",
}

# ---------------------------------------------------------------------------
# Step builders — create Steps from agent role config
# ---------------------------------------------------------------------------

def _build_llm_step(name: str, system_prompt: str, timeout: int = 60) -> LLMStep:
    """Create an LLMStep with env-configured provider settings."""
    env_config = get_llm_config()
    agent_cfg = get_agent_config()
    return LLMStep(name, {
        "system_prompt": system_prompt,
        "timeout_seconds": timeout,
        "cwd": agent_cfg["cwd"],
        "logs_dir": agent_cfg["logs_dir"],
        **env_config,
    })


# ---------------------------------------------------------------------------
# FunctionStep factories for pure logic
# ---------------------------------------------------------------------------

def _make_vote_collector(agents: List[str]) -> FunctionStep:
    """Parse parallel voter results and store in shared state."""
    async def collect_votes(data, step):
        votes = {}
        for agent_name in agents:
            result = data.get(agent_name, {})
            result_text = result.get("result", "")
            job_id = result.get("agent_job_id")
            try:
                parsed = json.loads(result_text)
                vote = "approve" if parsed.get("vote", "").lower() == "approve" else "reject"
                reasoning = parsed.get("reasoning", result_text)
            except (json.JSONDecodeError, ValueError, TypeError):
                vote = "approve" if "approve" in str(result_text).lower() else "reject"
                reasoning = result_text or "No response"
            votes[agent_name] = {
                "vote": vote,
                "reasoning": f"{agent_name} votes {vote}: {reasoning}",
                "job_id": job_id,
            }
        await step.write_state("votes", votes)
        return {"votes_collected": len(votes), "votes": votes}

    return FunctionStep("vote_collector", {"fn": collect_votes})


def _make_aggregator() -> FunctionStep:
    """Tally votes and determine if consensus is reached."""
    async def tally_votes(_data, step):
        votes = await step.read_state("votes") or {}
        strategy = await step.read_state("strategy") or "majority"
        iteration = await step.read_state("iteration") or 1
        max_iters = await step.read_state("max_iterations") or 3

        approve = sum(1 for v in votes.values() if v["vote"] == "approve")
        total = len(votes)
        ratio = approve / total if total else 0

        thresholds = {"majority": 0.5, "supermajority": 0.67, "unanimous": 1.0, "weighted": 0.6}
        threshold = thresholds.get(strategy, 0.5)
        reached = ratio >= threshold

        if not reached and iteration < max_iters:
            await step.write_state("iteration", iteration + 1)
            await step.write_state("consensus_reached", False)
        else:
            await step.write_state("consensus_reached", True)
            await step.write_state("final_agreement", ratio)

        return {
            "approve": approve, "reject": total - approve,
            "ratio": ratio, "threshold": threshold,
            "consensus_reached": reached or iteration >= max_iters,
            "iteration": iteration,
        }

    return FunctionStep("aggregator", {"fn": tally_votes})


def _make_argument_collector(agents: List[str], side: str) -> FunctionStep:
    """Parse parallel debater results and append to shared state."""
    async def collect_arguments(data, step):
        arguments = await step.read_state("arguments") or []
        round_num = await step.read_state("current_round") or 1
        for agent_name in agents:
            result = data.get(agent_name, {})
            result_text = result.get("result", "")
            job_id = result.get("agent_job_id")
            point = f"[Round {round_num}] {agent_name}: {result_text}" if result_text else f"[Round {round_num}] {agent_name}: No response"
            arguments.append({
                "agent": agent_name, "side": side, "round": round_num,
                "argument": point, "job_id": job_id,
            })
        await step.write_state("arguments", arguments)
        return {"collected": len(agents), "side": side}

    return FunctionStep(f"{side}_collector", {"fn": collect_arguments})


def _make_moderator_logic() -> FunctionStep:
    """Moderator pure-logic: advance rounds or finalize."""
    async def moderate(data, step):
        arguments = await step.read_state("arguments") or []
        max_rounds = await step.read_state("max_rounds") or 2
        current_round = await step.read_state("current_round") or 1
        moderator_text = data.get("result", "")
        job_id = data.get("agent_job_id")

        pro_args = [a for a in arguments if a["side"] == "proponent"]
        con_args = [a for a in arguments if a["side"] == "opponent"]

        is_final = current_round >= max_rounds

        if is_final:
            await step.write_state("debate_done", True)
            summary = moderator_text or (
                f"Debate concluded after {current_round} rounds. "
                f"{len(pro_args)} pro vs {len(con_args)} con arguments."
            )
            await step.write_state("verdict", summary)
            await step.write_state("proponent_key_points", [a["argument"] for a in pro_args[-2:]])
            await step.write_state("opponent_key_points", [a["argument"] for a in con_args[-2:]])
        else:
            await step.write_state("current_round", current_round + 1)
            await step.write_state("debate_done", False)
            summary = f"Round {current_round} complete. {len(pro_args)} pro, {len(con_args)} con arguments so far."

        return {
            "agent": "moderator", "summary": summary, "round": current_round,
            "total_arguments": len(arguments), "job_id": job_id,
        }

    return FunctionStep("moderator_logic", {"fn": moderate})


def _make_subtask_parser(leader_name: str) -> FunctionStep:
    """Parse leader's subtask delegation from LLM response."""
    async def parse_subtasks(data, step):
        result_text = data.get("result", "")
        job_id = data.get("agent_job_id")
        workers = await step.read_state("worker_names") or []

        subtasks = {}
        if result_text:
            try:
                subtasks = json.loads(result_text)
            except (json.JSONDecodeError, ValueError):
                pass
        if not subtasks:
            task = await step.read_state("task") or ""
            for i, w in enumerate(workers):
                subtasks[w] = f"Subtask {i+1} of '{task[:50]}': Analyse aspect {i+1}"

        await step.write_state("subtasks", subtasks)
        await step.write_state("leader_phase", "aggregate")
        return {"agent": leader_name, "phase": "delegation", "subtasks": subtasks, "job_id": job_id}

    return FunctionStep("subtask_parser", {"fn": parse_subtasks})


def _make_worker_result_collector(workers: List[str]) -> FunctionStep:
    """Collect parallel worker results into shared state."""
    async def collect_results(data, step):
        worker_results = {}
        for w in workers:
            result = data.get(w, {})
            result_text = result.get("result", "")
            job_id = result.get("agent_job_id")
            has_error = result.get("step_error", False) or result.get("error")
            worker_results[w] = {
                "agent": w,
                "subtask": (await step.read_state("subtasks") or {}).get(w, ""),
                "status": "error" if has_error else "success",
                "output": result_text or str(result.get("error", "")),
                "job_id": job_id,
            }
        await step.write_state("worker_results", worker_results)
        return {"collected": len(workers), "worker_results": worker_results}

    return FunctionStep("worker_collector", {"fn": collect_results})


def _make_leader_aggregator(leader_name: str) -> FunctionStep:
    """Leader aggregation — pure logic summary of worker results."""
    async def aggregate(data, step):
        worker_results = await step.read_state("worker_results") or {}
        successful = sum(1 for r in worker_results.values() if r.get("status") == "success")
        failed = len(worker_results) - successful
        summary = f"Aggregated {len(worker_results)} worker results: {successful} succeeded, {failed} failed."
        await step.write_state("aggregation", summary)
        return {
            "agent": leader_name, "phase": "aggregation", "summary": summary,
            "total_workers": len(worker_results), "successful_workers": successful,
            "failed_workers": failed,
        }

    return FunctionStep("leader_aggregator", {"fn": aggregate})


def _make_peer_collector(peers: List[str]) -> FunctionStep:
    """Collect parallel peer contributions into shared state."""
    async def collect(data, step):
        contributions = await step.read_state("contributions") or []
        round_num = await step.read_state("peer_round") or 1
        for name in peers:
            result = data.get(name, {})
            result_text = result.get("result", "")
            job_id = result.get("agent_job_id")
            idea = f"{name} (round {round_num}): {result_text}" if result_text else f"{name} (round {round_num}): No response"
            contributions.append({
                "agent": name, "round": round_num,
                "contribution": idea, "job_id": job_id,
            })
        await step.write_state("contributions", contributions)
        return {"collected": len(peers)}

    return FunctionStep("peer_collector", {"fn": collect})


def _make_synthesizer() -> FunctionStep:
    """Synthesize peer contributions — advance rounds or finalize."""
    async def synthesize(data, step):
        contributions = await step.read_state("contributions") or []
        max_rounds = await step.read_state("max_rounds") or 2
        current_round = await step.read_state("peer_round") or 1

        round_contributions = [c for c in contributions if c["round"] == current_round]

        if current_round < max_rounds:
            await step.write_state("peer_round", current_round + 1)
            await step.write_state("peer_done", False)
            summary = f"Round {current_round}: {len(round_contributions)} contributions collected. Moving to next round."
        else:
            await step.write_state("peer_done", True)
            summary = f"All {max_rounds} rounds complete. {len(contributions)} total contributions."
            await step.write_state("final_synthesis", summary)

        return {
            "agent": "synthesizer", "round": current_round,
            "round_contributions": len(round_contributions),
            "total_contributions": len(contributions), "summary": summary,
        }

    return FunctionStep("synthesizer", {"fn": synthesize})


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class CollaborationService:
    """Runs collaboration patterns using unified Step primitives.

    Each pattern:
    1. Creates a StateManager (shared memory bus for real-time agent coordination)
    2. Creates an AgentOrchestrator (graph-based execution engine)
    3. Registers Steps: LLMStep (CLI agent), FunctionStep (pure logic), ParallelStep (fan-out)
    4. Wires the graph with add_edge
    5. Uses orchestrator hooks for history capture + WS broadcast
    6. Drives execution via orchestrator.run() or manual fan-out+gather
    """

    def __init__(self, container):
        """Resolve all deps from the ServiceContainer — no caller boilerplate.

        container must already have agent_executor, reliability_service,
        ws_manager, and agent_execution_service set (done in main.py lifespan).
        """
        self.execution_history: List[Dict[str, Any]] = []
        self.exec_svc = container.agent_execution_service
        self.agent_executor = container.agent_executor
        self.reliability_metrics = container.reliability_service.metrics
        self.ws_callback: WSCallback = container.ws_manager.broadcast_collaboration

    def _new_services(self) -> ServiceRegistry:
        """Build a per-run ServiceRegistry carrying the shared agent executor."""
        services = ServiceRegistry()
        services.register('agent_executor', self.agent_executor)
        services.register('reliability_metrics', self.reliability_metrics)
        return services

    async def _fail_run(self, run_id: str, pattern: str, error: Exception) -> None:
        """Flip a collab run to 'failed' in the DB and broadcast collab_complete.

        Called from each run_X method's except block so a crash before the
        normal _record_complete still unsticks the frontend and marks the
        agent_executions row.
        """
        await self._record_complete(run_id, [], error_text=str(error))
        await self._broadcast({"type": "collab_complete", "run_id": run_id,
                               "pattern": pattern, "error": str(error)})

    async def _broadcast(self, msg: Dict[str, Any]):
        """Send a step update via WS."""
        try:
            await self.ws_callback(msg)
        except Exception as e:
            logger.debug("WS broadcast failed: %s", e)

    async def _record_start(self, run_id: str, pattern: str, task: str, agents: List[str]):
        """Record a collaboration run starting in DB."""
        try:
            await self.exec_svc.record_start(
                job_id=run_id,
                task=task,
                agent_role=pattern,
                agent_mode="collaboration",
                cli_type="orchestrator",
                metadata={"pattern": pattern, "agents": agents},
            )
        except Exception as e:
            logger.debug("Failed to record collab start: %s", e)

    async def _record_complete(self, run_id: str, child_job_ids: List[str],
                                error_text: str = None, duration: float = None,
                                full_output: Dict[str, Any] = None):
        """Record a collaboration run completing in DB."""
        try:
            result_text = None
            if full_output:
                result_text = json.dumps(full_output, default=str)
            else:
                result_text = ",".join(jid for jid in child_job_ids if jid)
            await self.exec_svc.record_complete(
                job_id=run_id,
                event_count=len(child_job_ids),
                result_text=result_text,
                error_text=error_text,
                duration_seconds=duration,
            )
        except Exception as e:
            logger.debug("Failed to record collab complete: %s", e)

    def get_patterns(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "consensus",
                "name": "Consensus",
                "description": "Agents vote on a proposal and iterate until agreement is reached based on a configurable strategy (majority, supermajority, unanimous, weighted).",
                "use_cases": ["Decision making", "Group approval"],
            },
            {
                "id": "debate",
                "name": "Debate",
                "description": "Proponents and opponents argue across multiple rounds while a moderator summarises and renders a verdict.",
                "use_cases": ["Critical evaluation", "Adversarial reasoning"],
            },
            {
                "id": "hierarchical",
                "name": "Hierarchical",
                "description": "A leader decomposes a task, delegates subtasks to workers, then aggregates their results.",
                "use_cases": ["Task delegation", "Divide and conquer"],
            },
            {
                "id": "peer_to_peer",
                "name": "Peer-to-Peer",
                "description": "Equal peers contribute ideas in rounds, building on each other's work, with a synthesiser merging results.",
                "use_cases": ["Brainstorming", "Collaborative ideation"],
            },
        ]

    # ------------------------------------------------------------------
    # Consensus — parallel voters per round, then aggregator
    # ------------------------------------------------------------------

    async def run_consensus(self, topic: str, agents: List[str],
                            strategy: str = "majority", max_iterations: int = 3) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        try:
            return await self._run_consensus_impl(run_id, topic, agents, strategy, max_iterations)
        except Exception as e:
            await self._fail_run(run_id, "consensus", e)
            raise

    async def _run_consensus_impl(self, run_id: str, topic: str, agents: List[str],
                            strategy: str = "majority", max_iterations: int = 3) -> Dict[str, Any]:
        t0 = datetime.now(UTC)
        child_job_ids: List[str] = []
        history: List[Dict[str, Any]] = []
        state = StateManager(thread_id=f"consensus-{run_id}")
        orch = AgentOrchestrator(state, self._new_services())

        await self._record_start(run_id, "consensus", topic, agents)

        await state.set("topic", topic)
        await state.set("strategy", strategy)
        await state.set("max_iterations", max_iterations)
        await state.set("iteration", 1)

        # Build voter LLMSteps — each spawns a real CLI agent
        # Role-specific perspectives so agents don't all converge on the same answer
        voter_steps = []
        for name in agents:
            perspective = _ROLE_PERSPECTIVES.get(name.lower(), "")
            voter_steps.append(_build_llm_step(
                name,
                system_prompt=(
                    f"You are {name}, voting on a proposal. "
                    f"{perspective}"
                    "You MUST form your own independent opinion based on your role's priorities. "
                    "Reply with EXACTLY one JSON object: "
                    '{"vote": "approve" or "reject", "reasoning": "one sentence why"}'
                ),
            ))

        parallel_voters = ParallelStep("voters", {"steps": voter_steps})
        vote_collector = _make_vote_collector(agents)
        aggregator = _make_aggregator()

        orch.add_step("voters", parallel_voters)
        orch.add_step("vote_collector", vote_collector)
        orch.add_step("aggregator", aggregator)

        orch.add_edge("voters", "vote_collector")
        orch.add_edge("vote_collector", "aggregator")

        # Hook: capture history
        async def on_complete(step_name, result, duration):
            jid = result.get("agent_job_id") or result.get("job_id")
            # Collect job_ids from parallel voter results
            if step_name == "vote_collector":
                for v in (result.get("votes") or {}).values():
                    vjid = v.get("job_id")
                    if vjid:
                        child_job_ids.append(vjid)
            elif jid:
                child_job_ids.append(jid)
            entry = {"phase": "step_complete", "agent": step_name,
                     "message": result.get("reasoning", result.get("summary", str(result))),
                     "duration": duration, "timestamp": datetime.now(UTC).isoformat(),
                     "job_id": jid, "run_id": run_id,
                     **{k: v for k, v in result.items() if k in ("vote", "approve", "reject", "ratio", "consensus_reached")}}
            history.append(entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **entry})

        orch.add_hook("step_complete", on_complete)

        setup_entry = {"phase": "setup", "message": f"Consensus on: {topic}", "agents": agents,
                       "strategy": strategy, "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
        history.append(setup_entry)
        await self._broadcast({"type": "collab_step", "run_id": run_id, **setup_entry})

        # Manual loop — voters → collector → aggregator per iteration
        for iteration in range(1, max_iterations + 1):
            await state.set("iteration", iteration)

            round_entry = {"phase": f"voting_round_{iteration}",
                           "message": f"Iteration {iteration}: agents casting votes",
                           "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
            history.append(round_entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **round_entry})

            # Run voters in parallel
            snapshot = await state.snapshot()
            snapshot["prompt"] = f"Proposal (iteration {iteration}): {topic}"
            voter_result = await parallel_voters.run(snapshot)

            for hook in orch.on_step_complete:
                await hook("voters", voter_result, 0.05)

            # Collect votes into state
            collect_result = await vote_collector.run(voter_result)
            for hook in orch.on_step_complete:
                await hook("vote_collector", collect_result, 0.02)

            # Aggregate
            agg_result = await aggregator.run({})
            for hook in orch.on_step_complete:
                await hook("aggregator", agg_result, 0.02)

            if agg_result["consensus_reached"]:
                break

        consensus_reached = await state.get("consensus_reached", False)
        final_agreement = await state.get("final_agreement", agg_result.get("ratio", 0))
        votes = await state.get("votes", {})

        output = {
            "pattern": "consensus", "topic": topic, "strategy": strategy,
            "run_id": run_id, "child_job_ids": child_job_ids,
            "history": history,
            "result": {"consensus_reached": consensus_reached, "agreement_level": final_agreement,
                       "iterations": iteration, "votes": votes},
        }

        duration = (datetime.now(UTC) - t0).total_seconds()
        await self._record_complete(run_id, child_job_ids, duration=round(duration, 2), full_output=output)

        self.execution_history.append(output)
        await self._broadcast({"type": "collab_complete", "run_id": run_id, "pattern": "consensus"})
        return output

    # ------------------------------------------------------------------
    # Debate — proponents + opponents per round, then moderator
    # ------------------------------------------------------------------

    async def run_debate(self, topic: str, proponents: List[str], opponents: List[str],
                         moderator: str = "Moderator", rounds: int = 2) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        try:
            return await self._run_debate_impl(run_id, topic, proponents, opponents, moderator, rounds)
        except Exception as e:
            await self._fail_run(run_id, "debate", e)
            raise

    async def _run_debate_impl(self, run_id: str, topic: str, proponents: List[str], opponents: List[str],
                         moderator: str = "Moderator", rounds: int = 2) -> Dict[str, Any]:
        t0 = datetime.now(UTC)
        child_job_ids: List[str] = []
        history: List[Dict[str, Any]] = []
        state = StateManager(thread_id=f"debate-{run_id}")
        orch = AgentOrchestrator(state, self._new_services())

        all_agents = proponents + opponents + [moderator]
        await self._record_start(run_id, "debate", topic, all_agents)

        await state.set("topic", topic)
        await state.set("max_rounds", rounds)
        await state.set("current_round", 1)

        # Build debater LLMSteps
        pro_steps = []
        for name in proponents:
            pro_steps.append(_build_llm_step(
                name,
                system_prompt=(
                    f"You are {name}, a proponent in a debate. "
                    "Make one concise argument (2-3 sentences) FOR the topic."
                ),
            ))

        opp_steps = []
        for name in opponents:
            opp_steps.append(_build_llm_step(
                name,
                system_prompt=(
                    f"You are {name}, an opponent in a debate. "
                    "Make one concise argument (2-3 sentences) AGAINST the topic."
                ),
            ))

        parallel_pros = ParallelStep("proponents", {"steps": pro_steps})
        parallel_opps = ParallelStep("opponents", {"steps": opp_steps})
        pro_collector = _make_argument_collector(proponents, "proponent")
        opp_collector = _make_argument_collector(opponents, "opponent")

        moderator_llm = _build_llm_step(
            moderator,
            system_prompt="You are a debate moderator. Summarise the debate and declare which side argued better in 2-3 sentences.",
        )
        moderator_logic = _make_moderator_logic()

        # Register all steps so they get services (StateManager access)
        orch.add_step("proponents", parallel_pros)
        orch.add_step("opponents", parallel_opps)
        orch.add_step("pro_collector", pro_collector)
        orch.add_step("opp_collector", opp_collector)
        orch.add_step("moderator_llm", moderator_llm)
        orch.add_step("moderator_logic", moderator_logic)

        # Hook
        async def on_complete(step_name, result, duration):
            jid = result.get("agent_job_id") or result.get("job_id")
            if jid:
                child_job_ids.append(jid)
            entry = {"phase": "step_complete", "agent": step_name,
                     "message": result.get("argument", result.get("summary", str(result))),
                     "timestamp": datetime.now(UTC).isoformat(),
                     "job_id": jid, "run_id": run_id}
            if "side" in result:
                entry["side"] = result["side"]
            history.append(entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **entry})

        orch.add_hook("step_complete", on_complete)

        setup_entry = {"phase": "setup", "message": f"Debate: {topic}",
                       "proponents": proponents, "opponents": opponents,
                       "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
        history.append(setup_entry)
        await self._broadcast({"type": "collab_step", "run_id": run_id, **setup_entry})

        for rnd in range(1, rounds + 1):
            await state.set("current_round", rnd)
            round_entry = {"phase": f"round_{rnd}_opening", "message": f"Round {rnd} begins",
                           "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
            history.append(round_entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **round_entry})

            # Proponents argue
            snapshot = await state.snapshot()
            arguments = await state.get("arguments") or []
            prev_args = [a["argument"] for a in arguments[-4:]] if arguments else []
            prev_text = "\n".join(prev_args) if prev_args else "No previous arguments."
            snapshot["prompt"] = f"Topic: {topic}\nRound: {rnd}\nPrevious arguments:\n{prev_text}"

            pro_result = await parallel_pros.run(snapshot)
            pro_collect_result = await pro_collector.run(pro_result)
            for hook in orch.on_step_complete:
                await hook("proponents", pro_collect_result, 0.05)

            # Opponents argue
            snapshot = await state.snapshot()
            arguments = await state.get("arguments") or []
            prev_args = [a["argument"] for a in arguments[-4:]]
            prev_text = "\n".join(prev_args)
            snapshot["prompt"] = f"Topic: {topic}\nRound: {rnd}\nPrevious arguments:\n{prev_text}"

            opp_result = await parallel_opps.run(snapshot)
            opp_collect_result = await opp_collector.run(opp_result)
            for hook in orch.on_step_complete:
                await hook("opponents", opp_collect_result, 0.05)

            # Moderator summarizes (LLM only on final round)
            if rnd >= rounds:
                arguments = await state.get("arguments") or []
                pro_args = [a for a in arguments if a["side"] == "proponent"]
                con_args = [a for a in arguments if a["side"] == "opponent"]
                mod_prompt = f"Pro arguments: {[a['argument'] for a in pro_args]}\nCon arguments: {[a['argument'] for a in con_args]}"
                mod_result = await moderator_llm.run({"prompt": mod_prompt})
                mod_logic_result = await moderator_logic.run(mod_result)
            else:
                mod_logic_result = await moderator_logic.run({})

            for hook in orch.on_step_complete:
                await hook(moderator, mod_logic_result, 0.03)

        arguments = await state.get("arguments", [])
        verdict = await state.get("verdict", "")

        output = {
            "pattern": "debate", "topic": topic,
            "run_id": run_id, "child_job_ids": child_job_ids,
            "history": history,
            "result": {
                "status": "completed", "total_rounds": rounds,
                "total_arguments": len(arguments), "verdict": verdict,
                "proponent_key_points": await state.get("proponent_key_points", []),
                "opponent_key_points": await state.get("opponent_key_points", []),
            },
        }

        duration = (datetime.now(UTC) - t0).total_seconds()
        await self._record_complete(run_id, child_job_ids, duration=round(duration, 2), full_output=output)

        self.execution_history.append(output)
        await self._broadcast({"type": "collab_complete", "run_id": run_id, "pattern": "debate"})
        return output

    # ------------------------------------------------------------------
    # Hierarchical — leader delegates, parallel workers, leader aggregates
    # ------------------------------------------------------------------

    async def run_hierarchical(self, task: str, leader: str, workers: List[str]) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        try:
            return await self._run_hierarchical_impl(run_id, task, leader, workers)
        except Exception as e:
            await self._fail_run(run_id, "hierarchical", e)
            raise

    async def _run_hierarchical_impl(self, run_id: str, task: str, leader: str, workers: List[str]) -> Dict[str, Any]:
        t0 = datetime.now(UTC)
        child_job_ids: List[str] = []
        history: List[Dict[str, Any]] = []
        state = StateManager(thread_id=f"hierarchical-{run_id}")
        orch = AgentOrchestrator(state, self._new_services())

        all_agents = [leader] + workers
        await self._record_start(run_id, "hierarchical", task, all_agents)

        await state.set("task", task)
        await state.set("worker_names", workers)
        await state.set("leader_phase", "delegate")

        # Leader LLM for delegation
        leader_llm = _build_llm_step(
            leader,
            system_prompt="You are a project leader. Break the task into subtasks (one per worker). Reply with a JSON object mapping worker name to subtask string.",
        )
        subtask_parser = _make_subtask_parser(leader)

        # Worker LLMSteps
        worker_steps = []
        for name in workers:
            worker_steps.append(_build_llm_step(
                name,
                system_prompt=f"You are {name}, a worker. Complete the assigned subtask in 1-2 sentences.",
            ))
        worker_collector = _make_worker_result_collector(workers)
        leader_aggregator = _make_leader_aggregator(leader)

        # Register all steps so they get services (StateManager access)
        orch.add_step("leader_llm", leader_llm)
        orch.add_step("subtask_parser", subtask_parser)
        for ws in worker_steps:
            orch.add_step(ws.name, ws)
        orch.add_step("worker_collector", worker_collector)
        orch.add_step("leader_aggregator", leader_aggregator)

        # Hook
        async def on_complete(step_name, result, duration):
            jid = result.get("agent_job_id") or result.get("job_id")
            if jid:
                child_job_ids.append(jid)
            entry = {"phase": "step_complete", "agent": step_name,
                     "message": result.get("output", result.get("summary", str(result)[:200])),
                     "status": result.get("status", result.get("phase", "")),
                     "timestamp": datetime.now(UTC).isoformat(),
                     "job_id": jid, "run_id": run_id}
            history.append(entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **entry})

        orch.add_hook("step_complete", on_complete)

        setup_entry = {"phase": "setup", "message": f"Hierarchical task: {task}",
                       "leader": leader, "workers": workers,
                       "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
        history.append(setup_entry)
        await self._broadcast({"type": "collab_step", "run_id": run_id, **setup_entry})

        # Phase 1: Leader delegates
        leader_result = await leader_llm.run({"prompt": f"Task: {task}\nWorkers: {workers}"})
        delegation = await subtask_parser.run(leader_result)
        for hook in orch.on_step_complete:
            await hook(leader, delegation, 0.03)

        subtasks = await state.get("subtasks", {})
        deleg_entry = {"phase": "task_delegation",
                       "message": f"{leader} delegated {len(subtasks)} subtasks",
                       "agent": leader, "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
        history.append(deleg_entry)
        await self._broadcast({"type": "collab_step", "run_id": run_id, **deleg_entry})

        for w, sub in subtasks.items():
            assign_entry = {"phase": "task_assignment", "message": f"Assigned to {w}: {sub}",
                            "agent": w, "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
            history.append(assign_entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **assign_entry})

        # Phase 2: Workers execute in parallel — each gets its OWN subtask
        worker_tasks = []
        for step in worker_steps:
            my_task = subtasks.get(step.name, "general work")
            step.services = orch.services
            worker_tasks.append(step.run({"prompt": f"Subtask: {my_task}"}))

        worker_results_list = await asyncio.gather(*worker_tasks, return_exceptions=True)
        worker_result = {}
        for step, result in zip(worker_steps, worker_results_list):
            if isinstance(result, Exception):
                worker_result[step.name] = {"error": str(result), "step_error": True}
            else:
                worker_result[step.name] = result

        collect_result = await worker_collector.run(worker_result)
        for hook in orch.on_step_complete:
            await hook("workers", collect_result, 0.05)

        # Phase 3: Leader aggregates
        agg = await leader_aggregator.run({})
        for hook in orch.on_step_complete:
            await hook(leader, agg, 0.03)

        output = {
            "pattern": "hierarchical", "task": task,
            "run_id": run_id, "child_job_ids": child_job_ids,
            "history": history,
            "result": {
                "status": "success" if agg.get("failed_workers", 0) == 0 else "partial",
                "total_workers": agg.get("total_workers", len(workers)),
                "successful_workers": agg.get("successful_workers", 0),
                "failed_workers": agg.get("failed_workers", 0),
                "summary": agg.get("summary", ""),
            },
        }

        duration = (datetime.now(UTC) - t0).total_seconds()
        await self._record_complete(run_id, child_job_ids, duration=round(duration, 2), full_output=output)

        self.execution_history.append(output)
        await self._broadcast({"type": "collab_complete", "run_id": run_id, "pattern": "hierarchical"})
        return output

    # ------------------------------------------------------------------
    # Peer-to-peer — round-based fan-out + synthesizer
    # ------------------------------------------------------------------

    async def run_peer_to_peer(self, task: str, peers: List[str], rounds: int = 2) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        try:
            return await self._run_peer_to_peer_impl(run_id, task, peers, rounds)
        except Exception as e:
            await self._fail_run(run_id, "peer_to_peer", e)
            raise

    async def _run_peer_to_peer_impl(self, run_id: str, task: str, peers: List[str], rounds: int = 2) -> Dict[str, Any]:
        t0 = datetime.now(UTC)
        child_job_ids: List[str] = []
        history: List[Dict[str, Any]] = []
        state = StateManager(thread_id=f"p2p-{run_id}")
        orch = AgentOrchestrator(state, self._new_services())

        await self._record_start(run_id, "peer_to_peer", task, peers)

        await state.set("task", task)
        await state.set("max_rounds", rounds)
        await state.set("peer_round", 1)

        # Build peer LLMSteps
        peer_steps = []
        for name in peers:
            peer_steps.append(_build_llm_step(
                name,
                system_prompt=(
                    f"You are {name} brainstorming collaboratively. "
                    "Contribute one concise idea (1-2 sentences). "
                    "Build on previous ideas if any."
                ),
            ))
        parallel_peers = ParallelStep("peers", {"steps": peer_steps})
        peer_collector = _make_peer_collector(peers)
        synthesizer = _make_synthesizer()

        # Register all steps so they get services (StateManager access)
        orch.add_step("peers", parallel_peers)
        orch.add_step("peer_collector", peer_collector)
        orch.add_step("synthesizer", synthesizer)

        # Hook
        async def on_complete(step_name, result, duration):
            jid = result.get("agent_job_id") or result.get("job_id")
            if jid:
                child_job_ids.append(jid)
            entry = {"phase": "step_complete", "agent": step_name,
                     "message": result.get("contribution", result.get("summary", str(result))),
                     "timestamp": datetime.now(UTC).isoformat(),
                     "job_id": jid, "run_id": run_id}
            history.append(entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **entry})

        orch.add_hook("step_complete", on_complete)

        setup_entry = {"phase": "setup", "message": f"Peer-to-peer: {task}",
                       "peers": peers, "rounds": rounds,
                       "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
        history.append(setup_entry)
        await self._broadcast({"type": "collab_step", "run_id": run_id, **setup_entry})

        for rnd in range(1, rounds + 1):
            await state.set("peer_round", rnd)
            round_entry = {"phase": f"round_{rnd}_start", "message": f"Round {rnd} begins",
                           "timestamp": datetime.now(UTC).isoformat(), "run_id": run_id}
            history.append(round_entry)
            await self._broadcast({"type": "collab_step", "run_id": run_id, **round_entry})

            # Peers contribute in parallel
            snapshot = await state.snapshot()
            contributions = await state.get("contributions") or []
            prev = [c["contribution"] for c in contributions[-3:]] if contributions else []
            prev_text = "\n".join(prev) if prev else "None yet."
            snapshot["prompt"] = f"Task: {task}\nRound: {rnd}\nPrevious contributions:\n{prev_text}"

            peer_result = await parallel_peers.run(snapshot)
            collect_result = await peer_collector.run(peer_result)
            for hook in orch.on_step_complete:
                await hook("peers", collect_result, 0.04)

            # Synthesize
            synth_result = await synthesizer.run({})
            for hook in orch.on_step_complete:
                await hook("synthesizer", synth_result, 0.02)

        contributions = await state.get("contributions", [])

        output = {
            "pattern": "peer_to_peer", "task": task,
            "run_id": run_id, "child_job_ids": child_job_ids,
            "history": history,
            "result": {
                "status": "completed", "total_peers": len(peers),
                "total_contributions": len(contributions), "rounds_completed": rounds,
                "contributions": contributions,
            },
        }

        duration = (datetime.now(UTC) - t0).total_seconds()
        await self._record_complete(run_id, child_job_ids, duration=round(duration, 2), full_output=output)

        self.execution_history.append(output)
        await self._broadcast({"type": "collab_complete", "run_id": run_id, "pattern": "peer_to_peer"})
        return output
