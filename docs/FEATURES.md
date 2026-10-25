# IA Modules Feature Matrix

Feature overview for v0.2.0. Features marked "Production" are tested and working.

## Core Pipeline Features

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Graph-Based Pipeline** | ✅ Production | Define workflows as directed graphs with conditional routing | [Pipeline Architecture](PIPELINE_ARCHITECTURE.md) |
| **Cyclic Graph Support** | ✅ Production | Support for loops and iterative workflows with cycle detection | [Pipeline Architecture](PIPELINE_ARCHITECTURE.md) |
| **Conditional Routing** | ✅ Production | Dynamic step routing based on execution results | [Getting Started](GETTING_STARTED.md) |
| **Parallel Execution** | ✅ Production | Execute multiple pipeline branches concurrently | [Getting Started](GETTING_STARTED.md) |
| **JSON Pipeline Definition** | ✅ Production | Define pipelines declaratively in JSON format | [Getting Started](GETTING_STARTED.md) |
| **Dynamic Step Loading** | ✅ Production | Load step implementations dynamically from modules | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Context Management** | ✅ Production | Thread-safe context for data sharing between steps | [Execution Architecture](EXECUTION_ARCHITECTURE.md) |

## Built-in Step Types (New in v0.2.0)

No more subclassing `Step` for common patterns — use these out of the box:

| Step Type | Status | Description | Documentation |
|-----------|--------|-------------|---------------|
| **LLMStep** | ✅ Production | Prompt-in, text-out via a CLI agent | [Developer Guide](DEVELOPER_GUIDE.md) |
| **FunctionStep** | ✅ Production | Wrap any async callable as a pipeline step | [Developer Guide](DEVELOPER_GUIDE.md) |
| **AgentStep** | ✅ Production | Run a CLI agent (Claude Code SDK, OpenCode) locally with workspace and tool constraints | [Developer Guide](DEVELOPER_GUIDE.md) |
| **A2AStep** | ✅ Production | Dispatch work to a remote A2A server via JSON-RPC | [Developer Guide](DEVELOPER_GUIDE.md) |
| **ParallelStep** | ✅ Production | Fan-out — run child steps concurrently | [Developer Guide](DEVELOPER_GUIDE.md) |
| **OrchestratorStep** | ✅ Production | Run a collaboration pattern (debate, reflection, planning, agentic RAG) atomically | [Developer Guide](DEVELOPER_GUIDE.md) |

## Agent Execution & Authentication (New in v0.2.0)

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Agent Execution Framework** | ✅ Production | Pluggable executor interface for CLI agents with workspace/mode/tool constraints | [Developer Guide](DEVELOPER_GUIDE.md) |
| **SubprocessExecutor** | ✅ Production | Run Claude Code SDK / OpenCode as subprocess with scoped CWD | [Developer Guide](DEVELOPER_GUIDE.md) |
| **A2AExecutor** | ✅ Production | Dispatch to remote A2A-protocol servers with JWT bearer auth | [Developer Guide](DEVELOPER_GUIDE.md) |
| **OIDC Authentication** | ✅ Production | Pluggable IDP adapter — `MiniOIDCAdapter` (dev) / `KeycloakAdapter` (prod, Auth0/Cognito compatible) | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Zero-Trust Claim Enforcement** | ✅ Production | `enforce_agent_claims()` validates JWT `a2a` claim against cwd/mode/tools before execution | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Collaboration Patterns** | ✅ Production | Debate, reflection, planning, agentic RAG as reusable orchestrators | [Developer Guide](DEVELOPER_GUIDE.md) |

## Reliability & Observability (EARF-Compliant)

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Reliability Metrics** | ✅ Production | Track SR, CR, PC, HIR, MA, TCL, WCT | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md) |
| **Multiple Storage Backends** | ✅ Production | In-memory, SQL (PostgreSQL, MySQL, SQLite, DuckDB), Redis | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md#storage-backends) |
| **SLO Monitoring** | ✅ Production | Define and monitor Service Level Objectives | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md#slo-tracking) |
| **Auto-Evidence Collection** | ✅ Production | Automatic evidence capture for compliance | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md#evidence-collection) |
| **Event Replay** | ✅ Production | Replay step executions for debugging | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md#replay-system) |
| **Compensation Tracking** | ✅ Production | Track and analyze compensation events | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md#core-metrics) |
| **FinOps Metrics** | ✅ Production | Tool Call Latency (TCL) and Workflow Completion Time (WCT) | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md#performance-metrics) |

