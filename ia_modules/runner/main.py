"""
Runner CLI: run one pipeline from config, exit with the outcome.

Contract (the shape the Command Center's k8s Jobs are built around — see
`docs/runtime-ia-modules.md` in the agent-command-center repo):

Args:
    --pipeline PATH    Pipeline file (.yaml, .yml or .json) in the bundle
                       schema: name / execution / steps / flow / error_handling
    --input PATH       Optional JSON file with input data for the pipeline
    --working-dir DIR  Added to sys.path first, so a step's `module:` import
                       resolves (the directory holding the pipeline's steps/)
    --output PATH      Write the full result JSON here (default: stdout)
    --list-clis        Detect the six CLI agents on PATH (+ version output),
                       emit JSON and exit 0 (T-080)
    --version          Print the ia_modules version and exit 0 (the image
                       HEALTHCHECK uses this as its no-op probe)

Env:
    IA_RUN_ID          Run id for checkpointing. When set and a checkpoint
                       already exists for it, the run resumes from that
                       checkpoint instead of starting over — this is what a
                       retried k8s Job (backoffLimit) leans on. Unset, a
                       fresh id is generated and nothing can resume.
    IA_MODULES_DB_URL  Full nexusql database URL, e.g.
                       postgresql://user:pass@host:5432/db
    IA_MODULES_DB_HOST / _PORT / _USER / _PASSWORD / _NAME
                       Or the parts; they build the URL when _URL is unset.
                       No IA_MODULES_DB_* at all: the pipeline still runs,
                       but with a loud warning — nothing checkpoints and no
                       retry can resume.

Exit codes:
    0  pipeline completed. A waiting_for_human pause also exits 0: it is a
       controlled pause for an out-of-band approval, not a failure.
    1  the pipeline failed, or storage could not be initialized
    2  usage error: missing/unreadable pipeline or input file, bad YAML/JSON,
       or a pipeline without name/steps/flow.start_at
       (argparse also exits 2 on unknown flags, so every non-zero-but-not-1
       answer means "fix the invocation")
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ia_modules import __version__

logger = logging.getLogger("ia_modules.runner")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

# T-080: the six CLI agents the runner image can host (docs/a0c-harvest.md).
# Each tuple is (canonical name, display label, binary names in search order).
CLI_SPECS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("claude_code", "Claude Code", ("claude",)),
    ("opencode", "OpenCode", ("opencode",)),
    ("aider", "Aider", ("aider",)),
    ("codex", "Codex", ("codex",)),
    ("gemini", "Gemini", ("gemini",)),
    ("qwen_code", "Qwen", ("qwen", "qwen-agent")),
)

CLI_PROBE_TIMEOUT_SECONDS = 5.0

# Schema fields the engine reads directly. `execution` and `error_handling`
# ride along in the bundle schema (engine, timeout, on_step_failure); the
# engine currently applies timeout/retry per step config, not per pipeline.
_REQUIRED_FIELDS = ("name", "steps", "flow")


class RunnerUsageError(Exception):
    """A problem with the invocation itself — always exit code 2."""


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the runner"""
    parser = argparse.ArgumentParser(
        prog='ia-runner',
        description='Run ONE ia_modules pipeline from a YAML/JSON bundle file; '
                    'checkpoints in nexusql storage, resumes on retry via IA_RUN_ID'
    )
    parser.add_argument(
        '--pipeline',
        type=str,
        help='Path to the pipeline file (.yaml, .yml or .json)'
    )
    parser.add_argument(
        '--input',
        type=str,
        help='Path to a JSON file with input data for the pipeline'
    )
    parser.add_argument(
        '--working-dir',
        type=str,
        help='Directory to add to sys.path so step module imports resolve '
             '(the directory holding the pipeline\'s steps/)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Path to save the result JSON (default: print to stdout)'
    )
    parser.add_argument(
        '--list-clis',
        action='store_true',
        help='Detect the six CLI agents (binary on PATH + version output), emit JSON and exit'
    )
    parser.add_argument(
        '--version',
        action='store_true',
        help='Print the ia_modules version and exit'
    )
    return parser


