"""SubprocessExecutor — runs CLI agents as local subprocesses.

Spawns `claude` or `opencode` CLI directly and streams NDJSON events.
No A2A server, no HTTP, no external dependencies beyond the CLI binaries.

Supports two modes:
1. Bridge mode (default): spawns `node run_agent.mjs --stdin`
   Requires: Node.js + bridge scripts directory
2. Direct mode (fallback): spawns `claude` or `opencode` CLI directly
   Requires: CLI binary on PATH
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from .executor import (
    AgentConfig, AgentEvent, CLIType, EventType, normalize_event,
)

logger = logging.getLogger(__name__)


def _find_executable(name: str) -> Optional[str]:
    return shutil.which(name)


def _write_opencode_json(
    config_dir: str,
    provider: str,
    api_key: str,
    model: Optional[str] = None,
):
    """Write opencode.json into an isolated per-agent config dir.

    ``config_dir`` is an ``XDG_CONFIG_HOME``-shaped path — the caller
    creates a per-job directory (under ``logs/<job_id>/config``) and
    passes it in. We write ``opencode/opencode.json`` inside it and
    point ``XDG_CONFIG_HOME`` at ``config_dir`` when spawning opencode
    so the CLI picks up the provider/api-key without us ever writing
    into the user's target working directory.

    Historical note: earlier versions wrote ``opencode.json`` directly
    into the user's ``cwd``, which would leak an ``OPENCODE_API_KEY``
    into whatever repo the demo was run against if the user forgot to
    clean up (or accidentally committed the file). That is the bug
    this refactor closes — the config file now lives in a per-run
    directory the caller controls and tears down after the agent exits.
    """
    cfg_root = Path(config_dir) / "opencode"
    # mode=0o700 so the per-agent opencode dir is owner-only on POSIX.
    # Windows ignores the mode bits. The API key file inside is 0o600,
    # but an ancestor world-listable dir still lets other local users
    # enumerate job ids and pipeline metadata. ([26])
    cfg_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    oc_path = cfg_root / "opencode.json"

    oc_config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            provider: {
                "options": {"apiKey": api_key},
            },
        },
    }
    if model:
        m = model.strip()
        if not m.startswith(f"{provider}/"):
            m = f"{provider}/{m}"
        oc_config["provider"][provider]["models"] = {model: {"name": model}}  # type: ignore[index]
        oc_config["model"] = m

    # Write with mode 0o600 where the platform honours it — on POSIX
    # this keeps the api key out of any other user's view. We write
    # via os.open(O_CREAT|O_TRUNC|O_WRONLY, 0o600) so the mode bits
    # are applied at create time, not after a race.
    fd = os.open(
        str(oc_path),
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
        0o600,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(oc_config, f, indent=2)

    logger.info(
        "Wrote opencode.json for provider=%s at %s (isolated from cwd)",
        provider,
        oc_path,
    )

    def cleanup():
        try:
            oc_path.unlink(missing_ok=True)
        except OSError:
            pass

    return cleanup


class SubprocessExecutor:
    """Runs CLI agents as local subprocesses.

    Default executor — no server needed.

    Args:
        bridge_dir: Path to directory containing run_agent.mjs / run_agent_opencode.mjs.
                    If None, falls back to direct CLI invocation.
        node_path: Path to node executable. Auto-detected if None.
        max_concurrent: Maximum concurrent agent subprocesses.
        line_buffer_size: Subprocess stdout buffer size in bytes.
        auth: Optional ``LocalJwtAuth`` (or any object exposing
              ``mint(cwd, mode, tools)`` and ``verify_and_enforce(token,
              cwd, mode, tools)``). When supplied, every ``execute()``
              call mints a token bound to the ``AgentConfig`` and calls
              ``verify_and_enforce`` before the subprocess is spawned.
              A ``ClaimsViolation`` (subclass of ``ValueError``) raised
              by the verifier propagates out of ``execute()`` and the
              subprocess never starts — this is the parent → child
              zero-trust gate. When ``auth`` is ``None`` the executor
              behaves exactly as before (no enforcement).
    """

    def __init__(
        self,
        bridge_dir: Optional[str] = None,
        node_path: Optional[str] = None,
        max_concurrent: int = 3,
        line_buffer_size: int = 4 * 1024 * 1024,
        auth: Optional[object] = None,
    ):
        self.bridge_dir = Path(bridge_dir) if bridge_dir else None
        self.node = node_path or _find_executable("node")
        self.max_concurrent = max_concurrent
        self.line_buffer_size = line_buffer_size
        self._auth = auth
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running: dict[str, asyncio.subprocess.Process] = {}

        if self.bridge_dir:
            logger.info("SubprocessExecutor: bridge_dir=%s, node=%s",
                        self.bridge_dir, self.node)
        else:
            logger.info("SubprocessExecutor: direct CLI mode (no bridge dir)")
        if self._auth is not None:
            logger.info("SubprocessExecutor: zero-trust auth gate enabled")

    async def execute(self, config: AgentConfig) -> AsyncIterator[AgentEvent]:
        """Spawn a CLI agent subprocess and yield normalized events.

        If an ``auth`` was supplied at construction time, this method
        mints a claim token bound to ``(config.cwd, config.mode,
        config.tools)`` and immediately verifies it against the same
        triple. The verification call is what invokes
        ``enforce_agent_claims`` — any drift between the mint and the
        verify (which would only be possible if another task mutated
        ``config`` concurrently) raises and prevents the subprocess
        from being spawned.
        """
        if self._auth is not None:
            token = self._auth.mint(  # type: ignore[union-attr]
                cwd=config.cwd,
                mode=config.mode.value,
                tools=list(config.tools),
            )
            # Raises ClaimsViolation on mismatch — do NOT catch here.
            self._auth.verify_and_enforce(  # type: ignore[union-attr]
                token,
                cwd=config.cwd,
                mode=config.mode.value,
                tools=list(config.tools),
            )

        job_id = config.job_id
        t_start = time.monotonic()
        seq = 0
        result_text = ""

        async with self._semaphore:
            try:
                async with asyncio.timeout(config.timeout_seconds):
                    async for event in self._execute_inner(config):
                        seq += 1
                        event.seq = seq
                        event.job_id = job_id
                        yield event

                        if event.type == EventType.TEXT and event.text:
                            result_text = event.text
                        elif event.type == EventType.RESULT and event.result:
                            if not result_text:
                                result_text = event.result

                        if event.is_fatal:
                            break
            except TimeoutError:
                seq += 1
                yield AgentEvent(
                    type=EventType.SYSTEM, subtype="error",
                    error=f"Agent timed out after {config.timeout_seconds}s",
                    seq=seq, job_id=job_id,
                )

        duration_ms = int((time.monotonic() - t_start) * 1000)
        seq += 1
        yield AgentEvent(
            type=EventType.SYSTEM, subtype="stream_end",
            result=result_text,
            seq=seq, job_id=job_id,
            metadata={"duration_ms": duration_ms},
        )

    async def _execute_inner(self, config: AgentConfig) -> AsyncIterator[AgentEvent]:
        """Route to bridge or direct execution."""
        if self.bridge_dir and self.node:
            async for event in self._run_via_bridge(config):
                yield event
        else:
            async for event in self._run_direct(config):
                yield event

    async def _run_via_bridge(self, config: AgentConfig) -> AsyncIterator[AgentEvent]:
        """Run agent via Node.js bridge script."""
        if config.cli_type == CLIType.OPENCODE:
            script = self.bridge_dir / "run_agent_opencode.mjs"  # type: ignore[operator]
        else:
            script = self.bridge_dir / "run_agent.mjs"  # type: ignore[operator]

        if not script.exists():
            raise FileNotFoundError(f"Bridge script not found: {script}")

        stdin_config = {
            "task": self._build_prompt(config),
            "cwd": config.cwd,
            "mode": config.mode.value,
        }
        if config.system_prompt:
            stdin_config["systemPrompt"] = config.system_prompt
        if config.tools:
            stdin_config["tools"] = ",".join(config.tools)
        if config.model:
            if config.cli_type == CLIType.OPENCODE and config.provider:
                m = config.model.strip()
                p = config.provider.strip()
                if not m.startswith(f"{p}/"):
                    m = f"{p}/{m}"
                stdin_config["model"] = m
            else:
                stdin_config["model"] = config.model
        if config.provider:
            stdin_config["provider"] = config.provider
        if config.api_key:
            stdin_config["apiKey"] = config.api_key
        if config.cli_type == CLIType.OPENCODE and config.provider and config.api_key:
            stdin_config["providerConfig"] = {  # type: ignore[assignment]
                "provider": config.provider,
                "apiKey": config.api_key,
            }
        if config.business_id:
            stdin_config["businessId"] = config.business_id
        if config.agent_id:
            stdin_config["agentId"] = config.agent_id
        if config.docs_dir:
            stdin_config["docsDir"] = config.docs_dir
        if config.task_id:
            stdin_config["taskId"] = config.task_id

        cmd = [self.node, str(script), "--stdin"]

        async for event in self._run_subprocess(cmd, stdin_config, config):
            yield event

    async def _run_direct(self, config: AgentConfig) -> AsyncIterator[AgentEvent]:
        """Run CLI agent directly without bridge scripts."""
        prompt = self._build_prompt(config)
        _cleanup = None
        extra_env: dict[str, str] = {}

        if config.cli_type == CLIType.OPENCODE:
            cli = _find_executable("opencode")
            if not cli:
                raise FileNotFoundError("opencode CLI not found on PATH")

            cmd = [cli, "run", "--format", "json"]
            if config.model:
                m = config.model.strip()
                p = (config.provider or "").strip()
                if p and not m.startswith(f"{p}/"):
                    m = f"{p}/{m}"
                cmd.extend(["-m", m])
            cmd.append(prompt)

            # Write opencode.json into a per-job config dir OUTSIDE the
            # target cwd. Previously this file landed in ``config.cwd``
            # and could be accidentally committed from the user's repo
            # (every demo run would drop the api key into whatever
            # directory the user pointed the showcase at). We now write
            # under ``logs/<job_id>/config`` and export ``XDG_CONFIG_HOME``
            # pointing there, which opencode honours for config lookup.
            if config.provider and config.api_key:
                logs_dir = (
                    config.metadata.get("logs_dir", "./logs")
                    if config.metadata
                    else "./logs"
                )
                cfg_dir = Path(logs_dir) / config.job_id / "config"
                # Per-job config dir — owner-only on POSIX. ([26])
                cfg_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                _cleanup = _write_opencode_json(
                    str(cfg_dir),
                    config.provider,
                    config.api_key,
                    config.model,
                )
                extra_env["XDG_CONFIG_HOME"] = str(cfg_dir)
        else:
            cli = _find_executable("claude")
            if not cli:
                raise FileNotFoundError("claude CLI not found on PATH")
            cmd = [cli, "--verbose", "--output-format", "stream-json", "-p", prompt]
            if config.model:
                cmd.extend(["--model", config.model])
            if config.system_prompt:
                cmd.extend(["--system-prompt", config.system_prompt])
            tools_str = ",".join(config.tools) if config.tools else ""
            if tools_str:
                cmd.extend(["--allowedTools", tools_str])

        try:
            async for event in self._run_subprocess(cmd, None, config, extra_env=extra_env):
                yield event
        finally:
            if _cleanup:
                _cleanup()

    async def _run_subprocess(
        self,
        cmd: list,
        stdin_config: Optional[dict],
        config: AgentConfig,
        extra_env: Optional[dict[str, str]] = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run a subprocess, optionally pipe JSON to stdin, yield AgentEvents."""
        label = f"exec-{config.job_id[:8]}"
        logger.info("[%s] Spawning: %s (cwd=%s, mode=%s)",
                    label, cmd[0], config.cwd, config.mode.value)

        child_env = {k: v for k, v in os.environ.items()
                     if k not in ("CLAUDECODE", "CLAUDE_CODE")}

        # Give each opencode agent its own data dir to avoid SQLite WAL lock
        # contention on the shared ~/.local/share/opencode/opencode.db.
        # opencode resolves data path as $XDG_DATA_HOME/opencode/.
        # We point XDG_DATA_HOME to a per-agent dir under our logs so we
        # control the DB location and can inspect it per-agent.
        if config.cli_type == CLIType.OPENCODE:
            logs_dir = config.metadata.get("logs_dir", "./logs") if config.metadata else "./logs"
            agent_data_dir = Path(logs_dir) / config.job_id / "data"
            # Per-agent data dir (opencode SQLite WAL lives here) —
            # owner-only on POSIX so other users can't enumerate. ([26])
            agent_data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            child_env["XDG_DATA_HOME"] = str(agent_data_dir)
            logger.info("[%s] OPENCODE data dir: %s", label, agent_data_dir)

        # Caller-supplied env overrides — used by _run_direct to export
        # XDG_CONFIG_HOME at a per-job config dir so the opencode.json
        # we just wrote is the one opencode reads.
        if extra_env:
            child_env.update(extra_env)

        # On Windows a child inherits the parent's console, so a CTRL_C_EVENT
        # goes to every process attached to it — one Ctrl-C in the launcher's
        # terminal kills every running agent with 0xC000013A
        # (STATUS_CONTROL_C_EXIT). Giving each child its own process group
        # stops it receiving the console's control events. It does not change
        # stdio, and shutdown is unaffected: children are terminated explicitly
        # below and in stop().
        spawn_kwargs = {}
        if sys.platform == "win32":
            spawn_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_config else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.cwd if os.path.isdir(config.cwd) else None,
            limit=self.line_buffer_size,
            env=child_env,
            **spawn_kwargs,
        )

        self._running[config.job_id] = proc

        if stdin_config and proc.stdin:
            proc.stdin.write(json.dumps(stdin_config).encode())
            await proc.stdin.drain()
            proc.stdin.close()

        stderr_lines: list[str] = []

        async def _read_stderr():
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                stderr_lines.append(line.decode(errors="replace").rstrip())

        stderr_task = asyncio.create_task(_read_stderr())

        seq = 0
        try:
            while True:
                line = await proc.stdout.readline()  # type: ignore[union-attr]
                if not line:
                    break
                text = line.decode(errors="replace").strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                    seq += 1
                    yield normalize_event(raw, seq=seq, job_id=config.job_id)
                except json.JSONDecodeError:
                    logger.debug("[%s] non-JSON stdout: %s", label, text[:200])
        finally:
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

            stderr_task.cancel()
            try:
                await stderr_task
            except asyncio.CancelledError:
                pass

            self._running.pop(config.job_id, None)

            logger.info("[%s] Exited: code=%s, events=%d", label, proc.returncode, seq)

            if proc.returncode and proc.returncode != 0:
                _noise = ("INFO", "DEBUG", "TRACE", "Allowed:", "Denied:",
                          "Ruleset:", "Permission", "  -",
                          "[opencode:stderr]", "[opencode:event]",
                          "[opencode:stdout]", "[opencode:trailing]")
                useful = [ln for ln in stderr_lines
                          if ln.strip() and not any(ln.lstrip().startswith(p) for p in _noise)]
                stderr_summary = "\n".join(useful[-10:]) if useful else ""

                if proc.returncode in (-2, -9, 137):
                    msg = "Agent interrupted" if proc.returncode == -2 else "Agent canceled"
                else:
                    msg = f"Agent exited with code {proc.returncode}"
                if stderr_summary:
                    msg += f"\n{stderr_summary}"

                seq += 1
                yield AgentEvent(
                    type=EventType.RESULT, subtype="error_agent_exit",
                    result=msg, error=msg,
                    seq=seq, job_id=config.job_id,
                )

    def _build_prompt(self, config: AgentConfig) -> str:
        """Build the full prompt including chat history if provided."""
        if not config.chat_history:
            return config.task

        parts = []
        for msg in config.chat_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")

        if parts:
            return (
                "Previous conversation:\n"
                + "\n\n".join(parts)
                + "\n\nCurrent request:\n"
                + config.task
            )
        return config.task

    async def cancel(self, job_id: str) -> bool:
        """Kill a running agent subprocess."""
        proc = self._running.get(job_id)
        if proc and proc.returncode is None:
            logger.info("Killing agent: job=%s pid=%s", job_id, proc.pid)
            proc.kill()
            return True
        return False


