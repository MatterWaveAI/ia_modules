"""
Decision Agent Step — real LLM-backed decision step built on LLMStep.

Subclasses LLMStep and asks the CLI agent to return a short JSON decision.
The raw LLM text is parsed best-effort for `decision` and `confidence`; if
parsing fails the text is kept as-is and confidence defaults to 0.5.
"""

import json
import re
from typing import Any, Dict

from ia_modules.pipeline.llm_step import LLMStep
from ia_modules.pipeline.llm_config import get_agent_config, get_llm_config


_SYSTEM_PROMPTS = {
    "validation": (
        "You are a validation decision agent. Given a task, content, and prior "
        "agent output, decide whether to accept or reject. Respond ONLY with a "
        'JSON object: {"decision": "accept"|"reject", "confidence": 0..1, '
        '"reasoning": "<short>"}. No markdown, no extra text.'
    ),
    "classification": (
        "You are a classification decision agent. Given a task and content, "
        "choose the best category. Respond ONLY with a JSON object: "
        '{"decision": "<category>", "confidence": 0..1, "reasoning": "<short>"}. '
        "No markdown, no extra text."
    ),
    "general": (
        "You are a decision agent. Given a task and content, make a decision. "
        'Respond ONLY with a JSON object: {"decision": "<your decision>", '
        '"confidence": 0..1, "reasoning": "<short>"}. No markdown, no extra text.'
    ),
}


def _parse_decision(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction from LLM response."""
    if not text:
        return {"decision": "unknown", "confidence": 0.5, "reasoning": ""}

    # Try direct parse first, then hunt for the first {...} block.
    for candidate in (text, _first_json_object(text)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return {
                    "decision": str(parsed.get("decision", "unknown")),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "reasoning": str(parsed.get("reasoning", "")),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    return {"decision": "unknown", "confidence": 0.5, "reasoning": text[:200]}


def _first_json_object(text: str) -> str:
    """Return the first {...} balanced block, or empty string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else ""


class DecisionAgentStep(LLMStep):
    """Agent step that asks a real LLM to make a decision."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self._decision_logic = config.get("decision_logic", "validation")
        system_prompt = _SYSTEM_PROMPTS.get(self._decision_logic, _SYSTEM_PROMPTS["general"])

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
        if not self.agent_available:
            return self._without_agent(data)
        task = data.get("task", "make decision")
        content = data.get("content", "")
        prior = data.get("prior_agent_output", "")

        parts = [f"Task: {task}"]
        if content:
            parts.append(f"Content: {content}")
        if prior:
            parts.append(f"Previous agent output: {prior}")
        prompt = "\n\n".join(parts)

        # Only forward what LLMStep needs (see SimpleAgentStep.run for rationale).
        llm_input: Dict[str, Any] = {"prompt": prompt}
        if "_execution_id" in data:
            llm_input["_execution_id"] = data["_execution_id"]

        llm_result = await super().run(llm_input)
        text = llm_result.get("text", "")
        parsed = _parse_decision(text)

        return {
            "agent_name": self.name,
            "decision_logic": self._decision_logic,
            "decision_explanation": text,
            "decision": parsed["decision"],
            "confidence": parsed["confidence"],
            "reasoning": parsed["reasoning"],
            "agent_job_id": llm_result.get("agent_job_id"),
            "event_count": llm_result.get("event_count", 0),
            "metadata": {
                "step_id": self.name,
                "agent_kind": "llm_decision_agent",
            },
        }

    # Without a registered agent executor the step decides by the rule it used
    # before it was LLM-backed: accept when there is a task and content to act on.
    def _without_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        has_task = bool(str(data.get("task", "")).strip())
        has_content = bool(str(data.get("content", "")).strip())
        if has_task and has_content:
            decision, confidence, reasoning = "accept", 0.8, "has both a task and content"
        elif has_task or has_content:
            decision, confidence, reasoning = "accept", 0.6, "has a task or content, not both"
        else:
            decision, confidence, reasoning = "reject", 0.9, "neither a task nor content"
        return {
            "agent_name": self.name,
            "decision_logic": self._decision_logic,
            "decision_explanation": f"{reasoning}; decided without an agent executor",
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "agent_job_id": None,
            "event_count": 0,
            "metadata": {"step_id": self.name, "agent_kind": "rule_based"},
        }
