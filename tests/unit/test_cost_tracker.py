"""Tests for cost tracking."""

from datetime import datetime, timedelta, timezone

from ia_modules.reliability.cost_tracker import (
    CostTracker,
    CostBudget,
    CostCategory,
    CostEntry
)


def test_cost_tracker_creation():
    """Test creating cost tracker."""
    tracker = CostTracker()

    assert len(tracker._costs) == 0
    assert len(tracker._budgets) == 0


def test_set_budget():
    """Test setting budget."""
    tracker = CostTracker()

    budget = CostBudget(
        name="monthly",
        total_limit=1000.0,
        period_hours=720
    )

    tracker.set_budget(budget)

    assert "monthly" in tracker._budgets
    assert tracker._budgets["monthly"].total_limit == 1000.0


def test_remove_budget():
    """Test removing budget."""
    tracker = CostTracker()

    budget = CostBudget(name="monthly", total_limit=1000.0)
    tracker.set_budget(budget)

    result = tracker.remove_budget("monthly")
    assert result is True
    assert "monthly" not in tracker._budgets

    # Try removing non-existent
    result = tracker.remove_budget("nonexistent")
    assert result is False


def test_set_model_pricing():
    """Test setting custom model pricing."""
    tracker = CostTracker()

    tracker.set_model_pricing("custom-model", 0.01, 0.02)

    assert "custom-model" in tracker._pricing
    assert tracker._pricing["custom-model"]["prompt"] == 0.01
    assert tracker._pricing["custom-model"]["completion"] == 0.02


def test_record_llm_cost():
    """Test recording LLM token cost."""
    tracker = CostTracker()

    tracker.record_llm_cost(
        agent="researcher",
        prompt_tokens=1000,
        completion_tokens=500,
        model="gpt-4"
    )

    assert len(tracker._costs) == 1
    cost = tracker._costs[0]

    assert cost.category == CostCategory.LLM_TOKENS
    assert cost.agent == "researcher"
    assert cost.quantity == 1500  # Total tokens
    assert cost.amount > 0


def test_record_llm_cost_calculation():
    """Test LLM cost calculation."""
    tracker = CostTracker()

    # GPT-4 pricing: $0.03 per 1K prompt, $0.06 per 1K completion
    tracker.record_llm_cost(
        agent="researcher",
        prompt_tokens=1000,
        completion_tokens=1000,
        model="gpt-4"
    )

    cost = tracker._costs[0]
    expected_cost = (1000 / 1000 * 0.03) + (1000 / 1000 * 0.06)  # $0.09

    assert abs(cost.amount - expected_cost) < 0.001


def test_record_tool_cost():
    """Test recording tool execution cost."""
    tracker = CostTracker()

    tracker.record_tool_cost(
        agent="executor",
        tool_name="api_call",
        cost=0.50
    )

    assert len(tracker._costs) == 1
    cost = tracker._costs[0]

    assert cost.category == CostCategory.TOOL_EXECUTION
    assert cost.agent == "executor"
    assert cost.amount == 0.50
    assert cost.context["tool_name"] == "api_call"


def test_record_workflow_completion():
    """Test recording workflow completion."""
    tracker = CostTracker()

    tracker.record_workflow_completion(
        workflow_id="workflow-123",
        agent="researcher",
        success=True
    )

    assert tracker._workflow_counts["researcher"] == 1


def test_get_report():
    """Test getting cost report."""
    tracker = CostTracker()

    # Record some costs
    tracker.record_llm_cost("researcher", 1000, 500, "gpt-4", "workflow-1")
    tracker.record_llm_cost("planner", 500, 250, "gpt-4", "workflow-1")
    tracker.record_tool_cost("executor", "api_call", 0.50, "workflow-1")

    report = tracker.get_report()

    assert report.total_cost > 0
    assert report.total_workflows == 1  # One unique workflow
    assert "llm_tokens" in report.by_category
    assert "tool_execution" in report.by_category
    assert "researcher" in report.by_agent


def test_get_report_with_time_filter():
    """Test getting cost report with time filter."""
    tracker = CostTracker()

    # Record cost in the past
    past_cost = CostEntry(
        category=CostCategory.LLM_TOKENS,
        amount=1.0,
        quantity=1000,
        unit_cost=0.001,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        agent="researcher"
    )
    tracker._costs.append(past_cost)

    # Record recent cost
    tracker.record_llm_cost("researcher", 1000, 500, "gpt-4")

    # Get report for last hour
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    tracker.get_report(since=since)

    # Should only include recent cost
    assert len([c for c in tracker._costs if c.timestamp >= since]) == 1


def test_cost_per_workflow():
    """Test CPSW (Cost Per Successful Workflow) calculation."""
    tracker = CostTracker()

    # Record costs for 2 workflows
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4", "workflow-1")
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4", "workflow-2")

    report = tracker.get_report()

    assert report.total_workflows == 2
    expected_cpsw = report.total_cost / 2
    assert abs(report.cost_per_workflow - expected_cpsw) < 0.001


def test_tokens_per_workflow():
    """Test TPW (Tokens Per Workflow) calculation."""
    tracker = CostTracker()

    # Record LLM costs
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4", "workflow-1")  # 1500 tokens
    tracker.record_llm_cost("agent1", 500, 250, "gpt-4", "workflow-2")   # 750 tokens

    report = tracker.get_report()

    assert report.total_workflows == 2
    expected_tpw = (1500 + 750) / 2
    assert abs(report.tokens_per_workflow - expected_tpw) < 0.1


