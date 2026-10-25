"""
Simple Agent Step — real LLM-backed step built on LLMStep.

Subclasses LLMStep so the agent pipeline actually spawns a CLI agent (opencode
or claude_code) instead of returning hard-coded dicts. Env configuration
(provider, model, api_key, cwd, logs_dir, timeout) is read from the same
environment variables used by showcase_app's collaboration patterns.
"""

from typing import Any, Dict

from ia_modules.pipeline.llm_step import LLMStep
from ia_modules.pipeline.llm_config import get_agent_config, get_llm_config


_SYSTEM_PROMPTS = {
    "ingestion": (
        "You are a data ingestion agent. Analyse the user's task and content, "
        "then respond with: (1) a brief summary, (2) key entities or concepts, "
        "(3) a data quality note, and (4) recommended next processing steps. "
        "Keep the full response under 200 words."
    ),
    "final_processing": (
        "You are a final-processing agent. Produce the final result for the "
        "user's task using the supplied content and prior agent output. "
        "Respond with: (1) the final result, (2) a one-line confidence note, "
        "and (3) any warnings. Keep the full response under 200 words."
    ),
    "general": (
        "You are an AI processing agent. Analyse the user's task and content "
        "and return a concise structured response with your analysis, result, "
        "and confidence. Keep the full response under 200 words."
    ),
}


class SimpleAgentStep(LLMStep):
    """Agent step that spawns a real LLM subprocess for ingestion/final processing."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self._processing_type = config.get("processing_type", "general")
        system_prompt = _SYSTEM_PROMPTS.get(self._processing_type, _SYSTEM_PROMPTS["general"])

        env_config = get_llm_config()
        agent_cfg = get_agent_config()
        merged = {
            **config,
            "system_prompt": system_prompt,
            "cwd": agent_cfg["cwd"],
            "logs_dir": agent_cfg["logs_dir"],
            "timeout_seconds": agent_cfg["timeout_seconds"],
            **env_config,
        }
        super().__init__(name, merged)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the LLM and return the agent output."""
        if not self.agent_available:
            return self._without_agent(data)
        task = data.get("task", "process data")
        content = data.get("content", "")

        parts = [f"Task: {task}"]
        if content:
            parts.append(f"Content: {content}")
        # Final-processing prompts also receive upstream agent outputs so the
        # step can actually "finalize" rather than re-run on raw input.
        ingestion_summary = data.get("ingestion_summary")
        if ingestion_summary:
            parts.append(f"Ingestion summary: {ingestion_summary}")
        decision = data.get("decision")
        if decision:
            parts.append(f"Decision: {decision}")
        decision_reasoning = data.get("decision_reasoning")
        if decision_reasoning:
            parts.append(f"Decision reasoning: {decision_reasoning}")
        prompt = "\n\n".join(parts)

        # Only forward what LLMStep needs. Splatting **data into super().run()
        # would bloat AgentConfig.metadata (and the agent NDJSON log) with the
        # full accumulated upstream payload.
        llm_input: Dict[str, Any] = {"prompt": prompt}
        if "_execution_id" in data:
            llm_input["_execution_id"] = data["_execution_id"]

        llm_result = await super().run(llm_input)

        return {
            "agent_name": self.name,
            "processing_type": self._processing_type,
            "agent_output": llm_result.get("text", ""),
            "agent_job_id": llm_result.get("agent_job_id"),
            "event_count": llm_result.get("event_count", 0),
            "metadata": {
                "step_id": self.name,
                "agent_kind": "llm_agent",
            },
        }

    # Without a registered agent executor the step returns a rule-based note in
    # the same shape, so the agent pipeline runs end to end in tests.
    def _without_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        task = data.get("task", "process data")
        content = str(data.get("content", ""))
        return {
            "agent_name": self.name,
            "processing_type": self._processing_type,
            "agent_output": (
                f"[{self._processing_type}] {task}: {len(content)} characters of content, "
                "handled without an agent executor"
            ),
            "agent_job_id": None,
            "event_count": 0,
            "metadata": {"step_id": self.name, "agent_kind": "rule_based"},
        }
