"""
Structured output validation.

Validates agent outputs against Pydantic schemas with automatic retry.
"""

from typing import Type, Callable, Any, Dict, Optional
from pydantic import BaseModel, ValidationError
import logging


class StructuredOutputValidator:
    """
    Validate agent outputs against Pydantic schemas.

    Features:
    - Automatic retry on validation failure
    - Schema enforcement
    - Type safety
    - Detailed error messages

    Example:
        >>> from pydantic import BaseModel, Field
        >>>
        >>> class MyOutput(BaseModel):
        ...     name: str
        ...     value: int = Field(..., ge=0, le=100)
        >>>
        >>> validator = StructuredOutputValidator()
        >>>
        >>> # Validate output
        >>> output = '{"name": "test", "value": 42}'
        >>> validated = await validator.validate(output, MyOutput)
    """

    def __init__(self):
        """Initialize validator."""
        self.logger = logging.getLogger("StructuredOutputValidator")

    async def validate(self, output: Any, schema: Type[BaseModel]) -> BaseModel:
        """
        Validate output against schema.

        Args:
            output: Output to validate (JSON string or dict)
            schema: Pydantic model to validate against

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            if isinstance(output, str):
                # Try to extract JSON from text (handles markdown code blocks, etc.)
                output = self._extract_json(output)
                # Parse JSON string
                validated = schema.model_validate_json(output)
            elif isinstance(output, dict):
                # Validate dict
                validated = schema.model_validate(output)
            else:
                # Try to convert to dict
                validated = schema.model_validate(output)

            self.logger.info(f"Validation successful for {schema.__name__}")
            return validated

        except ValidationError as e:
            self.logger.error(f"Validation failed: {e}")
            raise

    async def validate_and_retry(
        self,
        output: Any,
        schema: Type[BaseModel],
        retry_func: Callable,
        max_retries: int = 3
    ) -> BaseModel:
        """
        Validate output and retry if invalid.

        Args:
            output: Initial output to validate
            schema: Pydantic model to validate against
            retry_func: Async function to call for retry (receives error_feedback)
            max_retries: Maximum retry attempts

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If validation fails after max retries

        Example:
            >>> async def generate_output(error_feedback=None):
            ...     # Generate output, using error_feedback to fix issues
            ...     return {"name": "test", "value": 42}
            >>>
            >>> result = await validator.validate_and_retry(
            ...     output='{"invalid": "data"}',
            ...     schema=MyOutput,
            ...     retry_func=generate_output,
            ...     max_retries=3
            ... )
        """
        last_error: Optional[ValidationError] = None
        for attempt in range(max_retries):
            try:
                # Try to validate
                validated = await self.validate(output, schema)
                return validated

            except ValidationError as e:
                last_error = e
                if attempt == max_retries - 1:
                    # Final attempt failed - re-raise original error
                    self.logger.error(f"Output validation failed after {max_retries} attempts")
                    raise

                # Retry with error feedback
                error_msg = self._format_error(e)
                self.logger.info(f"Validation failed (attempt {attempt + 1}/{max_retries}), retrying with feedback")

                output = await retry_func(error_feedback=error_msg)

        assert last_error is not None
        raise last_error

    def _format_error(self, error: ValidationError) -> str:
        """
        Format validation error for feedback.

        Args:
            error: Validation error

        Returns:
            Human-readable error message
        """
        errors = error.errors()

        messages = []
        for err in errors:
            loc = " -> ".join(str(x) for x in err["loc"])
            msg = err["msg"]
            messages.append(f"{loc}: {msg}")

        return "Validation errors:\n" + "\n".join(f"- {m}" for m in messages)

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text (handles markdown code blocks, etc.).

        Args:
            text: Text possibly containing JSON

        Returns:
            Extracted JSON string
        """
        import re

        # Try to find JSON in markdown code block
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1)

        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)

        # Return as-is if no JSON found
        return text

    def get_schema_description(self, schema: Type[BaseModel]) -> Dict[str, Any]:
        """
        Get human-readable schema description.

        Args:
            schema: Pydantic model

        Returns:
            Schema information
        """
        return {
            "name": schema.__name__,
            "description": schema.__doc__,
            "schema": schema.model_json_schema()
        }

    def to_json_schema(self, schema: Type[BaseModel]) -> Dict[str, Any]:
        """
        Convert Pydantic model to JSON schema.

        Args:
            schema: Pydantic model

        Returns:
            JSON schema dict
        """
        return schema.model_json_schema()