def test_is_within_budget():
    """Test budget compliance check."""
    tracker = CostTracker()

    # Set budget
    budget = CostBudget(
        name="test",
        total_limit=1.0,  # $1 limit
        period_hours=24
    )
    tracker.set_budget(budget)

    # Record small cost (within budget)
    tracker.record_llm_cost("agent1", 100, 50, "gpt-4")

    assert tracker.is_within_budget() is True


def test_budget_exceeded():
    """Test budget exceeded detection."""
    tracker = CostTracker()

    # Set small budget
    budget = CostBudget(
        name="test",
        total_limit=0.01,  # Very small limit
        period_hours=24
    )
    tracker.set_budget(budget)

    # Record large cost (exceeds budget)
    tracker.record_llm_cost("agent1", 10000, 5000, "gpt-4")

    assert tracker.is_within_budget() is False


def test_category_budget_limit():
    """Test budget limits by category."""
    tracker = CostTracker()

    # Set budget with category limit
    budget = CostBudget(
        name="test",
        total_limit=100.0,
        category_limits={
            CostCategory.LLM_TOKENS: 0.01  # Very small LLM limit
        }
    )
    tracker.set_budget(budget)

    # Record LLM cost exceeding category limit
    tracker.record_llm_cost("agent1", 10000, 5000, "gpt-4")

    assert tracker.is_within_budget() is False


def test_agent_budget_limit():
    """Test budget limits by agent."""
    tracker = CostTracker()

    # Set budget with agent limit
    budget = CostBudget(
        name="test",
        total_limit=100.0,
        agent_limits={
            "researcher": 0.01  # Very small limit for researcher
        }
    )
    tracker.set_budget(budget)

    # Record cost for researcher exceeding limit
    tracker.record_llm_cost("researcher", 10000, 5000, "gpt-4")

    assert tracker.is_within_budget() is False


def test_get_budget_usage():
    """Test getting budget usage information."""
    tracker = CostTracker()

    budget = CostBudget(
        name="test",
        total_limit=10.0,
        period_hours=24
    )
    tracker.set_budget(budget)

    # Record some costs
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4")

    usage = tracker.get_budget_usage("test")

    assert usage is not None
    assert usage["budget_name"] == "test"
    assert usage["total_limit"] == 10.0
    assert usage["total_used"] > 0
    assert usage["total_remaining"] < 10.0
    assert 0 < usage["usage_percent"] < 100
    assert usage["within_budget"] is True


def test_get_costs_filtering():
    """Test retrieving costs with filters."""
    tracker = CostTracker()

    # Record costs for different agents and categories
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4")
    tracker.record_llm_cost("agent2", 500, 250, "gpt-4")
    tracker.record_tool_cost("agent1", "api_call", 0.50)

    # Filter by agent
    agent1_costs = tracker.get_costs(agent="agent1")
    assert len(agent1_costs) == 2

    # Filter by category
    llm_costs = tracker.get_costs(category=CostCategory.LLM_TOKENS)
    assert len(llm_costs) == 2

    tool_costs = tracker.get_costs(category=CostCategory.TOOL_EXECUTION)
    assert len(tool_costs) == 1


def test_get_costs_time_filter():
    """Test retrieving costs with time filter."""
    tracker = CostTracker()

    # Record old cost
    old_cost = CostEntry(
        category=CostCategory.LLM_TOKENS,
        amount=1.0,
        quantity=1000,
        unit_cost=0.001,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        agent="agent1"
    )
    tracker._costs.append(old_cost)

    # Record recent cost
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4")

    # Filter to recent costs
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_costs = tracker.get_costs(since=since)

    assert len(recent_costs) == 1


def test_clear_costs():
    """Test clearing all costs."""
    tracker = CostTracker()

    # Record some costs
    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4")
    tracker.record_tool_cost("agent1", "api_call", 0.50)

    assert len(tracker._costs) > 0

    tracker.clear_costs()

    assert len(tracker._costs) == 0


def test_cost_entry_to_dict():
    """Test converting cost entry to dictionary."""
    entry = CostEntry(
        category=CostCategory.LLM_TOKENS,
        amount=0.09,
        quantity=1500,
        unit_cost=0.00006,
        timestamp=datetime.now(timezone.utc),
        agent="researcher",
        workflow_id="workflow-123",
        context={"model": "gpt-4"}
    )

    data = entry.to_dict()

    assert data["category"] == "llm_tokens"
    assert data["amount"] == 0.09
    assert data["quantity"] == 1500
    assert data["agent"] == "researcher"
    assert data["workflow_id"] == "workflow-123"


def test_cost_report_to_dict():
    """Test converting cost report to dictionary."""
    tracker = CostTracker()

    tracker.record_llm_cost("agent1", 1000, 500, "gpt-4", "workflow-1")

    report = tracker.get_report()
    data = report.to_dict()

    assert "total_cost" in data
    assert "total_workflows" in data
    assert "cost_per_workflow" in data
    assert "tokens_per_workflow" in data
    assert "by_category" in data
    assert "by_agent" in data
