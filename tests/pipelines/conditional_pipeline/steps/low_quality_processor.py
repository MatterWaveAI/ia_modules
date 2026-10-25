"""
Low Quality Processor Step — LLM-backed basic-cleanup processor.

Runs on the low-quality branch of the conditional pipeline. Asks a real CLI
agent to perform a conservative cleanup (trim whitespace, drop nulls, flag
suspect records) without doing deeper enrichment.
"""

from typing import Any, Dict
import json

from ia_modules.pipeline.llm_step import LLMStep
from ia_modules.pipeline.llm_config import get_agent_config, get_llm_config


_SYSTEM_PROMPT = (
    "You are a basic-cleanup data processing agent. The input data has been "
    "judged low quality, so perform a conservative pass only: trim whitespace, "
    "drop null fields, and flag any record that looks suspect. Do not enrich "
    "or transform beyond cleanup. Respond with a short summary of what you "
    "cleaned, then the cleaned records. Keep the full response under 200 words."
)


class LowQualityProcessorStep(LLMStep):
    """Agent step that does conservative cleanup on low-quality data."""

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
        quality_score = data.get("quality_score", 0)

        prompt = (
            "Perform basic cleanup on the following low-quality records and "
            "describe what you cleaned.\n\n"
            f"Quality score: {quality_score}\n"
            f"Records: {json.dumps(raw_data, default=str)[:4000]}"
        )

        llm_input: Dict[str, Any] = {"prompt": prompt}
        if "_execution_id" in data:
            llm_input["_execution_id"] = data["_execution_id"]

        llm_result = await super().run(llm_input)

        return {
            "processed_data": llm_result.get("text", ""),
            "processing_level": "basic",
            "quality_score": quality_score,
            "agent_job_id": llm_result.get("agent_job_id"),
            "event_count": llm_result.get("event_count", 0),
        }

    # Without a registered agent executor the step does the basic cleanup it
    # did before it was LLM-backed: null fields dropped, text trimmed.
    def _without_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = data.get("ingested_data", [])
        records = raw_data if isinstance(raw_data, list) else [raw_data]
        processed = [
            {k: v.strip() if isinstance(v, str) else v for k, v in r.items() if v is not None}
            if isinstance(r, dict) else r
            for r in records
        ]
        return {
            "processed_data": processed if isinstance(raw_data, list) else processed[0],
            "processing_level": "basic",
            "quality_score": data.get("quality_score", 0),
            "agent_job_id": None,
            "event_count": 0,
        }
