"""
Intelligent Automation Modules

A modular framework for building intelligent automation solutions with advanced AI capabilities.

Core Modules:
- pipeline: Pipeline orchestration and execution
- agents: CLI agent execution (subprocess, A2A) and graph orchestration
- tools: Advanced tool calling with planning and execution
- memory: Conversation memory with pluggable backends
- guardrails: LLM safety and control (input/output rails, jailbreak detection)
- telemetry: OpenTelemetry integration, metrics, tracing
- reliability: Circuit breaker, SLO tracking, cost tracking
- plugins: Plugin system with built-in plugins
- cli: CLI interface
- scheduler: Task scheduling
- checkpoint: Pipeline checkpointing
- database: Database adapters (NexusQL, SQLAlchemy)
- validation: Data validation
- utils: Utility functions
"""

__version__ = "0.3.1"

# Modules are available but not auto-imported to avoid circular dependencies
# Import them explicitly as needed:
#   from ia_modules import pipeline
#   from ia_modules.pipeline import Step, Pipeline

__all__ = [
    # Core modules
    'pipeline',
    'agents',
    'tools',
    'memory',
    'guardrails',
    'telemetry',
    'reliability',
    'plugins',
    'cli',
    'scheduler',
    'checkpoint',
    'database',
    'validation',
    'utils',
]
