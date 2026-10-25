"""
Integration tests for routing system with advanced features
"""


import pytest

from ia_modules.pipeline.routing import (
    RoutingContext,
    ExpressionConditionEvaluator,
    AdvancedRouter
)


@pytest.mark.asyncio
async def test_expression_condition_integration():
    """Test expression condition evaluation with real data"""
    # Test with simple comparison
    evaluator = ExpressionConditionEvaluator(
        source="pipeline_data.score",
        operator=">=",
        value=80
    )
    
    context = RoutingContext(
        pipeline_data={"score": 90},
        step_results={},
        current_step_id="test",
        execution_id="exec_123"
    )
    
    # This should return True since 90 >= 80
    result = await evaluator.evaluate(context)
    assert result is True


@pytest.mark.asyncio
async def test_expression_condition_false_integration():
    """Test expression condition evaluation with false result"""
    evaluator = ExpressionConditionEvaluator(
        source="pipeline_data.score",
        operator="<",
        value=80
    )
    
    context = RoutingContext(
        pipeline_data={"score": 90},
        step_results={},
        current_step_id="test",
        execution_id="exec_123"
    )
    
    # This should return False since 90 < 80 is false
    result = await evaluator.evaluate(context)
    assert result is False


@pytest.mark.asyncio
async def test_advanced_router_integration():
    """Test advanced router functionality with real paths"""
    router = AdvancedRouter()
    
    context = RoutingContext(
        pipeline_data={"score": 90},
        step_results={},
        current_step_id="step1",
        execution_id="exec_123"
    )
    
    # Test expression condition
    condition_config = {
        "source": "pipeline_data.score",
        "operator": ">=",
        "value": 80
    }
    
    result = await router.evaluate_condition("expression", condition_config, context)
    assert result is True


@pytest.mark.asyncio
async def test_router_find_next_steps():
    """Test finding next steps with conditions"""
    router = AdvancedRouter()
    
    context = RoutingContext(
        pipeline_data={"score": 90},
        step_results={},
        current_step_id="step1",
        execution_id="exec_123"
    )
    
    # Test with a simple path
    paths = [
        {
            "from": "step1",
            "to": "step2",
            "condition": {"type": "always"}
        }
    ]
    
    next_steps = await router.find_next_steps("step1", paths, context)
    assert len(next_steps) == 1
    assert next_steps[0] == "step2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