# ---------------------------------------------------------------------------
# Process-wide shared executor
# ---------------------------------------------------------------------------
# A single SubprocessExecutor instance per process, registered by the host
# application at startup and fetched by standalone helpers (e.g. llm_call())
# that don't have access to a pipeline ServiceRegistry. Mirrors the
# execution_tracker / hitl._state_manager pattern.
#
# Every AgentStep/LLMStep inside a pipeline reaches its executor through the
# ServiceRegistry; only helpers outside that wiring use these functions.
#
# Host app contract: call set_shared_executor(...) exactly once from its
# lifespan startup. Failing to register and then calling get_shared_executor()
# raises — no silent fallback, no per-call constructor, because a fresh
# executor would silently defeat the concurrency semaphore.
_shared_executor: Optional["SubprocessExecutor"] = None


def set_shared_executor(executor: "SubprocessExecutor") -> None:
    """Register the process-wide SubprocessExecutor. Called once at startup."""
    global _shared_executor
    _shared_executor = executor


def get_shared_executor() -> "SubprocessExecutor":
    """Return the process-wide SubprocessExecutor, raising if unset."""
    if _shared_executor is None:
        raise RuntimeError(
            "SubprocessExecutor singleton is not registered — "
            "the host app must call set_shared_executor() at startup."
        )
    return _shared_executor
