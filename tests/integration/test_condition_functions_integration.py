"""
Integration tests for condition functions with real scenarios
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


def test_business_hours_condition_integration():
    """Test business hours condition with real context"""
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


def test_data_quality_condition_integration():
    """Test data quality condition with real data"""
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


def test_threshold_condition_integration():
    """Test threshold condition with real data"""
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


def test_cost_threshold_condition_integration():
    """Test cost threshold condition with real data"""
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


def test_load_balancing_condition_integration():
    """Test load balancing condition with real execution ID"""
    context = Mock(spec=RoutingContext)
    context.execution_id = "test_execution_123"
    context.step_results = {}
    
    parameters = {
        'route_percentage': 50
    }
    
    result = load_balancing_condition(context, parameters)
    assert isinstance(result, bool)


def test_feature_flag_condition_integration():
    """Test feature flag condition with real metadata"""
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


def test_error_rate_condition_integration():
    """Test error rate condition with real data"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'error_count': 5,
                'total_count': 100
            }
        }
    }
    
    parameters = {
        'error_field': 'error_count',
        'total_field': 'total_count',
        'max_error_rate': 0.06
    }
    
    result = error_rate_condition(context, parameters)
    assert isinstance(result, bool)


def test_regex_match_condition_integration():
    """Test regex match condition with real data"""
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


def test_approval_required_condition_integration():
    """Test approval required condition with real data"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'approval_status': 'pending'
            }
        }
    }
    
    parameters = {
        'field_path': 'approval_status',
        'required_status': 'approved'
    }
    
    result = approval_required_condition(context, parameters)
    assert isinstance(result, bool)


def test_retry_condition_integration():
    """Test retry condition with real data"""
    context = Mock(spec=RoutingContext)
    context.step_results = {
        'step1': {
            'result': {
                'retry_count': 2,
                'max_retries': 3
            }
        }
    }
    # Set up the current_step_id attribute that's expected by retry_condition
    context.current_step_id = "test_step"
    
    parameters = {
        'retry_field': 'retry_count',
        'max_retries_field': 'max_retries'
    }
    
    result = retry_condition(context, parameters)
    assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
