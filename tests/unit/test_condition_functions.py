"""
Unit tests for condition functions
"""

from unittest.mock import Mock

import pytest

from ia_modules.pipeline.condition_functions import (
    business_hours_condition,
    data_quality_condition,
    threshold_condition,
    error_rate_condition,
    regex_match_condition,
    cost_threshold_condition,
    approval_required_condition,
    retry_condition,
    load_balancing_condition,
    feature_flag_condition
)
from ia_modules.pipeline.routing import RoutingContext


def test_business_hours_condition():
    """Test business hours condition"""
    # Mock context with step results
    context = Mock(spec=RoutingContext)
    context.step_results = {}
    
    # Test with default parameters (should pass in normal business hours)
    parameters = {
        'timezone': 'UTC',
        'start_hour': 9,
        'end_hour': 17,
        'weekdays_only': True
    }
    
    result = business_hours_condition(context, parameters)
    # This will depend on actual time, so we just check it returns a boolean
    assert isinstance(result, bool)


def test_data_quality_condition():
    """Test data quality condition"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'field1': 'value1',
                'field2': 'value2',
                'error_count': 0,
                'total_records': 10
            }
        }
    }
    
    parameters = {
        'required_fields': ['field1', 'field2'],
        'min_completeness': 0.8,
        'max_error_rate': 0.1
    }
    
    result = data_quality_condition(context, parameters)
    assert isinstance(result, bool)


def test_threshold_condition():
    """Test threshold condition"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'score': 85
            }
        }
    }
    
    parameters = {
        'field_path': 'score',
        'operator': '>=',
        'threshold': 80
    }
    
    result = threshold_condition(context, parameters)
    assert isinstance(result, bool)


def test_error_rate_condition():
    """Test error rate condition"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {'error': 'some_error'}
        },
        'step2': {
            'result': {}
        }
    }
    
    parameters = {
        'max_error_rate': 0.5,
        'window_minutes': 60
    }
    
    result = error_rate_condition(context, parameters)
    assert isinstance(result, bool)


def test_regex_match_condition():
    """Test regex match condition"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'email': 'test@example.com'
            }
        }
    }
    
    parameters = {
        'field_path': 'email',
        'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    }
    
    result = regex_match_condition(context, parameters)
    assert isinstance(result, bool)


def test_cost_threshold_condition():
    """Test cost threshold condition"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'estimated_cost': 50.0
            }
        }
    }
    
    parameters = {
        'max_cost': 100.0,
        'cost_field': 'estimated_cost'
    }
    
    result = cost_threshold_condition(context, parameters)
    assert isinstance(result, bool)


def test_approval_required_condition():
    """Test approval required condition"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'risk_score': 0.8,
                'amount': 1500.0
            }
        }
    }
    
    parameters = {
        'risk_threshold': 0.7,
        'auto_approve_limit': 1000.0
    }
    
    result = approval_required_condition(context, parameters)
    assert isinstance(result, bool)


def test_load_balancing_condition():
    """Test load balancing condition"""
    context = Mock(spec=RoutingContext)
    context.execution_id = "test_execution_123"
    context.step_results = {}
    
    parameters = {
        'route_percentage': 50
    }
    
    result = load_balancing_condition(context, parameters)
    assert isinstance(result, bool)


def test_feature_flag_condition():
    """Test feature flag condition"""
    context = Mock(spec=RoutingContext)
    context.metadata = {
        'feature_flags': {
            'new_feature': True,
            'legacy_feature': False
        }
    }
    context.step_results = {}

    parameters = {
        'feature_name': 'new_feature',
        'default_value': False
    }

    result = feature_flag_condition(context, parameters)
    assert isinstance(result, bool)


# Additional tests for missing branches

def test_threshold_condition_all_operators():
    """Test threshold condition with all operators"""
    context = Mock(spec=RoutingContext)

    # Test ==
    context.step_results = {'step1': {'result': {'value': 10}}}
    assert threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '==', 'threshold': 10})
    assert not threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '==', 'threshold': 5})

    # Test !=
    assert threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '!=', 'threshold': 5})
    assert not threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '!=', 'threshold': 10})

    # Test >
    assert threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '>', 'threshold': 5})
    assert not threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '>', 'threshold': 15})

    # Test >=
    assert threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '>=', 'threshold': 10})
    assert not threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '>=', 'threshold': 15})

    # Test <
    assert threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '<', 'threshold': 15})
    assert not threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '<', 'threshold': 5})

    # Test <=
    assert threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '<=', 'threshold': 10})
    assert not threshold_condition(context, {'field_path': 'step1.result.value', 'operator': '<=', 'threshold': 5})

    # Test missing value (None)
    context.step_results = {'step1': {'result': {}}}
    assert not threshold_condition(context, {'field_path': 'step1.result.missing', 'operator': '>=', 'threshold': 10})


def test_retry_condition_scenarios():
    """Test retry condition with various scenarios"""
    context = Mock(spec=RoutingContext)
    context.current_step_id = 'step1'

    # Test: No retries yet, has retryable error
    context.step_results = {
        'step1': {
            'error': 'Connection failed',
            'error_type': 'timeout'
        }
    }
    parameters = {
        'max_retries': 3,
        'retry_on_errors': ['timeout', 'network_error']
    }
    assert retry_condition(context, parameters)

    # Test: Max retries reached
    context.step_results = {
        'step1': {'error': 'Connection failed', 'error_type': 'timeout'},
        'step1_retry_1': {'error': 'Still failing'},
        'step1_retry_2': {'error': 'Still failing'},
        'step1_retry_3': {'error': 'Still failing'}
    }
    assert not retry_condition(context, parameters)

    # Test: Error type not retryable
    context.step_results = {
        'step1': {
            'error': 'Invalid data',
            'error_type': 'validation_error'
        }
    }
    assert not retry_condition(context, parameters)

    # Test: No error (shouldn't retry)
    context.step_results = {
        'step1': {'result': 'success'}
    }
    assert not retry_condition(context, parameters)


