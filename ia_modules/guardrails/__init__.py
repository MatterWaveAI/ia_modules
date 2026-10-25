"""
Guardrails for LLM Safety and Control

Provides programmable guardrails for controlling LLM inputs and outputs.
Inspired by NVIDIA NeMo Guardrails architecture.

Core Components:
- models: Rail models and configurations
- base: BaseGuardrail abstract class
- input_rails: Pre-processing safety checks
- output_rails: Post-processing validation
- engine: Guardrails orchestration engine

Example Usage:
    >>> from ia_modules.guardrails import GuardrailsEngine, GuardrailsConfig
    >>> from ia_modules.guardrails.input_rails import JailbreakDetectionRail
    >>>
    >>> config = GuardrailsConfig()
    >>> engine = GuardrailsEngine(config)
    >>> result = await engine.check_input("user message")
"""

from .models import (
    RailType,
    RailAction,
    RailResult,
    GuardrailConfig,
    GuardrailsConfig,
    GuardrailViolation,
)

from .base import BaseGuardrail
from .engine import GuardrailsEngine

__all__ = [
    "RailType",
    "RailAction",
    "RailResult",
    "GuardrailConfig",
    "GuardrailsConfig",
    "GuardrailViolation",
    "BaseGuardrail",
    "GuardrailsEngine",
]
