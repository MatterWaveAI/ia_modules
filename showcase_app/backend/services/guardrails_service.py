"""Guardrails service using ACTUAL ia_modules guardrails library"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from ia_modules.guardrails import GuardrailsEngine, GuardrailConfig, RailType, RailAction
from ia_modules.guardrails.input_rails import JailbreakDetectionRail, ToxicityDetectionRail, PIIDetectionRail
from ia_modules.guardrails.output_rails.basic_filters import ToxicOutputFilterRail, DisclaimerRail, LengthLimitRail

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class GuardrailsService:
    """Service for testing and demonstrating ia_modules guardrails"""

    # Registry of all available rails with metadata
    RAIL_CATALOG = {
        "input": {
            "jailbreak": {
                "name": "Jailbreak Detection",
                "class": "JailbreakDetectionRail",
                "description": "Detects prompt injection and jailbreak attempts using pattern matching",
                "category": "input",
            },
            "toxicity": {
                "name": "Toxicity Detection",
                "class": "ToxicityDetectionRail",
                "description": "Detects toxic, harmful, or inappropriate content using keyword analysis",
                "category": "input",
            },
            "pii": {
                "name": "PII Detection",
                "class": "PIIDetectionRail",
                "description": "Detects and redacts emails, phone numbers, SSNs, credit cards, and IP addresses",
                "category": "input",
            },
        },
        "output": {
            "toxic_filter": {
                "name": "Toxic Output Filter",
                "class": "ToxicOutputFilterRail",
                "description": "Blocks LLM outputs containing toxic or harmful content",
                "category": "output",
            },
            "disclaimer": {
                "name": "Disclaimer Rail",
                "class": "DisclaimerRail",
                "description": "Adds disclaimers to medical, legal, or financial advice responses",
                "category": "output",
            },
            "length_limit": {
                "name": "Length Limit",
                "class": "LengthLimitRail",
                "description": "Enforces maximum output length and truncates if exceeded",
                "category": "output",
            },
        },
        "dialog": {
            "context_length": {
                "name": "Context Length",
                "class": "ContextLengthRail",
                "description": "Warns when conversation exceeds turn or token limits",
                "category": "dialog",
            },
            "topic_adherence": {
                "name": "Topic Adherence",
                "class": "TopicAdherenceRail",
                "description": "Ensures conversation stays on allowed topics",
                "category": "dialog",
            },
            "conversation_flow": {
                "name": "Conversation Flow",
                "class": "ConversationFlowRail",
                "description": "Detects repetitive patterns or conversation loops",
                "category": "dialog",
            },
        },
        "retrieval": {
            "source_validation": {
                "name": "Source Validation",
                "class": "SourceValidationRail",
                "description": "Validates retrieved documents come from trusted sources",
                "category": "retrieval",
            },
            "relevance_filter": {
                "name": "Relevance Filter",
                "class": "RelevanceFilterRail",
                "description": "Filters documents below minimum relevance threshold",
                "category": "retrieval",
            },
            "content_filter": {
                "name": "Content Filter",
                "class": "RetrievedContentFilterRail",
                "description": "Filters harmful or inappropriate content in retrieved documents",
                "category": "retrieval",
            },
        },
        "execution": {
            "tool_validation": {
                "name": "Tool Validation",
                "class": "ToolValidationRail",
                "description": "Validates tool/function calls against allowed/blocked lists",
                "category": "execution",
            },
            "code_safety": {
                "name": "Code Execution Safety",
                "class": "CodeExecutionSafetyRail",
                "description": "Detects dangerous operations in code (eval, os.system, etc.)",
                "category": "execution",
            },
            "parameter_validation": {
                "name": "Parameter Validation",
                "class": "ParameterValidationRail",
                "description": "Validates function parameters against type/range schemas",
                "category": "execution",
            },
            "resource_limit": {
                "name": "Resource Limit",
                "class": "ResourceLimitRail",
                "description": "Enforces execution time, memory, and iteration limits",
                "category": "execution",
            },
        },
    }

    def __init__(self):
        logger.info("Initializing GuardrailsService with ia_modules guardrails...")

    def list_available_rails(self) -> Dict[str, Any]:
        """List all available rail types and their metadata."""
        return self.RAIL_CATALOG

    async def test_input_rail(self, text: str, rail_type: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Test a specific input rail against provided text.

        Args:
            text: Text to check
            rail_type: One of 'jailbreak', 'toxicity', 'pii'
            options: Optional rail-specific options (e.g., redact for PII)

        Returns:
            Rail execution results
        """
        options = options or {}
        engine = GuardrailsEngine()

        config = GuardrailConfig(name=rail_type, type=RailType.INPUT)

        if rail_type == "jailbreak":
            rail = JailbreakDetectionRail(config)
        elif rail_type == "toxicity":
            rail = ToxicityDetectionRail(config)
        elif rail_type == "pii":
            redact = options.get("redact", True)
            rail = PIIDetectionRail(config, redact=redact)
        else:
            return {"error": f"Unknown input rail type: {rail_type}"}

        engine.add_rail(rail)
        result = await engine.check_input(text)

        return self._serialize_result(result)

    async def test_output_rail(self, text: str, rail_type: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Test a specific output rail against provided text.

        Args:
            text: Text to check
            rail_type: One of 'toxic_filter', 'disclaimer', 'length_limit'
            options: Optional rail-specific options (e.g., max_length)

        Returns:
            Rail execution results
        """
        options = options or {}
        engine = GuardrailsEngine()

        config = GuardrailConfig(name=rail_type, type=RailType.OUTPUT)

        if rail_type == "toxic_filter":
            rail = ToxicOutputFilterRail(config)
        elif rail_type == "disclaimer":
            disclaimer_text = options.get("disclaimer_text")
            rail = DisclaimerRail(config, disclaimer_text=disclaimer_text)
        elif rail_type == "length_limit":
            max_length = options.get("max_length", 500)
            rail = LengthLimitRail(config, max_length=max_length)
        else:
            return {"error": f"Unknown output rail type: {rail_type}"}

        engine.add_rail(rail)
        result = await engine.check_output(text)

        return self._serialize_result(result)

    async def run_guardrails_pipeline(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a full guardrails pipeline with multiple rails.

        Args:
            text: Text to process
            config: Pipeline configuration with rails to enable:
                {
                    "input_rails": ["jailbreak", "toxicity", "pii"],
                    "output_rails": ["toxic_filter", "disclaimer", "length_limit"],
                    "options": {
                        "pii_redact": true,
                        "max_length": 500
                    }
                }

        Returns:
            Step-by-step execution results
        """
        options = config.get("options", {})
        engine = GuardrailsEngine()
        steps = []

        # Add input rails
        input_rail_types = config.get("input_rails", [])
        for rail_type in input_rail_types:
            rail_config = GuardrailConfig(name=rail_type, type=RailType.INPUT)
            if rail_type == "jailbreak":
                engine.add_rail(JailbreakDetectionRail(rail_config))
            elif rail_type == "toxicity":
                engine.add_rail(ToxicityDetectionRail(rail_config))
            elif rail_type == "pii":
                engine.add_rail(PIIDetectionRail(rail_config, redact=options.get("pii_redact", True)))

        # Add output rails
        output_rail_types = config.get("output_rails", [])
        for rail_type in output_rail_types:
            rail_config = GuardrailConfig(name=rail_type, type=RailType.OUTPUT)
            if rail_type == "toxic_filter":
                engine.add_rail(ToxicOutputFilterRail(rail_config))
            elif rail_type == "disclaimer":
                engine.add_rail(DisclaimerRail(rail_config, disclaimer_text=options.get("disclaimer_text")))
            elif rail_type == "length_limit":
                engine.add_rail(LengthLimitRail(rail_config, max_length=options.get("max_length", 500)))

        # Run input rails
        current_text = text
        if input_rail_types:
            input_result = await engine.check_input(current_text)
            input_step = {
                "step": "input_rails",
                "rails_checked": input_rail_types,
                "action": input_result["action"].value,
                "triggered_count": input_result["triggered_count"],
                "results": self._serialize_rail_results(input_result.get("results", [])),
            }

            if input_result["action"] == RailAction.BLOCK:
                input_step["blocked"] = True
                input_step["reason"] = input_result.get("reason", "Blocked by input rails")
                steps.append(input_step)
                return {
                    "original_text": text,
                    "final_text": None,
                    "overall_action": "block",
                    "blocked": True,
                    "blocked_at": "input_rails",
                    "steps": steps,
                }

            if input_result["action"] == RailAction.MODIFY:
                current_text = input_result["content"]
                input_step["modified_text"] = current_text

            steps.append(input_step)

        # Run output rails (simulating LLM output = current_text for demo purposes)
        if output_rail_types:
            output_result = await engine.check_output(current_text)
            output_step = {
                "step": "output_rails",
                "rails_checked": output_rail_types,
                "action": output_result["action"].value,
                "triggered_count": output_result["triggered_count"],
                "results": self._serialize_rail_results(output_result.get("results", [])),
            }

            if output_result["action"] == RailAction.BLOCK:
                output_step["blocked"] = True
                output_step["reason"] = output_result.get("reason", "Blocked by output rails")
                steps.append(output_step)
                return {
                    "original_text": text,
                    "final_text": None,
                    "overall_action": "block",
                    "blocked": True,
                    "blocked_at": "output_rails",
                    "steps": steps,
                }

            if output_result["action"] == RailAction.MODIFY:
                current_text = output_result["content"]
                output_step["modified_text"] = current_text

            steps.append(output_step)

        # Get engine statistics
        stats = engine.get_statistics()

        return {
            "original_text": text,
            "final_text": current_text,
            "overall_action": "allow" if current_text == text else "modify",
            "blocked": False,
            "steps": steps,
            "engine_stats": {
                "total_rails": stats["total_rails"],
                "by_type": {
                    k: {"count": v["count"], "enabled": v["enabled"]}
                    for k, v in stats["by_type"].items()
                    if v["count"] > 0
                }
            },
        }

    def _serialize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize engine execution result to JSON-safe dict."""
        serialized = {
            "action": result["action"].value,
            "content": result["content"],
            "triggered_count": result.get("triggered_count", 0),
            "results": self._serialize_rail_results(result.get("results", [])),
        }
        if result.get("reason"):
            serialized["reason"] = result["reason"]
        if result.get("blocked_by"):
            serialized["blocked_by"] = result["blocked_by"]
        return serialized

    def _serialize_rail_results(self, results) -> List[Dict[str, Any]]:
        """Serialize individual rail results."""
        serialized = []
        for r in results:
            item = {
                "rail_id": r.rail_id,
                "rail_type": r.rail_type.value,
                "action": r.action.value,
                "triggered": r.triggered,
                "confidence": r.confidence,
            }
            if r.reason:
                item["reason"] = r.reason
            if r.modified_content is not None:
                item["modified_content"] = r.modified_content
            if r.metadata:
                # Filter metadata to JSON-serializable values
                item["metadata"] = {
                    k: v for k, v in r.metadata.items()
                    if isinstance(v, (str, int, float, bool, list, dict, type(None)))
                }
            serialized.append(item)
        return serialized