def _probe_cli_version(binary_path: str, timeout: float = CLI_PROBE_TIMEOUT_SECONDS) -> Optional[str]:
    """Run `<binary> --version` and return the first non-empty output line, or None if it fails."""
    try:
        proc = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def detect_cli_inventory(
    *,
    which: Callable[[str], Optional[str]] = shutil.which,
    probe_version: Callable[[str], Optional[str]] = _probe_cli_version,
    specs: Sequence[Tuple[str, str, Tuple[str, ...]]] = CLI_SPECS,
) -> Dict[str, List[Dict[str, Any]]]:
    """Detect each of the six CLI agents (binary on PATH + version output) and return the inventory dict."""
    clis: List[Dict[str, Any]] = []
    for name, label, binaries in specs:
        resolved_binary = binaries[0]
        resolved_path: Optional[str] = None
        for candidate in binaries:
            found = which(candidate)
            if found:
                resolved_binary = candidate
                resolved_path = found
                break
        version: Optional[str] = None
        if resolved_path is not None:
            version = probe_version(resolved_path)
            if version is not None:
                version = version.strip() or None
        available = resolved_path is not None and version is not None
        clis.append(
            {
                "name": name,
                "label": label,
                "binary": resolved_binary,
                "available": available,
                "version": version if available else None,
                "path": resolved_path,
            }
        )
    return {"clis": clis}


