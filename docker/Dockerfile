# The Command Center runner image.
#
# One image, `agent-runner`: ia_modules plus the `postgres` extra. The
# platform runs it three ways — Pipeline Job (the default), queue worker,
# CronJob — but every one of them is "run ONE pipeline from env/config and
# exit"; the exit code is the outcome. See docs/runtime-ia-modules.md in
# the agent-command-center repo.
#
# Note: ia_modules pins nexusql==0.4.0 in its core dependencies, so the
# state layer this image talks to is exactly the version the rest of the
# platform runs.
FROM python:3.11-slim

LABEL org.opencontainers.image.title="agent-runner" \
      org.opencontainers.image.description="ia_modules pipeline runner — one pipeline per process, checkpoints in Postgres via nexusql" \
      org.opencontainers.image.source="https://github.com/matterwaveai/ia_modules" \
      org.opencontainers.image.licenses="MIT"

# Stream logs straight to the collector; never want buffered stdout in k8s
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dedicated non-root user — the runner executes pipelines, it owns nothing
RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin runner

WORKDIR /app

# Install the package itself. Core dependencies bring nexusql (pinned
# ==0.4.0) and pyyaml (bundle pipelines); the postgres extra brings
# psycopg2-binary. All wheels — no build tools needed on slim.
COPY pyproject.toml README.md ./
COPY ia_modules ./ia_modules
RUN pip install ".[postgres]"

# The smoke pipeline the release CI runs against a service Postgres before
# pushing: first attempt fails after the first checkpoint, the retry must
# resume rather than rerun (see docker/smoke/smoke_steps.py).
COPY docker/smoke /opt/smoke

USER runner

# Jobs run one pipeline and exit: ENTRYPOINT is the binary so k8s `args`
# land as pipeline args. --version is the healthcheck-friendly no-op:
# process alive, config loadable, no pipeline needed.
ENTRYPOINT ["ia-runner"]
CMD ["--help"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["ia-runner", "--version"]
