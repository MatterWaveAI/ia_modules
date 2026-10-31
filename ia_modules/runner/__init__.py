"""
Runner Entrypoint for IA Modules

The container story (T-003): one process, one pipeline, one exit code.
`ia-runner` loads a bundle pipeline file (YAML or JSON), runs it against
nexusql storage configured from the environment, checkpoints progress, and
resumes from the last checkpoint when retried with the same run id.

    ia-runner --pipeline chat_pipeline.yaml

Console script: `ia-runner` (see [project.scripts] in pyproject.toml).
The runner image and its release CI live in `docker/` and
`.github/workflows/release-image.yml`.
"""

from .main import (
    EXIT_OK,
    EXIT_FAILED,
    EXIT_USAGE,
    RunnerUsageError,
    build_db_url_from_env,
    create_parser,
    load_pipeline_config,
    runner_main,
)

__all__ = [
    'EXIT_OK',
    'EXIT_FAILED',
    'EXIT_USAGE',
    'RunnerUsageError',
    'build_db_url_from_env',
    'create_parser',
    'load_pipeline_config',
    'runner_main',
]
