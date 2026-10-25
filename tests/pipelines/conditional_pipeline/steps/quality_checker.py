"""
Quality Checker Step — LLM-backed data quality assessment.

Asks a real CLI agent to score the ingested data on a 0..1 scale and emit a
short JSON payload. The numeric `quality_score` is forwarded as a top-level
field so the pipeline's `threshold_condition` routing (high vs low quality
processor) keeps working.
"""

import json
import re
from typing import Any, Dict

from ia_modules.pipeline.llm_step import LLMStep
from ia_modules.pipeline.llm_config import get_agent_config, get_llm_config


_SYSTEM_PROMPT = (
    "You are a data quality assessment agent. Given a batch of records, "
    "judge their overall quality on a 0..1 scale (1 = pristine, 0 = unusable) "
    "and explain why in one sentence. Respond ONLY with a JSON object: "
    '{"quality_score": <float 0..1>, "data_quality": "<Poor|Fair|Good|Excellent>", '
    '"reasoning": "<short>"}. No markdown, no extra text.'
)


def _first_json_object(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else ""


def _parse_quality(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction. Falls back to a neutral 0.5 score."""
    if not text:
        return {"quality_score": 0.5, "data_quality": "Fair", "reasoning": ""}

    for candidate in (text, _first_json_object(text)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                score = float(parsed.get("quality_score", 0.5))
                # Clamp to [0, 1] so downstream threshold routing is stable.
                score = max(0.0, min(1.0, score))
                return {
                    "quality_score": score,
                    "data_quality": str(parsed.get("data_quality", "Fair")),
                    "reasoning": str(parsed.get("reasoning", "")),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    return {"quality_score": 0.5, "data_quality": "Fair", "reasoning": text[:200]}


class QualityCheckerStep(LLMStep):
    """Agent step that asks an LLM to assess data quality."""

    def __init__(self, name: str, config: Dict[str, Any]):
        env_config = get_llm_config()
        agent_cfg = get_agent_config()
        merged = {
            **config,
            "system_prompt": _SYSTEM_PROMPT,
            "cwd": agent_cfg["cwd"],
            "logs_dir": agent_cfg["logs_dir"],
            "timeout_seconds": agent_cfg["timeout_seconds"],
            **env_config,
        }
        super().__init__(name, merged)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.agent_available:
            return self._without_agent(data)
        raw_data = data.get("ingested_data", [])
        prompt = (
            "Assess the quality of the following records and return the "
            "required JSON.\n\n"
            f"Records: {json.dumps(raw_data, default=str)[:4000]}"
        )

        llm_input: Dict[str, Any] = {"prompt": prompt}
        if "_execution_id" in data:
            llm_input["_execution_id"] = data["_execution_id"]

        llm_result = await super().run(llm_input)
        parsed = _parse_quality(llm_result.get("text", ""))

        return {
            "ingested_data": raw_data,  # Pass through for downstream processors.
            "quality_score": parsed["quality_score"],
            "data_quality": parsed["data_quality"],
            "reasoning": parsed["reasoning"],
            "agent_job_id": llm_result.get("agent_job_id"),
            "event_count": llm_result.get("event_count", 0),
        }

    # Without a registered agent executor (pytest, the CLI outside a host app)
    # the step scores records by how many of their fields are filled, the rule
    # it used before it was LLM-backed, so the pipeline still routes on quality.
    def _without_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = data.get("ingested_data", [])
        score = self._field_fill_score(raw_data)
        return {
            "ingested_data": raw_data,
            "quality_score": score,
            "data_quality": self._describe(score),
            "reasoning": "scored by field completeness; no agent executor registered",
            "agent_job_id": None,
            "event_count": 0,
        }

    @staticmethod
    def _field_fill_score(data: Any) -> float:
        def record_score(record: Dict[str, Any]) -> float:
            if "quality_score" in record:
                return float(record["quality_score"])
            if not record:
                return 0.0
            return sum(1 for value in record.values() if value is not None) / len(record)

        if isinstance(data, dict):
            return record_score(data)
        if isinstance(data, list):
            scores = [record_score(r) for r in data if isinstance(r, dict)]
            return sum(scores) / len(scores) if scores else 0.0
        return 0.5

    @staticmethod
    def _describe(score: float) -> str:
        if score >= 0.9:
            return "Excellent"
        if score >= 0.7:
            return "Good"
        if score >= 0.5:
            return "Fair"
        return "Poor"
