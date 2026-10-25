"""
Example Condition Functions for Phase 3 Function-based Routing

These functions demonstrate how to implement custom business logic
for pipeline routing decisions.
"""

from typing import Dict, Any
from datetime import datetime
import re

from .routing import RoutingContext


def business_hours_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Check if current time is within business hours"""
    parameters.get('timezone', 'UTC')
    start_hour = parameters.get('start_hour', 9)
    end_hour = parameters.get('end_hour', 17)
    weekdays_only = parameters.get('weekdays_only', True)

    now = datetime.now()

    # Check weekday if required
    if weekdays_only and now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Check hour range
    return start_hour <= now.hour < end_hour


def data_quality_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Evaluate data quality metrics for routing decisions"""
    required_fields = parameters.get('required_fields', [])
    min_completeness = parameters.get('min_completeness', 0.8)
    max_error_rate = parameters.get('max_error_rate', 0.1)

    # Get data from the latest step result
    step_results = context.step_results
    if not step_results:
        return False

    # Get the most recent step's output
    latest_step = max(step_results.keys())
    data = step_results[latest_step].get('result', {})

    # Check required fields
    missing_fields = 0
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing_fields += 1

    completeness = 1.0 - (missing_fields / len(required_fields)) if required_fields else 1.0

    # Check error indicators
    error_count = data.get('error_count', 0)
    total_records = data.get('total_records', 1)
    error_rate = error_count / total_records if total_records > 0 else 0

    return completeness >= min_completeness and error_rate <= max_error_rate


def threshold_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Generic threshold-based condition"""
    field_path = parameters.get('field_path', '')
    operator = parameters.get('operator', '>=')
    threshold = parameters.get('threshold', 0)

    # Extract value from context
    value = _extract_nested_value(context.step_results, field_path)

    if value is None:
        return False

    # Apply operator
    operators = {
        '==': lambda v, t: v == t,
        '!=': lambda v, t: v != t,
        '>': lambda v, t: v > t,
        '>=': lambda v, t: v >= t,
        '<': lambda v, t: v < t,
        '<=': lambda v, t: v <= t,
    }

    return operators.get(operator, operators['>='])(value, threshold)


def error_rate_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Check if error rate is below acceptable threshold"""
    max_error_rate = parameters.get('max_error_rate', 0.05)
    parameters.get('window_minutes', 60)

    # This would typically check error logs or metrics
    # For demonstration, we'll check step results for errors
    error_count = 0
    total_count = 0

    for step_id, result in context.step_results.items():
        if 'error' in result:
            error_count += 1
        total_count += 1

    if total_count == 0:
        return True

    current_error_rate = error_count / total_count
    return current_error_rate <= max_error_rate


def regex_match_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Check if a field matches a regular expression pattern"""
    field_path = parameters.get('field_path', '')
    pattern = parameters.get('pattern', '')
    flags = parameters.get('flags', 0)

    value = _extract_nested_value(context.step_results, field_path)

    if value is None:
        return False

    try:
        return bool(re.match(pattern, str(value), flags))
    except re.error:
        return False


def cost_threshold_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Route based on cost considerations"""
    max_cost = parameters.get('max_cost', 100.0)
    cost_field = parameters.get('cost_field', 'estimated_cost')

    cost = _extract_nested_value(context.step_results, cost_field)

    if cost is None:
        return True  # If no cost info, proceed

    return float(cost) <= max_cost


def approval_required_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Determine if human approval is required"""
    risk_threshold = parameters.get('risk_threshold', 0.7)
    auto_approve_limit = parameters.get('auto_approve_limit', 1000.0)

    # Check risk score
    risk_score = _extract_nested_value(context.step_results, 'risk_score')
    amount = _extract_nested_value(context.step_results, 'amount')

    if risk_score is not None and float(risk_score) > risk_threshold:
        return True  # High risk requires approval

    if amount is not None and float(amount) > auto_approve_limit:
        return True  # High amount requires approval

    return False  # Can proceed without approval


def retry_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Determine if a step should be retried"""
    max_retries = parameters.get('max_retries', 3)
    retry_on_errors = parameters.get('retry_on_errors', ['timeout', 'network_error'])

    # Count previous attempts for current step
    current_step = context.current_step_id
    retry_count = 0

    for step_id, result in context.step_results.items():
        if step_id.startswith(f"{current_step}_retry_"):
            retry_count += 1

    if retry_count >= max_retries:
        return False

    # Check if last execution had a retryable error
    last_result = context.step_results.get(current_step, {})
    if 'error' in last_result:
        error_type = last_result.get('error_type', '')
        return error_type in retry_on_errors

    return False


def load_balancing_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Simple load balancing based on hash of execution ID"""
    route_percentage = parameters.get('route_percentage', 50)  # 0-100

    # Use execution ID hash for consistent routing
    execution_hash = hash(context.execution_id) % 100

    return execution_hash < route_percentage


def feature_flag_condition(context: RoutingContext, parameters: Dict[str, Any]) -> bool:
    """Route based on feature flags"""
    feature_name = parameters.get('feature_name', '')
    default_value = parameters.get('default_value', False)

    # In a real implementation, this would check a feature flag service
    # For demonstration, we'll check pipeline metadata
    feature_flags = context.metadata.get('feature_flags', {}) if context.metadata else {}

    return feature_flags.get(feature_name, default_value)


def _extract_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Extract value from nested dictionary using dot notation"""
    if not path:
        return None

    parts = path.split('.')
    current = data

    try:
        for part in parts:
            if isinstance(current, dict):
                current = current[part]
            else:
                return None
        return current
    except (KeyError, TypeError):
        return None


# Example agent prompt templates for AI-based routing
AGENT_PROMPT_TEMPLATES = {
    "data_quality_assessment": """
Analyze the following pipeline data and determine if the data quality is sufficient to proceed:

Context:
{context}

Please evaluate:
1. Data completeness
2. Data accuracy indicators
3. Any error flags or warnings

Respond with 'yes' to proceed or 'no' to route to data cleaning step.
Provide your reasoning.
""",

    "risk_assessment": """
Based on the following transaction data, assess the risk level:

Context:
{context}

Consider:
1. Transaction amount
2. User behavior patterns
3. Geographical factors
4. Time of transaction

Respond with 'yes' for low risk (proceed) or 'no' for high risk (route to manual review).
""",

    "content_moderation": """
Review the following content for appropriateness:

Context:
{context}

Check for:
1. Inappropriate language
2. Spam indicators
3. Policy violations

Respond with 'yes' if content is appropriate (approve) or 'no' if it needs review.
""",

    "business_rule_evaluation": """
Evaluate whether the following business conditions are met:

Context:
{context}

Business Rules:
- Customer must be active
- Order amount within limits
- Inventory available

Respond with 'yes' if all conditions are met or 'no' if manual intervention is needed.
"""
}
