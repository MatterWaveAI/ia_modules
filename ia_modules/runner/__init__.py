"""
Runner Entrypoint for IA Modules

The container story: one process, one pipeline, one exit code.
`ia-runner` loads a bundle pipeline file (YAML or JSON), runs it against
nexusql storage configured from the environment, checkpoints progress, and
resumes from the last checkpoint when retried with the same run id.

    ia-runner --pipeline chat_pipeline.yaml

Environment: `IA_RUN_ID` names the run (checkpoint thread); `IA_RUN_ACTOR`
names who triggered it -- the dispatcher sets it from the console session's
subject claim, and a scheduler-triggered run names its service identity
(default `svc:ia-runner`). Storage comes from `IA_MODULES_DB_URL` or the
`IA_MODULES_DB_HOST/_PORT/_USER/_PASSWORD/_NAME` parts.

Console script: `ia-runner` (see [project.scripts] in pyproject.toml).
The runner image and its release CI live in `docker/` and
`.github/workflows/release-image.yml`.
"""

from .main import (
    CLI_SPECS,
    EXIT_OK,
    EXIT_FAILED,
    EXIT_USAGE,
    RunnerUsageError,
    build_db_url_from_env,
    create_parser,
    detect_cli_inventory,
    load_pipeline_config,
    runner_main,
)

__all__ = [
    'CLI_SPECS',
    'EXIT_OK',
    'EXIT_FAILED',
    'EXIT_USAGE',
    'RunnerUsageError',
    'build_db_url_from_env',
    'create_parser',
    'detect_cli_inventory',
    'load_pipeline_config',
    'runner_main',
]
