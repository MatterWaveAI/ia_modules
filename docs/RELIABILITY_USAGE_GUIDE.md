# Reliability & Observability Guide

Production monitoring and reliability features for AI agent systems.

## Table of Contents

- [Overview](#overview)
- [Reliability Metrics](#reliability-metrics)
- [Decision Trails](#decision-trails)
- [Replay System](#replay-system)
- [SLO Tracking](#slo-tracking)
- [Mode Enforcement](#mode-enforcement)
- [Evidence Collection](#evidence-collection)
- [Circuit Breakers](#circuit-breakers)
- [Cost Tracking](#cost-tracking)
- [Anomaly Detection](#anomaly-detection)
- [Trend Analysis](#trend-analysis)
- [Alert System](#alert-system)
- [Storage Backends](#storage-backends)
- [Best Practices](#best-practices)

## Overview

The reliability system provides:

- **Metrics**: Track SVR, CR, PC, HIR, MA for production agents
- **Decision Trails**: Reconstruct complete decision history
- **Replay System**: Replay and debug agent workflows
- **SLO Tracking**: Track MTTE (Mean Time to Explain) and RSR (Replay Success Rate)
- **Mode Enforcement**: Enforce explore/execute/escalate modes
- **Evidence Collection**: Track verified facts vs agent claims
- **Circuit Breakers**: Protect against cascading failures
- **Cost Tracking**: Monitor LLM and tool costs
- **Anomaly Detection**: Detect performance degradation
- **Trend Analysis**: Identify degrading metrics over time
- **Alerts**: Get notified of issues

All components are optional and can be used independently.

## Reliability Metrics

### Core Metrics

Track five key reliability metrics:

- **SVR** (Step Validity Rate): % of successful steps (target >95%)
- **CR** (Compensation Rate): % of steps requiring fixes (target <10%)
- **PC** (Plan Churn): Average replans per workflow (target <2)
- **HIR** (Human Intervention Rate): % requiring human help (target <5%)
- **MA** (Mode Adherence): % following declared mode (target >90%)

### Basic Usage

```python
from reliability import ReliabilityMetrics

# Initialize
metrics = ReliabilityMetrics()

# Record step execution
await metrics.record_step(
    agent="data_processor",
    success=True,
    required_compensation=False,
    required_human=False,
    mode="execute",
    declared_mode="execute"
)

# Record workflow completion
await metrics.record_workflow(
    workflow_id="workflow-001",
    total_steps=10,
    total_retries=2,
    required_compensation=False,
    required_human=False,
    agents_involved=["processor", "validator"]
)

# Get metrics report
report = await metrics.get_report()

print(f"SVR: {report.svr:.2%} (target >95%)")
print(f"CR: {report.cr:.2%} (target <10%)")
print(f"PC: {report.pc:.1f} (target <2)")
print(f"HIR: {report.hir:.2%} (target <5%)")
print(f"MA: {report.ma:.2%} (target >90%)")

# Check health
if report.is_healthy():
    print("✓ All metrics healthy")
else:
    print("✗ Violations:")
    for violation in report.get_violations():
        print(f"  - {violation}")
```

### Per-Agent Metrics

```python
# Get breakdown by agent
for agent_name, agent_metrics in report.agent_metrics.items():
    print(f"\n{agent_name}:")
    print(f"  SVR: {agent_metrics.svr:.2%}")
    print(f"  CR: {agent_metrics.cr:.2%}")
    print(f"  MA: {agent_metrics.ma:.2%}")
    print(f"  Total steps: {agent_metrics.total_steps}")
```

### Performance Metrics

Track tool and workflow timing:

```python
# Record step with tool timing
await metrics.record_step(
    agent="api_caller",
    success=True,
    tool_duration_ms=250  # Tool took 250ms
)

# Record workflow with duration
await metrics.record_workflow(
    workflow_id="workflow-002",
    total_steps=15,
    total_retries=0,
    duration_ms=5000  # Workflow took 5 seconds
)

# Get performance metrics
report = await metrics.get_report()

if report.tcl:
    print(f"Average Tool Latency: {report.tcl:.0f}ms")

if report.wct:
    print(f"Average Workflow Time: {report.wct:.0f}ms")
```

## Decision Trails

Reconstruct complete decision history for debugging and auditing.

### Basic Usage

```python
from reliability import DecisionTrailBuilder, Evidence, StepRecord

# Create trail builder (requires state manager, tool registry, checkpoint manager)
trail_builder = DecisionTrailBuilder(
    state_manager=state_manager,
    tool_registry=tool_registry,
    checkpoint_manager=checkpoint_manager
)

# Build trail for a workflow
trail = await trail_builder.build_trail(
    thread_id="workflow-123",
    checkpoint_id="checkpoint-456"
)

# Inspect trail
print(f"Goal: {trail.goal}")
print(f"Success: {trail.success}")
print(f"Steps: {len(trail.steps)}")
print(f"Tool calls: {len(trail.tool_calls)}")

# Examine evidence by confidence
for evidence in trail.evidence:
    print(f"{evidence.confidence}: {evidence.type} from {evidence.source}")
```

### Evidence Levels

```python
# Evidence is categorized by confidence:
# - "verified": From tools, database, APIs (objective facts)
# - "claimed": From agent outputs (subjective claims)
# - "inferred": Derived from other evidence

verified = [e for e in trail.evidence if e.confidence == "verified"]
claimed = [e for e in trail.evidence if e.confidence == "claimed"]

print(f"Verified facts: {len(verified)}")
print(f"Agent claims: {len(claimed)}")
```

## Replay System

Replay workflows for debugging and testing.

### Strict Replay

```python
from reliability import Replayer, ReplayMode

replayer = Replayer(decision_trail)

# Replay with real tools (exact reproduction)
result = await replayer.strict_replay(
    orchestrator=orchestrator,
    tool_registry=tool_registry
)

if result.is_exact_match():
    print("✓ Workflow reproduced exactly")
else:
    print("✗ Differences found:")
    for diff in result.differences:
        print(f"  {diff.field}: {diff.significance}")
```

### Simulated Replay

```python
# Replay with mocked tool responses (fast testing)
result = await replayer.simulated_replay(orchestrator=orchestrator)

# Fast - no real tool calls
# Perfect for unit testing workflow logic
```

### Counterfactual Replay

```python
# Test what-if scenarios
alternative_inputs = {"temperature": 0.5}

result = await replayer.counterfactual_replay(
    alternative_inputs,
    orchestrator=orchestrator,
    tool_registry=tool_registry
)

print(f"Original outcome: {trail.outcome}")
print(f"Alternative outcome: {result.outcome}")
```

## SLO Tracking

Track Service Level Objectives for reliability.

### MTTE (Mean Time to Explain)

Track how long it takes to reconstruct decisions:

```python
from reliability import SLOTracker
import time

slo_tracker = SLOTracker()

# Record explanation time
start = time.time()
trail = await trail_builder.build_trail(thread_id, checkpoint_id)
explanation = await trail_builder.explain_decision(trail)
duration_ms = int((time.time() - start) * 1000)

await slo_tracker.record_mtte(
    thread_id=thread_id,
    checkpoint_id=checkpoint_id,
    duration_ms=duration_ms,
    success=True
)

# Get SLO report
slo_report = await slo_tracker.get_report()

print(f"MTTE P95: {slo_report.mtte_p95_ms/1000:.1f}s (target: 5min)")
print(f"Compliant: {slo_report.is_mtte_compliant()}")
```

### RSR (Replay Success Rate)

Track replay success:

```python
# Record replay attempt
result = await replayer.strict_replay(orchestrator, tool_registry)

await slo_tracker.record_rsr(
    thread_id=thread_id,
    checkpoint_id=checkpoint_id,
    replay_mode="strict",
    success=result.success
)

# Check compliance
slo_report = await slo_tracker.get_report()

print(f"RSR: {slo_report.rsr:.1%} (target: 99%)")
print(f"Compliant: {slo_report.is_rsr_compliant()}")
```

## Mode Enforcement

Enforce agent operating modes for predictable behavior.

### Agent Modes

```python
from reliability import ModeEnforcer, AgentMode

enforcer = ModeEnforcer()

# EXPLORE mode - Read-only research
enforcer.set_mode("researcher", AgentMode.EXPLORE)

# EXECUTE mode - Can take actions
enforcer.set_mode("executor", AgentMode.EXECUTE)

# ESCALATE mode - Requires human approval
enforcer.set_mode("reviewer", AgentMode.ESCALATE)
```

### Validate Actions

```python
# Check if action is allowed
if enforcer.can_execute("researcher", "database_write"):
    # Execute action
    execute_write()
else:
    print("✗ Action blocked - agent in EXPLORE mode")

# Record mode adherence
enforcer.record_action(
    agent="researcher",
    action="database_read",
    allowed=True
)

# Get violations
violations = enforcer.get_violations(agent="researcher")
for v in violations:
    print(f"Violation: {v.attempted_action} at {v.timestamp}")
```

### Mode Rules

```python
# EXPLORE mode restrictions
# - Can use: search, lookup, read, get, fetch, query, analyze
# - Cannot use: write, update, delete, create, modify, execute

# EXECUTE mode permissions
# - Can use all tools
# - Actions are logged

# ESCALATE mode
# - Requires human approval callback
enforcer.require_approval("reviewer", lambda action: input(f"Approve {action}? (y/n): ") == 'y')
```

## Evidence Collection

Track verified facts vs agent claims.

### Manual Collection

```python
from reliability import EvidenceCollector

collector = EvidenceCollector()

# From tool result (verified)
evidence = collector.from_tool_result("search_api", search_results)

# From database (verified)
evidence = collector.from_database_read("users_table", query_result)

# From API (verified)
evidence = collector.from_api_response("weather_api", api_response)

# From user input (verified)
evidence = collector.from_user_input(user_input)

# From agent output (claimed)
evidence = collector.from_agent_output("planner", plan_output)

# Get verified evidence only
verified = collector.get_verified_evidence()
print(f"Verified facts: {len(verified)}")
```

### Evidence in Decision Trails

```python
# Evidence is automatically collected in decision trails
trail = await trail_builder.build_trail(thread_id, checkpoint_id)

# Filter by confidence
verified = [e for e in trail.evidence if e.confidence == "verified"]
claimed = [e for e in trail.evidence if e.confidence == "claimed"]

# Audit trail
for evidence in verified:
    print(f"Fact from {evidence.source}: {evidence.content}")
```

## Circuit Breakers

Protect against failures in external dependencies.

### Basic Circuit Breaker

```python
from reliability import CircuitBreaker, CircuitBreakerConfig, CircuitState

# Create circuit breaker for external API
breaker = CircuitBreaker(
    name="external_api",
    config=CircuitBreakerConfig(
        failure_threshold=5,      # Open after 5 failures
        success_threshold=2,       # Close after 2 successes
        timeout_seconds=60         # Try again after 60s
    )
)

# Use circuit breaker
if breaker.can_execute():
    try:
        result = call_external_api()
        breaker.record_success()
    except Exception as e:
        breaker.record_failure()
        print(f"API call failed: {e}")
else:
    print("Circuit open - API unavailable")

# Check state
if breaker.state == CircuitState.OPEN:
    print("Circuit protecting system from failures")
elif breaker.state == CircuitState.HALF_OPEN:
    print("Circuit testing recovery")
else:
    print("Circuit closed - operating normally")
```

### Circuit Breaker Registry

Manage multiple circuit breakers:

```python
from reliability import CircuitBreakerRegistry

registry = CircuitBreakerRegistry()

# Get/create breakers
api_breaker = registry.get_breaker("external_api")
db_breaker = registry.get_breaker("database")
cache_breaker = registry.get_breaker("redis_cache")

# Check overall status
status = registry.get_status()
for name, state in status.items():
    print(f"{name}: {state}")

# Get open circuits
open_circuits = registry.get_open_breakers()
if open_circuits:
    print(f"Warning: {len(open_circuits)} circuits are open")
    for name in open_circuits:
        print(f"  - {name}")
```

## Cost Tracking

Monitor LLM and tool costs.

### Basic Cost Tracking

```python
from reliability import CostTracker, CostBudget

tracker = CostTracker()

# Set daily budget
budget = CostBudget(
    name="daily",
    total_limit=100.0,  # $100/day
    period_hours=24
)
tracker.set_budget(budget)

# Record LLM costs
tracker.record_llm_cost(
    agent="researcher",
    prompt_tokens=1000,
    completion_tokens=500,
    model="gpt-4",
    workflow_id="workflow-001"
)

# Record tool costs
tracker.record_tool_cost(
    agent="image_generator",
    tool_name="dall_e",
    cost=0.50,
    workflow_id="workflow-001"
)

# Check budget
if not tracker.is_within_budget():
    print("⚠️ Budget exceeded!")

# Get cost report
report = tracker.get_report()
print(f"Total cost: ${report.total_cost:.2f}")
print(f"Cost per workflow: ${report.cost_per_workflow:.2f}")
print(f"Average tokens per workflow: {report.tokens_per_workflow:.0f}")

# Get breakdown by agent
for agent, cost in report.cost_by_agent.items():
    print(f"{agent}: ${cost:.2f}")
```

## Anomaly Detection

Detect unusual patterns in metrics.

### Threshold-Based Detection

```python
from reliability import AnomalyDetector, AnomalyThreshold, Severity

detector = AnomalyDetector(min_baseline_samples=10)

# Configure thresholds
detector.add_threshold(AnomalyThreshold(
    metric_name="error_rate",
    max_value=0.10,  # Max 10% errors
    severity=Severity.HIGH
))

detector.add_threshold(AnomalyThreshold(
    metric_name="success_rate",
    min_value=0.95,  # Min 95% success
    severity=Severity.HIGH
))

# Record values
detector.record_value("error_rate", 0.05)
detector.record_value("success_rate", 0.98)

# Detect anomalies
anomalies = detector.detect_anomalies()

for anomaly in anomalies:
    print(f"{anomaly.severity.value}: {anomaly.metric_name}")
    print(f"  Current: {anomaly.current_value}")
    print(f"  Expected: {anomaly.expected_value}")
```

### Statistical Detection

```python
# Build baseline (normal operation)
for i in range(20):
    detector.record_value("latency", 100 + i)  # 100-120ms normal

# Record spike
detector.record_value("latency", 500)  # Anomaly!

# Detect
anomalies = detector.detect_anomalies()

from reliability import AnomalyType

spikes = [a for a in anomalies if a.type == AnomalyType.SUDDEN_SPIKE]
if spikes:
    print(f"Detected {len(spikes)} latency spikes")
```

## Alert System

Get notified of issues.

### Setup Alerts

```python
from reliability import AlertManager, AlertSeverity, CallbackAlertChannel

manager = AlertManager()

# Add custom alert handler
def send_to_slack(alert):
    print(f"🚨 ALERT: {alert.title}")
    print(f"Severity: {alert.severity.value}")
    print(f"Message: {alert.message}")
    # Send to Slack, PagerDuty, etc.

manager.add_channel("slack", CallbackAlertChannel(send_to_slack))

# Trigger metric alert
await manager.trigger_metric_alert(
    metric_name="error_rate",
    current_value=0.15,
    threshold=0.10,
    severity=AlertSeverity.WARNING
)

# Trigger anomaly alert
for anomaly in anomalies:
    await manager.trigger_anomaly_alert(anomaly)

# Get recent alerts
from datetime import datetime, timedelta

recent = manager.get_alerts(
    since=datetime.utcnow() - timedelta(hours=1),
    severity=AlertSeverity.HIGH
)

print(f"High-severity alerts in last hour: {len(recent)}")
```

## Trend Analysis

Identify degrading metrics over time.

### Detect Trends

```python
from reliability import TrendAnalyzer, TrendDirection
from datetime import datetime, timedelta

analyzer = TrendAnalyzer(min_data_points=10)

# Record values over time
base_time = datetime.utcnow()
for i in range(20):
    timestamp = base_time + timedelta(hours=i)
    value = 0.99 - (i * 0.01)  # Degrading trend
    analyzer.record_value("success_rate", value, timestamp)

# Analyze trend
trend = analyzer.analyze("success_rate")

if trend.direction == TrendDirection.DEGRADING:
    print("⚠️ Success rate degrading!")
    print(f"  Slope: {trend.slope}")
    print(f"  Confidence: {trend.confidence:.2%}")
    print(f"  Current: {trend.current_value:.2%}")
    print(f"  Predicted next: {trend.predicted_value:.2%}")
```

### Forecast Values

```python
# Forecast 24 hours ahead
forecast = analyzer.forecast("success_rate", hours_ahead=24)

for timestamp, predicted_value in forecast:
    print(f"{timestamp}: {predicted_value:.2%}")
```

### Predict Degradation

```python
# Check if will drop below threshold
degradation = analyzer.detect_degradation(
    "success_rate",
    threshold=0.90,
    forecast_hours=24
)

if degradation:
    print(f"⚠️ Will breach threshold in {degradation['hours_until_breach']:.1f} hours")
    print(f"Breach value: {degradation['breach_value']:.2%}")
```

## Storage Backends

### In-Memory Storage (Default)

```python
from reliability import ReliabilityMetrics, MemoryMetricStorage

# Default - data lost on restart
metrics = ReliabilityMetrics()
```

### SQL Storage

```python
from reliability import SQLMetricStorage, ReliabilityMetrics
from ia_modules.database import get_database

# Create database connection
db = get_database('postgresql://localhost/metrics')

# Use SQL storage
storage = SQLMetricStorage(db)
metrics = ReliabilityMetrics(storage=storage)

# Metrics persist to database
await metrics.record_step(...)
```

### Redis Storage

```python
from reliability import RedisMetricStorage, ReliabilityMetrics

# Create Redis storage
storage = RedisMetricStorage(
    redis_url="redis://localhost:6379",
    ttl_days=90  # Auto-cleanup after 90 days
)

metrics = ReliabilityMetrics(storage=storage)

# Metrics stored in Redis
await metrics.record_step(...)
```

## Best Practices

### 1. Track All Workflows

```python
# Record every step
await metrics.record_step(
    agent=agent_name,
    success=success,
    mode=actual_mode,
    declared_mode=expected_mode
)

# Record every workflow
await metrics.record_workflow(
    workflow_id=workflow_id,
    total_steps=step_count,
    total_retries=retry_count
)
```

### 2. Use Circuit Breakers for External Services

```python
# Create breakers for all external dependencies
registry = CircuitBreakerRegistry()

api_breaker = registry.get_breaker("external_api")
db_breaker = registry.get_breaker("database")

# Check before calling
if api_breaker.can_execute():
    result = call_api()
    api_breaker.record_success()
else:
    # Fallback or queue for later
    use_cached_data()
```

### 3. Set Cost Budgets

```python
# Monitor spend
tracker = CostTracker()
tracker.set_budget(CostBudget("daily", 100.0, 24))

# Check before expensive operations
if tracker.is_within_budget():
    await call_expensive_llm()
else:
    print("Budget exceeded - throttling")
```

### 4. Monitor Continuously

```python
# Regular health checks
async def monitor_health():
    report = await metrics.get_report()

    if not report.is_healthy():
        violations = report.get_violations()
        for v in violations:
            await alert_manager.trigger_metric_alert(...)

# Run every 5 minutes
```

### 5. Use Persistent Storage in Production

```python
# Development - in-memory
if ENV == "dev":
    metrics = ReliabilityMetrics()

# Production - SQL
else:
    db = get_database(DATABASE_URL)
    storage = SQLMetricStorage(db)
    metrics = ReliabilityMetrics(storage=storage)
```

## Complete Example

```python
import asyncio
from reliability import (
    ReliabilityMetrics,
    CircuitBreakerRegistry,
    CostTracker,
    CostBudget,
    AnomalyDetector,
    AnomalyThreshold,
    Severity,
    AlertManager,
    CallbackAlertChannel
)

async def main():
    # Setup
    metrics = ReliabilityMetrics()
    breakers = CircuitBreakerRegistry()
    cost_tracker = CostTracker()
    detector = AnomalyDetector()
    alerts = AlertManager()

    # Configure
    cost_tracker.set_budget(CostBudget("daily", 100.0, 24))
    detector.add_threshold(AnomalyThreshold("error_rate", max_value=0.10, severity=Severity.HIGH))
    alerts.add_channel("log", CallbackAlertChannel(lambda a: print(f"Alert: {a.title}")))

    # Execute workflow
    api_breaker = breakers.get_breaker("external_api")

    if api_breaker.can_execute() and cost_tracker.is_within_budget():
        try:
            # Do work
            result = await execute_workflow()

            # Record success
            await metrics.record_step("agent", True, "execute", "execute")
            cost_tracker.record_llm_cost("agent", 1000, 500, "gpt-4")
            api_breaker.record_success()

        except Exception as e:
            # Record failure
            await metrics.record_step("agent", False, "execute", "execute")
            api_breaker.record_failure()

    # Monitor
    report = await metrics.get_report()
    detector.record_value("error_rate", 1.0 - report.svr)

    if not report.is_healthy():
        print("⚠️ Health check failed:")
        for v in report.get_violations():
            print(f"  - {v}")

    anomalies = detector.detect_anomalies()
    for anomaly in anomalies:
        await alerts.trigger_anomaly_alert(anomaly)

asyncio.run(main())
```

## Documentation

- [Developer Guide](DEVELOPER_GUIDE.md) - API reference
- [Testing Guide](TESTING_GUIDE.md) - Testing patterns
- [Getting Started](GETTING_STARTED.md) - Quick start
