"""
Configuration loader for guardrails from YAML files.

Allows declarative configuration of guardrails pipelines.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
from .models import GuardrailConfig, GuardrailsConfig, RailType
from .engine import GuardrailsEngine
from .base import BaseGuardrail

# Import all rail implementations
from .input_rails.jailbreak_detection import JailbreakDetectionRail
from .input_rails.toxicity_detection import ToxicityDetectionRail
from .input_rails.pii_detection import PIIDetectionRail

from .output_rails.basic_filters import (
    ToxicOutputFilterRail,
    DisclaimerRail,
    LengthLimitRail
)

from .dialog_rails.basic_dialog import (
    ContextLengthRail,
    TopicAdherenceRail,
    ConversationFlowRail
)

from .retrieval_rails.basic_retrieval import (
    SourceValidationRail,
    RelevanceFilterRail,
    RetrievedContentFilterRail
)

from .execution_rails.basic_execution import (
    ToolValidationRail,
    CodeExecutionSafetyRail,
    ParameterValidationRail,
    ResourceLimitRail
)


# Registry of available rail classes
RAIL_REGISTRY = {
    # Input rails
    "JailbreakDetectionRail": JailbreakDetectionRail,
    "ToxicityDetectionRail": ToxicityDetectionRail,
    "PIIDetectionRail": PIIDetectionRail,

    # Output rails
    "ToxicOutputFilterRail": ToxicOutputFilterRail,
    "DisclaimerRail": DisclaimerRail,
    "LengthLimitRail": LengthLimitRail,

    # Dialog rails
    "ContextLengthRail": ContextLengthRail,
    "TopicAdherenceRail": TopicAdherenceRail,
    "ConversationFlowRail": ConversationFlowRail,

    # Retrieval rails
    "SourceValidationRail": SourceValidationRail,
    "RelevanceFilterRail": RelevanceFilterRail,
    "RetrievedContentFilterRail": RetrievedContentFilterRail,

    # Execution rails
    "ToolValidationRail": ToolValidationRail,
    "CodeExecutionSafetyRail": CodeExecutionSafetyRail,
    "ParameterValidationRail": ParameterValidationRail,
    "ResourceLimitRail": ResourceLimitRail,
}


class ConfigLoader:
    """Loads guardrails configuration from YAML/JSON files."""

    @staticmethod
    def load_from_dict(config_dict: Dict[str, Any]) -> GuardrailsEngine:
        """
        Load guardrails engine from configuration dictionary.

        Args:
            config_dict: Configuration dictionary with structure:
                {
                    "guardrails_config": {...},  # Optional engine config
                    "rails": [
                        {
                            "class": "JailbreakDetectionRail",
                            "config": {
                                "name": "jailbreak",
                                "type": "input",
                                "enabled": true
                            },
                            "params": {...}  # Rail-specific params
                        },
                        ...
                    ]
                }

        Returns:
            Configured GuardrailsEngine instance
        """
        # Create engine config
        engine_config_dict = config_dict.get("guardrails_config", {})
        engine_config = GuardrailsConfig(**engine_config_dict) if engine_config_dict else None

        # Create engine
        engine = GuardrailsEngine(config=engine_config)

        # Load rails
        rails_config = config_dict.get("rails", [])
        for rail_spec in rails_config:
            rail = ConfigLoader._create_rail(rail_spec)
            if rail:
                engine.add_rail(rail)

        return engine

    @staticmethod
    def _create_rail(rail_spec: Dict[str, Any]) -> Optional[BaseGuardrail]:
        """
        Create a guardrail instance from specification.

        Args:
            rail_spec: Rail specification dictionary

        Returns:
            Guardrail instance or None if creation fails
        """
        rail_class_name = rail_spec.get("class")
        if not rail_class_name or rail_class_name not in RAIL_REGISTRY:
            print(f"Warning: Unknown rail class '{rail_class_name}', skipping")
            return None

        # Get rail class
        rail_class = RAIL_REGISTRY[rail_class_name]

        # Create config
        config_dict = rail_spec.get("config", {})

        # Convert type string to enum if needed
        if "type" in config_dict and isinstance(config_dict["type"], str):
            config_dict["type"] = RailType(config_dict["type"])

        config = GuardrailConfig(**config_dict)

        # Get rail-specific parameters
        params = rail_spec.get("params", {})

        # Create rail instance
        try:
            rail = rail_class(config, **params)
            return rail
        except Exception as e:
            print(f"Warning: Failed to create rail {rail_class_name}: {e}")
            return None

    @staticmethod
    def load_from_json(file_path: str) -> GuardrailsEngine:
        """
        Load guardrails engine from JSON file.

        Args:
            file_path: Path to JSON configuration file

        Returns:
            Configured GuardrailsEngine instance
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)

        return ConfigLoader.load_from_dict(config_dict)

    @staticmethod
    def load_from_yaml(file_path: str) -> GuardrailsEngine:
        """
        Load guardrails engine from YAML file.

        Args:
            file_path: Path to YAML configuration file

        Returns:
            Configured GuardrailsEngine instance
        """
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML configuration. "
                "Install it with: pip install pyyaml"
            )

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)

        return ConfigLoader.load_from_dict(config_dict)

    @staticmethod
    def save_to_dict(engine: GuardrailsEngine) -> Dict[str, Any]:
        """
        Export engine configuration to dictionary.

        Args:
            engine: GuardrailsEngine instance

        Returns:
            Configuration dictionary
        """
        config_dict = {
            "guardrails_config": engine.config.model_dump() if engine.config else {},
            "rails": []
        }

        # Export all rails
        for rail_type, rails in engine.rails.items():
            for rail in rails:
                rail_class_name = rail.__class__.__name__

                rail_spec = {
                    "class": rail_class_name,
                    "config": {
                        "name": rail.config.name,
                        "type": rail.config.type.value,
                        "enabled": rail.config.enabled,
                        "priority": rail.config.priority
                    },
                    "params": {}  # Note: Cannot automatically extract params
                }

                config_dict["rails"].append(rail_spec)

        return config_dict

    @staticmethod
    def save_to_json(engine: GuardrailsEngine, file_path: str) -> None:
        """
        Save engine configuration to JSON file.

        Args:
            engine: GuardrailsEngine instance
            file_path: Output file path
        """
        config_dict = ConfigLoader.save_to_dict(engine)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)

    @staticmethod
    def save_to_yaml(engine: GuardrailsEngine, file_path: str) -> None:
        """
        Save engine configuration to YAML file.

        Args:
            engine: GuardrailsEngine instance
            file_path: Output file path
        """
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML configuration. "
                "Install it with: pip install pyyaml"
            )

        config_dict = ConfigLoader.save_to_dict(engine)

        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
