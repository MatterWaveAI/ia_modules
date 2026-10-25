# IA Modules - Quick Start Guide

Get started with IA Modules in under 5 minutes!

## 🚀 Fastest Start: Showcase App

**See IA Modules in action with our interactive showcase.** From the repository root:

```bash
# Terminal 1 - Backend (http://localhost:7331)
cd showcase_app/backend
pip install -e ../..
pip install -r requirements.txt
cp .env.example .env
python main.py

# Terminal 2 - Frontend
cd showcase_app/frontend
npm install
npm run dev
```

**Then open:** http://localhost:5174

See [README.md](README.md#quick-start) for the LLM settings in `showcase_app/backend/.env`.

### What You'll See

- ✅ **Example Pipelines** - Pre-built pipelines ready to execute
- ✅ **Agent Collaboration Patterns** - Debate, reflection, planning, agentic RAG
- ✅ **Real-Time Monitoring** - Watch pipelines execute live
- ✅ **Reliability Dashboard** - SR, CR, HIR, TCL, WCT metrics
- ✅ **SLO Compliance** - Visual compliance tracking
- ✅ **Execution History** - All runs with detailed logs

## 📦 Framework-Only Installation

If you just want to use IA Modules in your own project (Python 3.11+):

```bash
# Install with all features
pip install ia_modules[all]

# Or minimal install
pip install ia_modules
```

## 💻 Your First Pipeline

```python
import asyncio
from ia_modules.pipeline.core import Pipeline, Step, ExecutionContext
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.reliability import ReliabilityMetrics, MemoryMetricStorage

# 1. Define a step: run() receives the pipeline data and returns its outputs
class GreetingStep(Step):
    async def run(self, data):
        name = data.get("name", "World")
        return {"greeting": f"Hello, {name}!"}

async def main():
    # 2. Build a one-step pipeline
    pipeline = Pipeline(
        name="hello",
        steps=[GreetingStep("greet", {})],
        flow={"start_at": "greet", "paths": []},
        services=ServiceRegistry(),
    )

    # 3. Run it
    result = await pipeline.run(
        {"name": "Developer"},
        execution_context=ExecutionContext(execution_id="run-1", pipeline_id="hello"),
    )
    print(f"Result: {result['output']['greeting']}")

    # 4. Record and report reliability metrics
    metrics = ReliabilityMetrics(MemoryMetricStorage())
    await metrics.record_step(agent="greet", success=True)
    report = await metrics.get_report()
    print(f"Step Validity Rate: {report.svr:.2%}")

asyncio.run(main())
```

Pipelines are usually defined in JSON and run with `run_pipeline_from_json`; see
[README.md](README.md#quickstart-your-first-pipeline).

## 📚 Next Steps

### Learn the Framework

1. **[Getting Started Guide](docs/GETTING_STARTED.md)** - Comprehensive tutorial
2. **[Features Overview](docs/FEATURES.md)** - All capabilities
3. **[API Reference](docs/API_REFERENCE.md)** - Detailed API docs

### Explore Examples

1. **Showcase App** - Interactive demo at http://localhost:5174
2. **Example Pipelines** - See [tests/pipelines/](tests/pipelines/)
3. **Test Suite** - Check [tests/](tests/) for working examples

### Production Deployment

1. **[Reliability Guide](docs/RELIABILITY_USAGE_GUIDE.md)** - EARF compliance
2. **[Upgrading to 0.3.0](README.md#upgrading-to-030)** - Database and environment changes
3. **[Migration Guide](docs/MIGRATION.md)** - Upgrading from older versions
4. **[Contributing](CONTRIBUTING.md)** - How to contribute

## Built-in Step Types

IA Modules provides ready-to-use step types so you don't need to subclass `Step` for common patterns:

| Step Type | Module | Use Case |
|-----------|--------|----------|
| `LLMStep` | `pipeline.llm_step` | Send a prompt to a CLI agent, get text back |
| `FunctionStep` | `pipeline.function_step` | Wrap an async callable (vote tallying, routing, aggregation) |
| `AgentStep` | `pipeline.agent_step` | Run a CLI agent with workspace and tools |
| `A2AStep` | `pipeline.a2a_step` | Dispatch work to a remote A2A agent server |
| `ParallelStep` | `pipeline.parallel_step` | Fan-out: run child steps concurrently |
| `OrchestratorStep` | `pipeline.orchestrator_step` | Run an orchestrator pattern as one atomic step |

Every step takes `(name, config)`:

```python
from ia_modules.pipeline import LLMStep, FunctionStep, ParallelStep

# LLM step — just a prompt, no subclassing needed
summarizer = LLMStep("summarize", {
    "system_prompt": "Summarize the following text concisely.",
    "cli_type": "claude_code",
    "model": "claude-sonnet-4-5",
})

# Function step — wrap any async callable; it receives (data, step)
async def tally_votes(data, step):
    votes = data.get("votes", [])
    return {"winner": max(set(votes), key=votes.count)}

tally = FunctionStep("tally", {"fn": tally_votes})

# Parallel step — fan out to multiple child steps
parallel = ParallelStep("all_reviewers", {
    "steps": [LLMStep(f"reviewer_{i}", {"system_prompt": "Review this change."}) for i in range(3)],
})
```

## Agent Authentication

For multi-tenant or production deployments, agents authenticate via OIDC JWTs. The auth system is pluggable — use the built-in mini OIDC provider for local dev, or connect to Keycloak/Auth0/Cognito for production.

```python
from ia_modules.agents.auth import get_adapter
from ia_modules.agents.permissions import enforce_agent_claims

# Get configured IDP adapter (AGENT_AUTH_MODE=local or oidc)
adapter = get_adapter(db=my_db)

# Validate a Bearer token and get claims
claims = await adapter.validate_token(token)

# Enforce permissions before execution
enforce_agent_claims(claims, cwd="/data/workspace", mode="research", tools=["Read", "Glob"])
```

Set `AGENT_AUTH_MODE=oidc` and configure `OIDC_DISCOVERY_URL` for production Keycloak/OIDC. Default is `local` (built-in mini OIDC, no external IDP needed).

## 🎯 Common Use Cases

### Remote Agent Dispatch (A2A)

```python
# Dispatch to a remote A2A server
from ia_modules.pipeline import A2AStep

remote_agent = A2AStep("remote_analysis", {
    "task": "Analyze the codebase for security issues",
    "a2a_url": "http://a2a-server:3008",
    "mode": "research",
    "tools": ["Read", "Glob", "Grep"],
})
```

### Human-in-the-Loop

Add a `HumanInputStep` (from `ia_modules.pipeline.hitl`) to a pipeline to pause for approval; see
[README.md](README.md#human-in-the-loop-hitl) and [tests/pipelines/hitl_pipeline/](tests/pipelines/hitl_pipeline/).

## 🛠️ CLI Tools

```bash
# Validate pipeline definition
ia-modules validate pipeline.json

# Run pipeline
ia-modules run pipeline.json --input input.json

# Visualize pipeline (needs the cli extra: pip install ia_modules[cli])
ia-modules visualize pipeline.json --output graph.png

# Format pipeline JSON
ia-modules format pipeline.json --in-place
```

## 💡 Tips

### Enable Reliability Tracking

Store metrics in SQL in production. The `reliability_*` tables come from ia_modules' migrations:

```python
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR
from ia_modules.reliability import ReliabilityMetrics
from ia_modules.reliability.sql_metric_storage import SQLMetricStorage

db = DatabaseManager("postgresql://user:pass@localhost/metrics")
await db.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])

storage = SQLMetricStorage(db)
metrics = ReliabilityMetrics(storage)
```

### Monitor SLO Compliance

`SLOTracker` tracks Mean Time to Explain (MTTE) and Replay Success Rate (RSR):

```python
from ia_modules.reliability.slo_tracker import SLOTracker

tracker = SLOTracker()
await tracker.record_rsr("thread-1", "checkpoint-1", "strict", success=True)

report = await tracker.get_report()
if not report.is_compliant():
    print("SLO violations:", report.get_violations())
```

### Use Checkpointing

```python
from ia_modules.checkpoint import MemoryCheckpointer

pipeline = Pipeline(
    name="hello",
    steps=[GreetingStep("greet", {})],
    flow={"start_at": "greet", "paths": []},
    services=ServiceRegistry(),
    checkpointer=MemoryCheckpointer(),
)

# Saves state after each step under thread_id ...
result = await pipeline.run(
    {"name": "Developer"},
    execution_context=ExecutionContext(execution_id="run-2", pipeline_id="hello"),
    thread_id="workflow_123",
)

# ... so a failed run can be resumed from its last checkpoint
result = await pipeline.resume(thread_id="workflow_123")
```

## 🆘 Troubleshooting

### Backend Won't Start

```bash
# Check if port 7331 is in use
netstat -an | grep 7331  # Linux/Mac
netstat -an | findstr 7331  # Windows
```

The backend port is set in `showcase_app/backend/main.py`, and the frontend proxies `/api` and `/ws` to it
(`showcase_app/frontend/vite.config.js`).

### Frontend Build Errors

```bash
cd showcase_app/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Import Errors

```bash
# Make sure IA Modules is installed
pip install -e .

# Verify installation
python -c "import ia_modules; print(ia_modules.__version__)"
```

## 📖 Documentation

- **Getting Started**: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)
- **Features**: [docs/FEATURES.md](docs/FEATURES.md)
- **API Reference**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Reliability**: [docs/RELIABILITY_USAGE_GUIDE.md](docs/RELIABILITY_USAGE_GUIDE.md)
- **Showcase App**: [showcase_app/README.md](showcase_app/README.md)

## 🔗 Links

- **Main README**: [README.md](README.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **License**: [LICENSE](LICENSE)

## 🎉 You're Ready!

Choose your path:

1. **Try the showcase app** → See [Fastest Start](#-fastest-start-showcase-app) above
2. **Build with the framework** → Read [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)
3. **Deploy to production** → See [docs/RELIABILITY_USAGE_GUIDE.md](docs/RELIABILITY_USAGE_GUIDE.md)

**Questions?** Check the docs or open an issue on GitHub.

**Happy building!** 🚀
