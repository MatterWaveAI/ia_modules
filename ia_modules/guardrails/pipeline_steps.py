"""
Pipeline Step wrappers for guardrails.

Allows guardrails to be used as steps in ia_modules pipelines.
"""
from typing import Dict, Any
from ia_modules.pipeline.core import Step
from .engine import GuardrailsEngine
from .models import GuardrailConfig, RailType, RailAction
from .config_loader import ConfigLoader


class GuardrailStep(Step):
    """
    Generic guardrail step for pipelines.

    Can be configured to run any rail type (input, output, dialog, retrieval, execution).
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize guardrail step.

        Config format:
        {
            "rail_type": "input",  # input|output|dialog|retrieval|execution
            "rails_config": {...},  # GuardrailsEngine configuration
            "fail_on_block": true,  # Raise error if blocked (default: true)
            "content_field": "content",  # Field in data to check (default: "content")
            "context_fields": ["metadata"],  # Fields to pass as context
            "output_field": "guardrails_result"  # Where to store result
        }
        """
        super().__init__(name, config)

        # Guardrail configuration
        self.rail_type = RailType(config.get("rail_type", "input"))
        self.fail_on_block = config.get("fail_on_block", True)
        self.content_field = config.get("content_field", "content")
        self.context_fields = config.get("context_fields", [])
        self.output_field = config.get("output_field", "guardrails_result")

        # Load rails configuration
        rails_config = config.get("rails_config")
        if rails_config:
            if isinstance(rails_config, str):
                # Load from file
                self.engine = ConfigLoader.load_from_json(rails_config)
            elif isinstance(rails_config, dict):
                # Load from dict
                self.engine = ConfigLoader.load_from_dict(rails_config)
            else:
                raise ValueError("rails_config must be a file path or configuration dict")
        else:
            # Create empty engine
            self.engine = GuardrailsEngine()

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute guardrails on the data.

        Args:
            data: Pipeline data containing content to check

        Returns:
            Modified data with guardrails result

        Raises:
            ValueError: If content is blocked and fail_on_block=True
        """
        # Extract content to check
        content = data.get(self.content_field)
        if content is None:
            self.logger.warning(f"No content found in field '{self.content_field}'")
            return data

        # Build context from specified fields
        context = {}
        for field in self.context_fields:
            if field in data:
                context[field] = data[field]

        # Execute appropriate rail type
        if self.rail_type == RailType.INPUT:
            result = await self.engine.check_input(content, context=context)
        elif self.rail_type == RailType.OUTPUT:
            result = await self.engine.check_output(content, context=context)
        elif self.rail_type == RailType.DIALOG:
            result = await self.engine.check_dialog(content, context=context)
        elif self.rail_type == RailType.RETRIEVAL:
            result = await self.engine.check_retrieval(content, context=context)
        elif self.rail_type == RailType.EXECUTION:
            result = await self.engine.check_execution(content, context=context)
        else:
            raise ValueError(f"Unknown rail type: {self.rail_type}")

        # Store result
        data[self.output_field] = result

        # Handle blocking
        if result["action"] == RailAction.BLOCK:
            if self.fail_on_block:
                raise ValueError(
                    f"Content blocked by guardrails: {result.get('reason', 'No reason provided')}"
                )
            else:
                self.logger.warning(f"Content blocked: {result.get('reason')}")

        # Update content if modified
        if result["action"] == RailAction.MODIFY:
            data[self.content_field] = result["content"]
            self.logger.info("Content modified by guardrails")

        # Log warnings
        if result.get("triggered_count", 0) > 0:
            self.logger.info(
                f"Guardrails triggered: {result['triggered_count']}/{len(result.get('results', []))} rails"
            )

        return data


class InputGuardrailStep(Step):
    """Pre-configured input guardrails step."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

        # Load or create engine
        rails_config = config.get("rails_config")
        if rails_config:
            if isinstance(rails_config, str):
                self.engine = ConfigLoader.load_from_json(rails_config)
            elif isinstance(rails_config, dict):
                self.engine = ConfigLoader.load_from_dict(rails_config)
        else:
            # Create default input rails
            from .input_rails import JailbreakDetectionRail, ToxicityDetectionRail, PIIDetectionRail
            self.engine = GuardrailsEngine()
            self.engine.add_rails([
                JailbreakDetectionRail(GuardrailConfig(name="jailbreak", type=RailType.INPUT)),
                ToxicityDetectionRail(GuardrailConfig(name="toxicity", type=RailType.INPUT)),
                PIIDetectionRail(
                    GuardrailConfig(name="pii", type=RailType.INPUT),
                    redact=config.get("redact_pii", True)
                )
            ])

        self.content_field = config.get("content_field", "user_input")
        self.fail_on_block = config.get("fail_on_block", True)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check input with guardrails."""
        content = data.get(self.content_field, "")

        result = await self.engine.check_input(content)

        # Store result
        data["input_guardrails_result"] = result

        if result["action"] == RailAction.BLOCK:
            if self.fail_on_block:
                raise ValueError(f"Input blocked: {result.get('reason')}")

        # Update content if modified (e.g., PII redacted)
        if result["action"] == RailAction.MODIFY:
            data[self.content_field] = result["content"]

        return data


class OutputGuardrailStep(Step):
    """Pre-configured output guardrails step."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

        # Load or create engine
        rails_config = config.get("rails_config")
        if rails_config:
            if isinstance(rails_config, str):
                self.engine = ConfigLoader.load_from_json(rails_config)
            elif isinstance(rails_config, dict):
                self.engine = ConfigLoader.load_from_dict(rails_config)
        else:
            # Create default output rails
            from .output_rails import ToxicOutputFilterRail, DisclaimerRail, LengthLimitRail
            self.engine = GuardrailsEngine()
            self.engine.add_rails([
                ToxicOutputFilterRail(GuardrailConfig(name="toxic_output", type=RailType.OUTPUT)),
                DisclaimerRail(GuardrailConfig(name="disclaimer", type=RailType.OUTPUT)),
                LengthLimitRail(
                    GuardrailConfig(name="length", type=RailType.OUTPUT),
                    max_length=config.get("max_length", 500)
                )
            ])

        self.content_field = config.get("content_field", "llm_response")
        self.fail_on_block = config.get("fail_on_block", True)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check output with guardrails."""
        content = data.get(self.content_field, "")

        result = await self.engine.check_output(content)

        # Store result
        data["output_guardrails_result"] = result

        if result["action"] == RailAction.BLOCK:
            if self.fail_on_block:
                raise ValueError(f"Output blocked: {result.get('reason')}")

        # Update content if modified (e.g., disclaimer added)
        if result["action"] == RailAction.MODIFY:
            data[self.content_field] = result["content"]

        return data


class RetrievalGuardrailStep(Step):
    """Pre-configured retrieval guardrails step for RAG pipelines."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

        # Load or create engine
        rails_config = config.get("rails_config")
        if rails_config:
            if isinstance(rails_config, str):
                self.engine = ConfigLoader.load_from_json(rails_config)
            elif isinstance(rails_config, dict):
                self.engine = ConfigLoader.load_from_dict(rails_config)
        else:
            # Create default retrieval rails
            from .retrieval_rails import SourceValidationRail, RelevanceFilterRail
            self.engine = GuardrailsEngine()

            allowed_sources = config.get("allowed_sources", ["*.edu", "*.gov", "wikipedia.org"])
            min_score = config.get("min_relevance_score", 0.7)

            self.engine.add_rails([
                SourceValidationRail(
                    GuardrailConfig(name="source", type=RailType.RETRIEVAL),
                    allowed_sources=allowed_sources
                ),
                RelevanceFilterRail(
                    GuardrailConfig(name="relevance", type=RailType.RETRIEVAL),
                    min_score=min_score
                )
            ])

        self.documents_field = config.get("documents_field", "retrieved_documents")
        self.fail_on_block = config.get("fail_on_block", False)  # Usually don't fail, just filter

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter retrieved documents with guardrails."""
        documents = data.get(self.documents_field, [])

        if not documents:
            return data

        result = await self.engine.check_retrieval(documents)

        # Store result
        data["retrieval_guardrails_result"] = result

        # Update documents if filtered
        if result["action"] in [RailAction.MODIFY, RailAction.ALLOW]:
            data[self.documents_field] = result["content"]
        elif result["action"] == RailAction.BLOCK and self.fail_on_block:
            raise ValueError(f"All documents blocked: {result.get('reason')}")

        return data


class ExecutionGuardrailStep(Step):
    """Pre-configured execution guardrails step for tool/code execution."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

        # Load or create engine
        rails_config = config.get("rails_config")
        if rails_config:
            if isinstance(rails_config, str):
                self.engine = ConfigLoader.load_from_json(rails_config)
            elif isinstance(rails_config, dict):
                self.engine = ConfigLoader.load_from_dict(rails_config)
        else:
            # Create default execution rails
            from .execution_rails import ToolValidationRail, CodeExecutionSafetyRail
            self.engine = GuardrailsEngine()

            allowed_tools = config.get("allowed_tools")
            blocked_tools = config.get("blocked_tools", [])

            rails = []
            if allowed_tools or blocked_tools:
                rails.append(ToolValidationRail(
                    GuardrailConfig(name="tool", type=RailType.EXECUTION),
                    allowed_tools=allowed_tools,
                    blocked_tools=blocked_tools
                ))

            rails.append(CodeExecutionSafetyRail(  # type: ignore[arg-type]
                GuardrailConfig(name="code", type=RailType.EXECUTION),
                allow_file_read=config.get("allow_file_read", True),
                allow_network=config.get("allow_network", False)
            ))

            self.engine.add_rails(rails)  # type: ignore[arg-type]

        self.code_field = config.get("code_field", "code")
        self.tool_field = config.get("tool_field", "tool_name")
        self.fail_on_block = config.get("fail_on_block", True)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate code/tool execution with guardrails."""
        # Check for code or tool execution
        code = data.get(self.code_field)
        tool_name = data.get(self.tool_field)

        content = code or tool_name
        if not content:
            return data

        # Build context
        context = {}
        if tool_name:
            context["tool_name"] = tool_name

        result = await self.engine.check_execution(content, context=context)

        # Store result
        data["execution_guardrails_result"] = result

        if result["action"] == RailAction.BLOCK and self.fail_on_block:
            raise ValueError(f"Execution blocked: {result.get('reason')}")

        return data
