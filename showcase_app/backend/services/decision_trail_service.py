"""
Decision Trail Service

Wraps ia_modules DecisionTrailBuilder for the showcase app.

The real library API is a single coroutine: `build_trail(thread_id, checkpoint_id,
include_evidence) -> DecisionTrail`. Everything here is built by calling that once
and projecting the resulting dataclass into the shapes each API endpoint returns.
"""

from typing import Any, Dict, List, Optional

from ia_modules.reliability.decision_trail import DecisionTrail


class DecisionTrailService:
    """Service for managing decision trails and execution paths."""

    def __init__(self, decision_trail_builder, reliability_metrics):
        """
        Args:
            decision_trail_builder: ia_modules DecisionTrailBuilder instance
            reliability_metrics: ReliabilityMetrics service for context
        """
        self.decision_trail_builder = decision_trail_builder
        self.reliability_metrics = reliability_metrics

    async def _build(self, job_id: str) -> Optional[DecisionTrail]:
        """Call the real builder. `job_id` is the checkpointer thread_id."""
        if not self.decision_trail_builder:
            return None
        return await self.decision_trail_builder.build_trail(
            thread_id=job_id,
            checkpoint_id=None,
            include_evidence=True,
        )

    async def get_decision_trail(self, job_id: str) -> Dict[str, Any]:
        """Complete decision trail projected into nodes/edges for the UI."""
        try:
            trail = await self._build(job_id)
            if trail is None:
                return _empty_trail(job_id)

            nodes = _nodes_from_trail(trail)
            edges = _edges_from_trail(trail)

            return {
                "job_id": job_id,
                "thread_id": trail.thread_id,
                "checkpoint_id": trail.checkpoint_id,
                "goal": trail.goal,
                "success": trail.success,
                "nodes": nodes,
                "edges": edges,
                "metadata": trail.metadata,
                "statistics": _statistics(trail, nodes, edges),
                "timestamp": trail.timestamp,
                "duration_ms": trail.duration_ms,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get decision trail: {str(e)}")

    async def get_decision_node(self, job_id: str, node_id: str) -> Dict[str, Any]:
        """Look up a single node (step or tool call) by id."""
        try:
            trail = await self._build(job_id)
            if trail is None:
                raise ValueError(f"Decision trail not found: {job_id}")

            for node in _nodes_from_trail(trail):
                if node["id"] == node_id:
                    return {
                        "node_id": node_id,
                        "job_id": job_id,
                        **node,
                    }
            raise ValueError(f"Decision node not found: {node_id}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get decision node: {str(e)}")

    async def get_execution_path(self, job_id: str) -> List[Dict[str, Any]]:
        """Ordered list of agents that ran, one entry per recorded step."""
        try:
            trail = await self._build(job_id)
            if trail is None:
                return []

            # Prefer steps_taken (has success + error); fall back to execution_path.
            if trail.steps_taken:
                return [
                    {
                        "step": step.step_index,
                        "node_id": f"step-{step.step_index}",
                        "agent": step.agent,
                        "success": step.success,
                        "error": step.error,
                        "duration_ms": step.duration_ms,
                        "retries": step.retries,
                        "timestamp": step.timestamp,
                    }
                    for step in trail.steps_taken
                ]

            return [
                {
                    "step": idx + 1,
                    "node_id": f"agent-{idx + 1}",
                    "agent": agent,
                }
                for idx, agent in enumerate(trail.execution_path)
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to get execution path: {str(e)}")

    async def get_decision_evidence(
        self, job_id: str, node_id: str
    ) -> List[Dict[str, Any]]:
        """Evidence collected during the run, optionally filtered to one node."""
        try:
            trail = await self._build(job_id)
            if trail is None:
                return []

            items = []
            for idx, ev in enumerate(trail.evidence):
                # A tool-call evidence item is tied to the node whose `source`
                # matches the tool name. If node_id is a step-N id we return all
                # evidence (per-step evidence isn't tracked by the real builder).
                if node_id.startswith("tool-") and ev.source != node_id[len("tool-") :]:
                    continue
                items.append(
                    {
                        "evidence_id": f"ev-{idx}",
                        "type": ev.type,
                        "source": ev.source,
                        "content": ev.content,
                        "confidence": ev.confidence,
                        "timestamp": ev.timestamp,
                        "metadata": ev.metadata,
                    }
                )
            return items
        except Exception as e:
            raise RuntimeError(f"Failed to get decision evidence: {str(e)}")

    async def get_alternative_paths(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Alternative paths are not tracked by the real DecisionTrailBuilder — it
        only reconstructs the path actually taken. Return an empty list so the
        API stays well-formed instead of 500-ing.
        """
        return []

    async def export_trail(self, job_id: str, format: str = "json") -> Any:
        """Export the trail. `json` returns the projected dict; others render it."""
        try:
            trail_dict = await self.get_decision_trail(job_id)
            if format == "json":
                return trail_dict
            if format == "graphviz":
                return _export_graphviz(trail_dict)
            if format == "mermaid":
                return _export_mermaid(trail_dict)
            raise ValueError(f"Unsupported export format: {format}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to export trail: {str(e)}")


# -------- helpers (module-level so they aren't pickled with `self`) --------


def _empty_trail(job_id: str) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "thread_id": job_id,
        "checkpoint_id": "unknown",
        "goal": "",
        "success": False,
        "nodes": [],
        "edges": [],
        "metadata": {},
        "statistics": {
            "total_nodes": 0,
            "decision_points": 0,
            "total_edges": 0,
            "tool_calls": 0,
            "evidence_items": 0,
        },
        "timestamp": None,
        "duration_ms": 0,
    }


def _nodes_from_trail(trail: DecisionTrail) -> List[Dict[str, Any]]:
    """Flatten steps_taken and tool_calls into UI nodes."""
    nodes: List[Dict[str, Any]] = []

    for step in trail.steps_taken:
        nodes.append(
            {
                "id": f"step-{step.step_index}",
                "type": "step",
                "label": step.agent,
                "decision": "completed" if step.success else "failed",
                "confidence": 1.0 if step.success else 0.0,
                "timestamp": step.timestamp,
                "metadata": {
                    "error": step.error,
                    "duration_ms": step.duration_ms,
                    "retries": step.retries,
                },
            }
        )

    for tc in trail.tool_calls:
        nodes.append(
            {
                "id": f"tool-{tc.tool_name}",
                "type": "tool_call",
                "label": tc.tool_name,
                "decision": "success" if tc.success else "error",
                "confidence": 1.0 if tc.success else 0.0,
                "timestamp": tc.timestamp,
                "metadata": {
                    "parameters": tc.parameters,
                    "duration_ms": tc.duration_ms,
                    "error": tc.error,
                },
            }
        )

    return nodes


def _edges_from_trail(trail: DecisionTrail) -> List[Dict[str, Any]]:
    """Chain successive steps together as directed edges."""
    if len(trail.steps_taken) < 2:
        return []
    edges = []
    for prev, curr in zip(trail.steps_taken, trail.steps_taken[1:]):
        edges.append(
            {
                "from": f"step-{prev.step_index}",
                "to": f"step-{curr.step_index}",
                "label": "",
                "condition": None,
                "weight": 1.0,
            }
        )
    return edges


def _statistics(
    trail: DecisionTrail,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "total_nodes": len(nodes),
        "decision_points": len(trail.steps_taken),
        "total_edges": len(edges),
        "tool_calls": len(trail.tool_calls),
        "evidence_items": len(trail.evidence),
    }


def _export_graphviz(trail: Dict[str, Any]) -> str:
    lines = ["digraph DecisionTrail {", "  rankdir=LR;"]
    for node in trail["nodes"]:
        label = f"{node['label']}\\n{node.get('decision', '')}"
        lines.append(f'  "{node["id"]}" [label="{label}"];')
    for edge in trail["edges"]:
        lines.append(f'  "{edge["from"]}" -> "{edge["to"]}";')
    lines.append("}")
    return "\n".join(lines)


def _export_mermaid(trail: Dict[str, Any]) -> str:
    lines = ["graph LR"]
    for node in trail["nodes"]:
        label = f"{node['label']}: {node.get('decision', '')}"
        lines.append(f'  {node["id"]}["{label}"]')
    for edge in trail["edges"]:
        lines.append(f'  {edge["from"]} --> {edge["to"]}')
    return "\n".join(lines)
