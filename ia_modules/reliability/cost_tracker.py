"""
Cost tracking for agent operations.

Tracks LLM token costs, API costs, and tool execution costs to monitor
the financial efficiency of agent systems. Implements EARF FinOps metrics.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import logging


class CostCategory(Enum):
    """Categories of costs."""
    LLM_TOKENS = "llm_tokens"           # LLM API token costs
    TOOL_EXECUTION = "tool_execution"   # Tool/API execution costs
    STORAGE = "storage"                 # Storage costs
    COMPUTE = "compute"                 # Compute/infrastructure costs
    OTHER = "other"                     # Other costs


@dataclass
class CostEntry:
    """
    Record of a cost incurred.

    Attributes:
        category: Cost category
        amount: Cost in dollars
        quantity: Quantity of resource (e.g., tokens, API calls)
        unit_cost: Cost per unit
        timestamp: When cost was incurred
        agent: Agent that incurred cost
        workflow_id: Associated workflow (optional)
        context: Additional context
    """
    category: CostCategory
    amount: float
    quantity: int
    unit_cost: float
    timestamp: datetime
    agent: str
    workflow_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "amount": self.amount,
            "quantity": self.quantity,
            "unit_cost": self.unit_cost,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "workflow_id": self.workflow_id,
            "context": self.context
        }


@dataclass
class CostBudget:
    """
    Budget configuration for cost tracking.

    Attributes:
        name: Budget name
        total_limit: Total budget limit in dollars
        period_hours: Budget period in hours (None = unlimited)
        category_limits: Limits per cost category
        agent_limits: Limits per agent
        enabled: Whether budget is enabled
    """
    name: str
    total_limit: float
    period_hours: Optional[int] = None
    category_limits: Dict[CostCategory, float] = field(default_factory=dict)
    agent_limits: Dict[str, float] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class CostReport:
    """
    Cost report for a time period.

    Attributes:
        total_cost: Total cost in dollars
        total_workflows: Total workflows executed
        cost_per_workflow: Average cost per workflow (CPSW metric)
        tokens_per_workflow: Average tokens per workflow (TPW metric)
        by_category: Costs broken down by category
        by_agent: Costs broken down by agent
        period_start: Report period start
        period_end: Report period end
    """
    total_cost: float
    total_workflows: int
    cost_per_workflow: float  # CPSW - Cost Per Successful Workflow
    tokens_per_workflow: float  # TPW - Tokens Per Workflow
    by_category: Dict[str, float]
    by_agent: Dict[str, float]
    period_start: datetime
    period_end: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_cost": self.total_cost,
            "total_workflows": self.total_workflows,
            "cost_per_workflow": self.cost_per_workflow,
            "tokens_per_workflow": self.tokens_per_workflow,
            "by_category": self.by_category,
            "by_agent": self.by_agent,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat()
        }


class CostTracker:
    """
    Track costs for agent operations.

    Implements EARF FinOps metrics:
    - Tokens Per Workflow (TPW)
    - Cost Per Successful Workflow (CPSW)
    - Budget enforcement
    - Cost alerting

    Example:
        >>> tracker = CostTracker()
        >>>
        >>> # Set budget
        >>> budget = CostBudget(
        ...     name="monthly",
        ...     total_limit=1000.0,  # $1000/month
        ...     period_hours=720
        ... )
        >>> tracker.set_budget(budget)
        >>>
        >>> # Record LLM token cost
        >>> tracker.record_llm_cost(
        ...     agent="researcher",
        ...     prompt_tokens=1000,
        ...     completion_tokens=500,
        ...     model="gpt-4",
        ...     workflow_id="workflow-123"
        ... )
        >>>
        >>> # Check if within budget
        >>> if tracker.is_within_budget():
        ...     # Continue operations
        ...     pass
        >>> else:
        ...     # Alert and throttle
        ...     print("Budget exceeded!")
    """

    # Default LLM pricing (per 1K tokens)
    DEFAULT_PRICING = {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125}
    }

    def __init__(self):
        """Initialize cost tracker."""
        self._costs: List[CostEntry] = []
        self._budgets: Dict[str, CostBudget] = {}
        self._workflow_counts: Dict[str, int] = {}  # Track workflows per agent
        self._pricing = self.DEFAULT_PRICING.copy()
        self.logger = logging.getLogger("CostTracker")

    def set_budget(self, budget: CostBudget):
        """
        Set or update budget.

        Args:
            budget: Budget configuration
        """
        self._budgets[budget.name] = budget
        self.logger.info(f"Set budget '{budget.name}': ${budget.total_limit}")

    def remove_budget(self, name: str) -> bool:
        """
        Remove budget.

        Args:
            name: Budget name

        Returns:
            True if removed, False if not found
        """
        if name in self._budgets:
            del self._budgets[name]
            self.logger.info(f"Removed budget: {name}")
            return True
        return False

    def set_model_pricing(
        self,
        model: str,
        prompt_price: float,
        completion_price: float
    ):
        """
        Set custom pricing for LLM model.

        Args:
            model: Model name
            prompt_price: Price per 1K prompt tokens
            completion_price: Price per 1K completion tokens
        """
        self._pricing[model] = {
            "prompt": prompt_price,
            "completion": completion_price
        }
        self.logger.info(f"Set pricing for {model}: prompt=${prompt_price}, completion=${completion_price}")

    def record_llm_cost(
        self,
        agent: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "gpt-4",
        workflow_id: Optional[str] = None
    ):
        """
        Record LLM token cost.

        Args:
            agent: Agent name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            model: LLM model name
            workflow_id: Associated workflow
        """
        if model not in self._pricing:
            self.logger.warning(f"No pricing for model {model}, using gpt-4 pricing")
            model = "gpt-4"

        pricing = self._pricing[model]

        # Calculate cost
        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]
        total_cost = prompt_cost + completion_cost
        total_tokens = prompt_tokens + completion_tokens

        # Record cost
        entry = CostEntry(
            category=CostCategory.LLM_TOKENS,
            amount=total_cost,
            quantity=total_tokens,
            unit_cost=total_cost / total_tokens if total_tokens > 0 else 0,
            timestamp=datetime.now(timezone.utc),
            agent=agent,
            workflow_id=workflow_id,
            context={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            }
        )

        self._costs.append(entry)

        self.logger.debug(f"Recorded LLM cost: ${total_cost:.4f} ({total_tokens} tokens)")

    def record_tool_cost(
        self,
        agent: str,
        tool_name: str,
        cost: float,
        workflow_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Record tool execution cost.

        Args:
            agent: Agent name
            tool_name: Tool that was executed
            cost: Cost in dollars
            workflow_id: Associated workflow
            context: Additional context
        """
        entry = CostEntry(
            category=CostCategory.TOOL_EXECUTION,
            amount=cost,
            quantity=1,
            unit_cost=cost,
            timestamp=datetime.now(timezone.utc),
            agent=agent,
            workflow_id=workflow_id,
            context={
                "tool_name": tool_name,
                **(context or {})
            }
        )

        self._costs.append(entry)

        self.logger.debug(f"Recorded tool cost: ${cost:.4f} ({tool_name})")

    def record_workflow_completion(
        self,
        workflow_id: str,
        agent: str,
        success: bool
    ):
        """
        Record workflow completion for CPSW calculation.

        Args:
            workflow_id: Workflow ID
            agent: Agent name
            success: Whether workflow succeeded
        """
        if success:
            if agent not in self._workflow_counts:
                self._workflow_counts[agent] = 0
            self._workflow_counts[agent] += 1

    def get_report(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> CostReport:
        """
        Get cost report for time period.

        Args:
            since: Start of period (None = all time)
            until: End of period (None = now)

        Returns:
            CostReport with aggregated costs
        """
        if until is None:
            until = datetime.now(timezone.utc)

        if since is None:
            # Use earliest cost
            if self._costs:
                since = min(c.timestamp for c in self._costs)
            else:
                since = until

        # Filter costs to period
        period_costs = [
            c for c in self._costs
            if since <= c.timestamp <= until
        ]

        # Calculate totals
        total_cost: float = sum(c.amount for c in period_costs)

        # Count workflows in period
        workflows_in_period = set()
        for cost in period_costs:
            if cost.workflow_id:
                workflows_in_period.add(cost.workflow_id)

        total_workflows = len(workflows_in_period)

        # Calculate CPSW (Cost Per Successful Workflow)
        cost_per_workflow = total_cost / total_workflows if total_workflows > 0 else 0

        # Calculate TPW (Tokens Per Workflow)
        total_tokens = sum(
            c.quantity for c in period_costs
            if c.category == CostCategory.LLM_TOKENS
        )
        tokens_per_workflow = total_tokens / total_workflows if total_workflows > 0 else 0

        # Break down by category
        by_category = {}
        for category in CostCategory:
            category_cost = sum(
                c.amount for c in period_costs
                if c.category == category
            )
            if category_cost > 0:
                by_category[category.value] = category_cost

        # Break down by agent
        by_agent = {}
        for cost in period_costs:
            if cost.agent not in by_agent:
                by_agent[cost.agent] = 0
            by_agent[cost.agent] += cost.amount

        return CostReport(
            total_cost=total_cost,
            total_workflows=total_workflows,
            cost_per_workflow=cost_per_workflow,
            tokens_per_workflow=tokens_per_workflow,
            by_category=by_category,
            by_agent=by_agent,  # type: ignore[arg-type]
            period_start=since,
            period_end=until
        )

    def is_within_budget(
        self,
        budget_name: Optional[str] = None
    ) -> bool:
        """
        Check if within budget limits.

        Args:
            budget_name: Specific budget to check (None = check all)

        Returns:
            True if within budget, False if exceeded
        """
        budgets_to_check = (
            [self._budgets[budget_name]] if budget_name
            else list(self._budgets.values())
        )

        for budget in budgets_to_check:
            if not budget.enabled:
                continue

            # Determine period
            if budget.period_hours:
                since = datetime.now(timezone.utc) - timedelta(hours=budget.period_hours)
            else:
                since = None

            # Get costs for period
            report = self.get_report(since=since)

            # Check total limit
            if report.total_cost > budget.total_limit:
                self.logger.warning(
                    f"Budget '{budget.name}' exceeded: ${report.total_cost:.2f} > ${budget.total_limit:.2f}"
                )
                return False

            # Check category limits
            for category, limit in budget.category_limits.items():
                category_cost = report.by_category.get(category.value, 0)
                if category_cost > limit:
                    self.logger.warning(
                        f"Budget '{budget.name}' category {category.value} exceeded: "
                        f"${category_cost:.2f} > ${limit:.2f}"
                    )
                    return False

            # Check agent limits
            for agent, limit in budget.agent_limits.items():
                agent_cost = report.by_agent.get(agent, 0)
                if agent_cost > limit:
                    self.logger.warning(
                        f"Budget '{budget.name}' agent {agent} exceeded: "
                        f"${agent_cost:.2f} > ${limit:.2f}"
                    )
                    return False

        return True

    def get_budget_usage(
        self,
        budget_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get current budget usage.

        Args:
            budget_name: Budget name

        Returns:
            Dict with usage information
        """
        if budget_name not in self._budgets:
            return None

        budget = self._budgets[budget_name]

        # Determine period
        if budget.period_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=budget.period_hours)
        else:
            since = None

        report = self.get_report(since=since)

        return {
            "budget_name": budget_name,
            "total_limit": budget.total_limit,
            "total_used": report.total_cost,
            "total_remaining": budget.total_limit - report.total_cost,
            "usage_percent": (report.total_cost / budget.total_limit * 100) if budget.total_limit > 0 else 0,
            "within_budget": report.total_cost <= budget.total_limit,
            "period_hours": budget.period_hours,
            "report": report.to_dict()
        }

    def get_costs(
        self,
        since: Optional[datetime] = None,
        agent: Optional[str] = None,
        category: Optional[CostCategory] = None
    ) -> List[CostEntry]:
        """
        Retrieve cost entries with filtering.

        Args:
            since: Only return costs after this time
            agent: Filter by agent
            category: Filter by category

        Returns:
            Filtered list of cost entries
        """
        filtered = self._costs

        if since:
            filtered = [c for c in filtered if c.timestamp >= since]

        if agent:
            filtered = [c for c in filtered if c.agent == agent]

        if category:
            filtered = [c for c in filtered if c.category == category]

        return filtered

    def clear_costs(self):
        """Clear all cost entries."""
        self._costs.clear()
        self._workflow_counts.clear()
        self.logger.info("Cleared all costs")