def load_pipeline_config(path: str) -> Dict[str, Any]:
    """Load a pipeline file, YAML or JSON, into a config dict.

    Raises:
        RunnerUsageError: file missing, unparsable, or missing required fields
    """
    pipeline_path = Path(path)
    if not pipeline_path.exists():
        raise RunnerUsageError(f"Pipeline file not found: {pipeline_path}")

    suffix = pipeline_path.suffix.lower()
    try:
        if suffix in ('.yaml', '.yml'):
            import yaml
            with open(pipeline_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        elif suffix == '.json':
            with open(pipeline_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            raise RunnerUsageError(
                f"Unsupported pipeline file type '{suffix}': "
                f"{pipeline_path} must be .yaml, .yml or .json"
            )
    except RunnerUsageError:
        raise
    except Exception as e:
        raise RunnerUsageError(f"Cannot parse pipeline file {pipeline_path}: {e}")

    if not isinstance(config, dict):
        raise RunnerUsageError(
            f"Pipeline file {pipeline_path} must contain a mapping, "
            f"got {type(config).__name__}"
        )

    missing = [field for field in _REQUIRED_FIELDS if field not in config]
    if missing:
        raise RunnerUsageError(
            f"Pipeline {pipeline_path} is missing required field(s): "
            + ", ".join(missing)
        )

    flow = config.get('flow') or {}
    if not isinstance(flow, dict) or not flow.get('start_at'):
        raise RunnerUsageError(
            f"Pipeline {pipeline_path} needs a flow.start_at step id"
        )

    return config


def build_db_url_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """The nexusql database URL from IA_MODULES_DB_* env, or None.

    IA_MODULES_DB_URL wins when set; otherwise a URL is assembled from the
    _HOST/_PORT/_USER/_PASSWORD/_NAME parts (sane localhost defaults, the
    shape the k8s secret store mounts). No storage env at all returns None —
    the caller decides whether that is fatal or a warn-and-continue.
    """
    env = os.environ if env is None else env

    url = env.get("IA_MODULES_DB_URL")
    if url:
        return url

    if not env.get("IA_MODULES_DB_HOST") and not env.get("IA_MODULES_DB_NAME"):
        return None

    host = env.get("IA_MODULES_DB_HOST", "localhost")
    port = env.get("IA_MODULES_DB_PORT", "5432")
    user = env.get("IA_MODULES_DB_USER", "postgres")
    password = env.get("IA_MODULES_DB_PASSWORD", "")
    name = env.get("IA_MODULES_DB_NAME", "ia_modules")

    netloc = f"{user}:{password}@{host}:{port}" if password else f"{user}@{host}:{port}"
    return f"postgresql://{netloc}/{name}"


def _load_input_data(path: str) -> Dict[str, Any]:
    """Load the --input JSON file. Usage errors are exit code 2."""
    input_path = Path(path)
    if not input_path.exists():
        raise RunnerUsageError(f"Input file not found: {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise RunnerUsageError(f"Cannot parse input file {input_path}: {e}")
    if not isinstance(data, dict):
        raise RunnerUsageError(
            f"Input file {input_path} must contain a JSON object"
        )
    return data


async def _make_checkpointer(db_url: str):
    """Connect to nexusql storage and return a checkpointer over it.

    Applies ia_modules' own migrations (pipeline_checkpoints lives beside
    the platform's schema in the runner's database, per the platform rule:
    real Postgres via nexusql). Any failure here is a failed run — storage
    that cannot initialize is exactly the case a k8s Job should retry on,
    so it raises and the exit code reports it.
    """
    from nexusql import DatabaseManager

    from ia_modules.checkpoint import SQLCheckpointer
    from ia_modules.database import MIGRATIONS_DIR

    db = DatabaseManager(db_url)
    if not await db.initialize(app_migration_paths=[str(MIGRATIONS_DIR)]):
        raise RuntimeError(
            f"Storage initialization failed for {db_url.split('@')[-1]} "
            "(migrations did not apply)"
        )
    # Raises CheckpointSaveError when the table is still missing — that is
    # a storage problem, so it propagates as a failed run (exit 1).
    return SQLCheckpointer(db)


async def _run(args: argparse.Namespace) -> int:
    """Run the pipeline described by parsed args; returns the exit code."""
    from ia_modules.pipeline.core import ExecutionContext
    from ia_modules.pipeline.runner import create_pipeline_from_json
    from ia_modules.pipeline.services import ServiceRegistry

    config = load_pipeline_config(args.pipeline)

    input_data: Dict[str, Any] = {}
    if args.input:
        input_data = _load_input_data(args.input)

    # Step modules import relative to the pipeline's directory
    # (`module: steps`, like the fiber-apps pipelines do).
    if args.working_dir and args.working_dir not in sys.path:
        sys.path.insert(0, args.working_dir)

    # The run id is the whole resume story: same IA_RUN_ID on retry,
    # same checkpoint thread, pick up where the dead pod stopped.
    run_id = os.environ.get("IA_RUN_ID") or str(uuid.uuid4())
    if not os.environ.get("IA_RUN_ID"):
        logger.info("No IA_RUN_ID set, generated run id: %s", run_id)

    services = ServiceRegistry()
    db_url = build_db_url_from_env()
    if db_url:
        checkpointer = await _make_checkpointer(db_url)
        # create_pipeline_from_json picks the checkpointer up from services
        # and hands it to the Pipeline, which checkpoints after every step.
        services.register('checkpointer', checkpointer)
    else:
        logger.warning(
            "No storage configured (set IA_MODULES_DB_URL or "
            "IA_MODULES_DB_HOST/_USER/_PASSWORD/_NAME): this run will NOT "
            "checkpoint and a retry cannot resume"
        )
        checkpointer = None

    pipeline = create_pipeline_from_json(config, services, input_data=input_data)
    # The run's actor: the dispatcher sets IA_RUN_ACTOR from the console
    # session's subject claim; a scheduler-triggered run names its service
    # identity instead. Never a hardcoded person.
    actor = os.environ.get("IA_RUN_ACTOR") or "svc:ia-runner"

    # Resume when a checkpoint exists for this run id; start fresh otherwise.
    existing = await checkpointer.load_checkpoint(run_id) if checkpointer else None
    if existing:
        logger.info(
            "Run %s: resuming from checkpoint %s (step '%s', index %s)",
            run_id, existing.checkpoint_id, existing.step_name, existing.step_index,
        )
        result = await pipeline.resume(thread_id=run_id)
    else:
        logger.info("Run %s: fresh start (actor '%s')", run_id, actor)
        context = ExecutionContext(
            execution_id=run_id,
            pipeline_id=config.get('name'),
            user_id=actor,
        )
        result = await pipeline.run(input_data, context, thread_id=run_id)

    # Emit the full result: --output file, or stdout (logs go to stderr)
    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(payload)
        logger.info("Pipeline result saved to: %s", output_path)
    else:
        print(payload)

    if result.get('status') == 'waiting_for_human':
        logger.warning(
            "Run %s paused for human input at step '%s' (interaction %s) — "
            "exiting 0; the approval flow resumes the run out-of-band",
            run_id, result.get('waiting_step'), result.get('interaction_id'),
        )
    else:
        logger.info("Run %s completed successfully", run_id)
    return EXIT_OK


def runner_main(argv: Optional[list] = None) -> int:
    """Main runner entry point: exit code is the outcome."""
    logging.basicConfig(
        level=os.environ.get("IA_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    args = create_parser().parse_args(argv)

    if args.version:
        print(__version__)
        return EXIT_OK

    if args.list_clis:
        payload = json.dumps(detect_cli_inventory(), indent=2)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding='utf-8')
        else:
            print(payload)
        return EXIT_OK

    # Not parser-enforced so --version and --list-clis work with no other flags
    if not args.pipeline:
        print("Error: --pipeline is required", file=sys.stderr)
        return EXIT_USAGE

    try:
        return asyncio.run(_run(args))
    except RunnerUsageError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return EXIT_FAILED
    except Exception as e:
        print(f"Pipeline run failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return EXIT_FAILED


def main():
    """Entry point for console script"""
    sys.exit(runner_main())


if __name__ == '__main__':
    main()
