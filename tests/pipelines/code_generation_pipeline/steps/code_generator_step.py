"""Code generator step: an LLM writes the code, through a CLI agent."""
from typing import Any, Dict

from ia_modules.pipeline.llm_config import get_agent_config, get_llm_config
from ia_modules.pipeline.llm_step import LLMStep

_SYSTEM_PROMPT = (
    "You are an expert Python developer. Write clean, readable, documented code "
    "with type hints and error handling, following PEP 8. Respond with ONLY the "
    "code, wrapped in a ```python code block."
)


class CodeGeneratorStep(LLMStep):
    """Generate code for the task in the input.

    Config: temperature, max_tokens (passed to the agent). Output: generated_code,
    raw_response, llm_metadata.
    """

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
        task = data.get("task", "")
        context = data.get("context", "")
        if not self.agent_available:
            return self._without_agent(task)

        llm_input: Dict[str, Any] = {"prompt": self._build_prompt(task, context)}
        if "_execution_id" in data:
            llm_input["_execution_id"] = data["_execution_id"]
        llm_result = await super().run(llm_input)
        raw = llm_result.get("text", "")
        code = self._extract_code(raw)
        self.logger.info(f"Generated {len(code)} characters of code")
        return {
            "generated_code": code,
            "raw_response": raw,
            "llm_metadata": {
                "agent_job_id": llm_result.get("agent_job_id"),
                "event_count": llm_result.get("event_count", 0),
            },
        }

    # Without a registered agent executor (pytest, the bare CLI) the step emits a
    # stub with the task recorded in it, so the guardrail and writer steps still run.
    def _without_agent(self, task: str) -> Dict[str, Any]:
        summary = " ".join(task.split())[:120] or "the requested task"
        code = (
            f'"""{summary}"""\n\n\n'
            "def solution():\n"
            '    """Placeholder: no agent executor was registered when this ran."""\n'
            "    return None\n"
        )
        return {
            "generated_code": code,
            "raw_response": code,
            "llm_metadata": {"agent_job_id": None, "event_count": 0, "note": "stub; no agent executor"},
        }

    @staticmethod
    def _build_prompt(task: str, context: str) -> str:
        if context:
            return f"Context (existing code):\n```python\n{context}\n```\n\nTask: {task}"
        return f"Task: {task}"

    @staticmethod
    def _extract_code(response: str) -> str:
        """The code inside the first ```python (or ```) block, else the whole response."""
        if "```python" in response:
            return response.split("```python", 1)[1].split("```", 1)[0].strip()
        if "```" in response:
            return response.split("```", 2)[1].strip()
        return response.strip()
