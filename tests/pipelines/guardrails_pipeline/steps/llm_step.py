"""
Stand-in LLM step for the guardrails example.

It answers from a fixed template, so the example runs with no model or API
key and the guardrails are what you see. For a real model, point the step's
"module" in pipeline.json at ia_modules.pipeline.llm_step: that LLMStep sends
the prompt to a CLI agent (claude_code, opencode), reads its input from a
"prompt", "message", "text" or "input" field, and returns the reply as "text".
"""
from typing import Any, Dict

from ia_modules.pipeline.core import Step


class LLMStep(Step):
    """Return a placeholder reply built from the input field.

    Config:
        input_field: key of the user's text in the step input (default "user_input")
        output_field: key the reply is returned under (default "llm_response")
    """

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        input_field = self.config.get("input_field", "user_input")
        output_field = self.config.get("output_field", "llm_response")
        user_input = data.get(input_field, "")
        reply = (
            f"You asked: {user_input}\n\n"
            "This reply comes from the example's placeholder LLM step, so the "
            "guardrail steps around it can be tried without a model."
        )
        return {output_field: reply}