def test_business_hours_condition_edge_cases():
    """Test business hours with different timezones and days"""
    context = Mock(spec=RoutingContext)
    context.step_results = {}

    # Test with different timezone
    parameters = {
        'timezone': 'America/New_York',
        'start_hour': 9,
        'end_hour': 17,
        'weekdays_only': True
    }
    result = business_hours_condition(context, parameters)
    assert isinstance(result, bool)

    # Test weekdays_only = False (weekends allowed)
    parameters['weekdays_only'] = False
    result = business_hours_condition(context, parameters)
    assert isinstance(result, bool)


def test_data_quality_condition_edge_cases():
    """Test data quality with missing fields and edge cases"""
    context = Mock(spec=RoutingContext)

    # Test: Missing required field
    context.step_results = {
        'step1': {
            'result': {
                'field1': 'value1'
                # field2 missing
            }
        }
    }
    parameters = {
        'required_fields': ['field1', 'field2'],
        'min_completeness': 0.9,
        'max_error_rate': 0.1
    }
    result = data_quality_condition(context, parameters)
    assert isinstance(result, bool)

    # Test: High error rate
    context.step_results = {
        'step1': {
            'result': {
                'field1': 'value1',
                'field2': 'value2',
                'error_count': 8,
                'total_records': 10
            }
        }
    }
    result = data_quality_condition(context, parameters)
    # Should fail due to high error rate
    assert not result


def test_regex_match_condition_no_match():
    """Test regex match when pattern doesn't match"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'email': 'not-an-email'
            }
        }
    }

    parameters = {
        'field_path': 'email',
        'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    }

    result = regex_match_condition(context, parameters)
    assert not result


def test_cost_threshold_exceeded():
    """Test cost threshold when cost exceeds limit"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'estimated_cost': 150.0
            }
        }
    }

    parameters = {
        'max_cost': 100.0,
        'cost_field': 'step1.result.estimated_cost'
    }

    result = cost_threshold_condition(context, parameters)
    assert not result


def test_approval_required_multiple_conditions():
    """Test approval required with various thresholds"""
    context = Mock(spec=RoutingContext)

    # Test: High risk, high amount - needs approval
    context.step_results = {
        'risk_score': 0.9,
        'amount': 5000.0
    }
    parameters = {
        'risk_threshold': 0.7,
        'auto_approve_limit': 1000.0
    }
    result = approval_required_condition(context, parameters)
    assert result

    # Test: Low risk, low amount - no approval needed
    context.step_results = {
        'risk_score': 0.3,
        'amount': 500.0
    }
    result = approval_required_condition(context, parameters)
    assert not result


def test_business_hours_weekend():
    """Test business hours on weekends"""
    context = Mock(spec=RoutingContext)
    context.step_results = {}

    parameters = {
        'timezone': 'UTC',
        'start_hour': 9,
        'end_hour': 17,
        'weekdays_only': True
    }

    # The result depends on actual date/time
    result = business_hours_condition(context, parameters)
    assert isinstance(result, bool)


def test_data_quality_empty_results():
    """Test data quality with no step results"""
    context = Mock(spec=RoutingContext)
    context.step_results = {}

    parameters = {
        'required_fields': ['field1'],
        'min_completeness': 0.9
    }

    result = data_quality_condition(context, parameters)
    assert not result


def test_error_rate_no_errors():
    """Test error rate when no errors present"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {'result': 'success'},
        'step2': {'result': 'success'},
        'step3': {'result': 'success'}
    }

    parameters = {
        'max_error_rate': 0.5
    }

    result = error_rate_condition(context, parameters)
    assert result


def test_error_rate_high_error_rate():
    """Test error rate when errors exceed threshold"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {'error': 'failed'},
        'step2': {'error': 'failed'},
        'step3': {'result': 'success'}
    }

    parameters = {
        'max_error_rate': 0.5
    }

    result = error_rate_condition(context, parameters)
    assert not result


def test_regex_invalid_pattern():
    """Test regex with invalid pattern"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'email': 'test@example.com'
    }

    parameters = {
        'field_path': 'email',
        'pattern': '[invalid(regex'  # Invalid regex
    }

    result = regex_match_condition(context, parameters)
    assert not result


def test_approval_required_high_amount_only():
    """Test approval required when only amount exceeds limit"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'risk_score': 0.3,  # Low risk
        'amount': 5000.0    # High amount
    }

    parameters = {
        'risk_threshold': 0.7,
        'auto_approve_limit': 1000.0
    }

    result = approval_required_condition(context, parameters)
    assert result


def test_extract_nested_value_empty_path():
    """Test _extract_nested_value with empty path"""
    from ia_modules.pipeline.condition_functions import _extract_nested_value

    result = _extract_nested_value({'key': 'value'}, '')
    assert result is None


def test_extract_nested_value_non_dict():
    """Test _extract_nested_value when encountering non-dict"""
    from ia_modules.pipeline.condition_functions import _extract_nested_value

    data = {'step1': 'string_value'}
    result = _extract_nested_value(data, 'step1.nested.field')
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