### Reliability Metrics Detail

**Core Metrics:**
- **SR (Success Rate)**: Percentage of successful step executions
- **CR (Compensation Rate)**: Percentage requiring compensation/rollback
- **PC (Pass Confidence)**: Statistical confidence in success rate
- **HIR (Human Intervention Rate)**: Percentage requiring human review
- **MA (Model Accuracy)**: Agent decision accuracy

**Performance Metrics:**
- **TCL (Tool Call Latency)**: Average tool execution time (ms)
- **WCT (Workflow Completion Time)**: End-to-end workflow duration (ms)
- **MTTE (Mean Time to Error)**: Average time between failures
- **RSR (Retry Success Rate)**: Success rate after retries

## Checkpointing & Recovery

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Automatic Checkpointing** | ✅ Production | Save pipeline state at each step | [Getting Started](GETTING_STARTED.md) |
| **Resume from Checkpoint** | ✅ Production | Resume failed pipelines from last checkpoint | [Getting Started](GETTING_STARTED.md) |
| **Thread Management** | ✅ Production | Organize checkpoints by workflow threads | [Execution Architecture](EXECUTION_ARCHITECTURE.md) |
| **State Serialization** | ✅ Production | Serialize arbitrary Python objects in checkpoints | [Developer Guide](DEVELOPER_GUIDE.md) |
| **SQLite Storage** | ✅ Production | Persistent checkpoint storage with SQLite | [Developer Guide](DEVELOPER_GUIDE.md) |

## Memory & State Management

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Conversation Memory** | ✅ Production | Track conversation history across pipeline runs | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Session Management** | ✅ Production | Group related conversations into sessions | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Vector Search** | ✅ Production | Semantic search over conversation history | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Memory Summarization** | ✅ Production | Automatic summarization of long conversations | [Developer Guide](DEVELOPER_GUIDE.md) |
| **SQLite Storage** | ✅ Production | Persistent memory storage | [Developer Guide](DEVELOPER_GUIDE.md) |

## Scheduling & Automation

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Cron Scheduling** | ✅ Production | Schedule pipelines with cron expressions | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Job Management** | ✅ Production | Create, update, delete scheduled jobs | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Async Execution** | ✅ Production | Non-blocking scheduled pipeline execution | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Job History** | ✅ Production | Track execution history for scheduled jobs | [Developer Guide](DEVELOPER_GUIDE.md) |

## Multi-Agent Orchestration

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Agent Orchestrator** | ✅ Production | Coordinate multiple AI agents | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Sequential Workflows** | ✅ Production | Execute agents in sequence | [Getting Started](GETTING_STARTED.md) |
| **Parallel Workflows** | ✅ Production | Execute agents concurrently | [Getting Started](GETTING_STARTED.md) |
| **Hierarchical Agents** | ✅ Production | Parent-child agent relationships | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Agent State Sharing** | ✅ Production | Share state between agents in workflows | [Developer Guide](DEVELOPER_GUIDE.md) |

## Grounding & Validation

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Schema Validation** | ✅ Production | Validate data against Pydantic schemas | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Type Checking** | ✅ Production | Runtime type validation for step inputs/outputs | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Citation Tracking** | ✅ Production | Track sources and citations for agent outputs | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Fact Verification** | ✅ Production | Verify agent claims against knowledge base | [Developer Guide](DEVELOPER_GUIDE.md) |
| **Grounding Metrics** | ✅ Production | Measure grounding quality and citation coverage | [Reliability Guide](RELIABILITY_USAGE_GUIDE.md) |

## Developer Tools

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **CLI Tool** | ✅ Production | Command-line interface for pipeline management | [CLI Documentation](CLI_TOOL_DOCUMENTATION.md) |
| **Pipeline Validation** | ✅ Production | Validate pipeline definitions before execution | [CLI Documentation](CLI_TOOL_DOCUMENTATION.md) |
| **Pipeline Visualization** | ✅ Production | Generate graph visualizations of pipelines | [CLI Documentation](CLI_TOOL_DOCUMENTATION.md) |
| **Plugin System** | ✅ Production | Extend IA Modules with custom plugins | [Plugin Documentation](PLUGIN_SYSTEM_DOCUMENTATION.md) |

