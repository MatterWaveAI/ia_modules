"""Code generator step using LLM."""
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class CodeGeneratorStep(Step):
    """Generate code using LLM."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 2000)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code based on task description."""
        llm_service = self.services.get('llm_provider')
        if not llm_service:
            raise RuntimeError("LLM service not registered")

        task = data.get("task", "")
        context = data.get("context", "")

        # Build code generation prompt
        prompt = self._build_prompt(task, context)

        self.logger.info(f"Generating code for task: {task[:50]}...")

        # Generate code
        response = await llm_service.generate_completion(
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        # Extract code from response
        code = self._extract_code(response.content)

        self.logger.info(f"Generated {len(code)} characters of code")

        data["generated_code"] = code
        data["raw_response"] = response.content
        data["llm_metadata"] = {
            "provider": response.provider.value,
            "model": response.model,
            "usage": response.usage,
            "timestamp": response.timestamp.isoformat()
        }

        return data

    def _build_prompt(self, task: str, context: str) -> str:
        """Build code generation prompt."""
        if context:
            prompt = f"""You are an expert Python developer. Generate clean, well-documented code for the following task.

Context (existing code):
```python
{context}
```

Task: {task}

Requirements:
- Write clean, readable Python code
- Include docstrings
- Follow PEP 8 style guidelines
- Add type hints
- Include error handling where appropriate

Respond with ONLY the code, wrapped in ```python code blocks.

Generated code:"""
        else:
            prompt = f"""You are an expert Python developer. Generate clean, well-documented code for the following task.

Task: {task}

Requirements:
- Write clean, readable Python code
- Include docstrings
- Follow PEP 8 style guidelines
- Add type hints
- Include error handling where appropriate

Respond with ONLY the code, wrapped in ```python code blocks.

Generated code:"""

        return prompt

    def _extract_code(self, response: str) -> str:
        """Extract code from LLM response."""
        # Look for code blocks
        if "```python" in response:
            # Extract from python code block
            parts = response.split("```python")
            if len(parts) > 1:
                code_part = parts[1].split("```")[0]
                return code_part.strip()

        if "```" in response:
            # Extract from generic code block
            parts = response.split("```")
            if len(parts) > 1:
                return parts[1].strip()

        # Return full response if no code blocks found
        return response.strip()