### CLI Commands

```bash
ia-modules run <pipeline.json>         # Execute pipeline
ia-modules validate <pipeline.json>    # Validate pipeline definition
ia-modules format <pipeline.json>      # Format a pipeline JSON file
ia-modules visualize <pipeline.json>   # Generate graph visualization
```

See [CLI_TOOL_DOCUMENTATION.md](CLI_TOOL_DOCUMENTATION.md) for full flag reference.

## Plugin System

| Feature | Status | Description | Documentation |
|---------|--------|-------------|---------------|
| **Plugin Discovery** | ✅ Production | Automatic plugin discovery and loading | [Plugin Documentation](PLUGIN_SYSTEM_DOCUMENTATION.md) |
| **Hook System** | ✅ Production | Register callbacks for pipeline events | [Plugin Documentation](PLUGIN_SYSTEM_DOCUMENTATION.md) |
| **Step Plugins** | ✅ Production | Add custom pipeline steps via plugins | [Plugin Documentation](PLUGIN_SYSTEM_DOCUMENTATION.md) |
| **Storage Plugins** | ✅ Production | Custom storage backends for metrics/checkpoints | [Plugin Documentation](PLUGIN_SYSTEM_DOCUMENTATION.md) |
| **Plugin Configuration** | ✅ Production | Configure plugins via JSON | [Plugin Documentation](PLUGIN_SYSTEM_DOCUMENTATION.md) |

## Database Support

Via nexusql package:

| Feature | Status | Backend | Notes |
|---------|--------|---------|-------|
| **PostgreSQL** | ✅ Production | SQL | Via nexusql |
| **MySQL** | ✅ Production | SQL | Via nexusql |
| **SQLite** | ✅ Production | SQL | Default, via nexusql |
| **DuckDB** | ✅ Production | SQL | Via nexusql |

## Python Version Support

| Python Version | Status | Notes |
|----------------|--------|-------|
| 3.11 – 3.14 | ✅ Supported | 3.11 is the minimum; CI tests 3.14 |

## EARF Compliance Matrix

IA Modules v0.2.0 is fully compliant with the Enterprise Agent Reliability Framework (EARF).

| EARF Pillar | Requirement | Implementation | Status |
|-------------|-------------|----------------|--------|
| **Total Observability** | Comprehensive metrics | SR, CR, PC, HIR, MA, TCL, WCT metrics | ✅ Complete |
| **Total Observability** | Multiple storage backends | SQL, Redis, In-Memory | ✅ Complete |
| **Total Observability** | Real-time monitoring | Live metric collection | ✅ Complete |
| **Total Observability** | Performance tracking | TCL, WCT, MTTE, RSR | ✅ Complete |
| **Absolute Reproducibility** | Checkpointing | Automatic state snapshots | ✅ Complete |
| **Absolute Reproducibility** | Event replay | Replay step executions | ✅ Complete |
| **Absolute Reproducibility** | State serialization | Full context preservation | ✅ Complete |
| **Formal Safety & Verification** | Schema validation | Pydantic-based validation | ✅ Complete |
| **Formal Safety & Verification** | Type checking | Runtime type validation | ✅ Complete |
| **Formal Safety & Verification** | Grounding | Citation tracking and verification | ✅ Complete |
| **Formal Safety & Verification** | SLO compliance | Automated SLO monitoring | ✅ Complete |
| **Formal Safety & Verification** | Evidence collection | Auto-capture for audits | ✅ Complete |

## Test Coverage

| Module | Tests | Notes |
|--------|-------|-------|
| **Total** | Unit, integration, showcase, e2e | Includes agent-auth and built-in step-type suites |



## Getting Help

- **Documentation**: [docs/](.)
- **Getting Started**: [GETTING_STARTED.md](GETTING_STARTED.md)
- **Developer Guide**: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Testing Guide**: [TESTING_GUIDE.md](TESTING_GUIDE.md)
