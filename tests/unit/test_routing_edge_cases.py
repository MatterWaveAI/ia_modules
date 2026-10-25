"""
Edge case tests for pipeline/routing.py to improve coverage
"""

import pytest
from ia_modules.pipeline.routing import (
    RoutingContext,
    AgentConditionEvaluator,
    FunctionConditionEvaluator
)


class TestRoutingContextEdgeCases:
    """Test edge cases in RoutingContext"""

    def test_routing_context_with_all_fields(self):
        """Test RoutingContext with all fields populated"""
        context = RoutingContext(
            pipeline_data={"input": "test"},
            step_results={"step1": "result1"},
            current_step_id="step2",
            execution_id="exec-001",
            metadata={"user_id": "user-123"}
        )

        assert context.pipeline_data == {"input": "test"}
        assert context.step_results == {"step1": "result1"}
        assert context.current_step_id == "step2"
        assert context.execution_id == "exec-001"
        assert context.metadata == {"user_id": "user-123"}

    def test_routing_context_with_minimal_fields(self):
        """Test RoutingContext with only required fields"""
        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-002"
        )

        assert context.pipeline_data == {}
        assert context.step_results == {}
        assert context.metadata is None

    def test_routing_context_with_empty_metadata(self):
        """Test RoutingContext with explicitly empty metadata"""
        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-003",
            metadata={}
        )

        assert context.metadata == {}


class TestAgentConditionEvaluatorEdgeCases:
    """Test edge cases in AgentConditionEvaluator"""

    def test_agent_evaluator_initialization_defaults(self):
        """Test AgentConditionEvaluator with default parameters"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Should we proceed? {context}"
        )

        assert evaluator.model == "gpt-4"
        assert evaluator.context_fields == []
        assert evaluator.expected_outputs == ["yes", "no", "true", "false"]
        assert evaluator.confidence_threshold == 0.7
        assert evaluator.max_retries == 2

    def test_agent_evaluator_initialization_custom(self):
        """Test AgentConditionEvaluator with custom parameters"""
        evaluator = AgentConditionEvaluator(
            model="claude-3",
            prompt_template="Check this: {context}",
            context_fields=["field1", "field2"],
            expected_outputs=["approved", "rejected"],
            confidence_threshold=0.9,
            max_retries=5
        )

        assert evaluator.context_fields == ["field1", "field2"]
        assert evaluator.expected_outputs == ["approved", "rejected"]
        assert evaluator.confidence_threshold == 0.9
        assert evaluator.max_retries == 5

    @pytest.mark.asyncio
    async def test_agent_evaluator_successful_yes_response(self):
        """Test agent evaluator returning True for 'yes' response"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Proceed?"
        )

        context = RoutingContext(
            pipeline_data={"status": "good"},
            step_results={},
            current_step_id="step1",
            execution_id="exec-001"
        )

        # Default mock returns "yes" for non-error prompts
        result = await evaluator.evaluate(context)

        assert result is True

    @pytest.mark.asyncio
    async def test_agent_evaluator_successful_no_response(self):
        """Test agent evaluator returning False for 'no' response"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Is there an error in {context}?"
        )

        context = RoutingContext(
            pipeline_data={"error": "failure"},
            step_results={},
            current_step_id="step1",
            execution_id="exec-001"
        )

        # Mock returns "no" for prompts containing "error" or "fail"
        result = await evaluator.evaluate(context)

        assert result is False

    def test_build_agent_context_with_specific_fields(self):
        """Test _build_agent_context includes specified fields"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="test",
            context_fields=["field1", "field2"]
        )

        context = RoutingContext(
            pipeline_data={"field1": "value1", "field3": "value3"},
            step_results={"field2": "value2"},
            current_step_id="step1",
            execution_id="exec-001"
        )

        agent_context = evaluator._build_agent_context(context)

        assert agent_context["field1"] == "value1"
        assert agent_context["field2"] == "value2"
        assert "field3" not in agent_context  # Not in context_fields
        assert "current_step" in agent_context
        assert "execution_id" in agent_context
        assert "timestamp" in agent_context

    def test_build_agent_context_with_no_fields(self):
        """Test _build_agent_context includes all data when no fields specified"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="test"
        )

        context = RoutingContext(
            pipeline_data={"input": "test"},
            step_results={"step1": "result1"},
            current_step_id="step2",
            execution_id="exec-001"
        )

        agent_context = evaluator._build_agent_context(context)

        assert "step_results" in agent_context
        assert "pipeline_data" in agent_context
        assert agent_context["step_results"] == {"step1": "result1"}
        assert agent_context["pipeline_data"] == {"input": "test"}

    def test_parse_agent_response_yes_variations(self):
        """Test parsing various 'yes' responses"""
        evaluator = AgentConditionEvaluator(model="gpt-4", prompt_template="test")

        yes_responses = [
            {"response": "yes", "confidence": 0.9},
            {"response": "YES", "confidence": 0.9},
            {"response": "true", "confidence": 0.9},
            {"response": "True", "confidence": 0.9},
            {"response": "1", "confidence": 0.9},
            {"response": "proceed", "confidence": 0.9},
            {"response": "continue", "confidence": 0.9},
        ]

        for response in yes_responses:
            result = evaluator._parse_agent_response(response)
            assert result is True, f"Failed for response: {response['response']}"

    def test_parse_agent_response_no_variations(self):
        """Test parsing various 'no' responses"""
        evaluator = AgentConditionEvaluator(model="gpt-4", prompt_template="test")

        no_responses = [
            {"response": "no", "confidence": 0.9},
            {"response": "NO", "confidence": 0.9},
            {"response": "false", "confidence": 0.9},
            {"response": "False", "confidence": 0.9},
            {"response": "0", "confidence": 0.9},
            {"response": "stop", "confidence": 0.9},
            {"response": "halt", "confidence": 0.9},
        ]

        for response in no_responses:
            result = evaluator._parse_agent_response(response)
            assert result is False, f"Failed for response: {response['response']}"

    def test_parse_agent_response_low_confidence(self):
        """Test parsing rejects low confidence responses"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="test",
            confidence_threshold=0.8
        )

        response = {"response": "yes", "confidence": 0.5}

        with pytest.raises(ValueError, match="confidence.*below threshold"):
            evaluator._parse_agent_response(response)

    def test_parse_agent_response_unexpected_value(self):
        """Test parsing rejects unexpected response values"""
        evaluator = AgentConditionEvaluator(model="gpt-4", prompt_template="test")

        response = {"response": "maybe", "confidence": 0.9}

        with pytest.raises(ValueError, match="Unexpected agent response"):
            evaluator._parse_agent_response(response)

    def test_parse_agent_response_missing_response(self):
        """Test parsing handles missing response field"""
        evaluator = AgentConditionEvaluator(model="gpt-4", prompt_template="test")

        response = {"confidence": 0.9}

        with pytest.raises(ValueError, match="Unexpected agent response"):
            evaluator._parse_agent_response(response)

    def test_parse_agent_response_missing_confidence(self):
        """Test parsing handles missing confidence field"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="test",
            confidence_threshold=0.8
        )

        response = {"response": "yes"}  # No confidence field, defaults to 0.0

        with pytest.raises(ValueError, match="confidence.*below threshold"):
            evaluator._parse_agent_response(response)


class TestFunctionConditionEvaluatorEdgeCases:
    """Test edge cases in FunctionConditionEvaluator"""

    def test_function_evaluator_initialization_defaults(self):
        """Test FunctionConditionEvaluator with default parameters"""
        evaluator = FunctionConditionEvaluator(
            function_name="check_condition",
            module_path="my_module.conditions"
        )

        assert evaluator.function_name == "check_condition"
        assert evaluator.module_path == "my_module.conditions"
        assert evaluator.parameters == {}
        assert evaluator.timeout_seconds == 30
        assert evaluator._function is None

    def test_function_evaluator_initialization_custom(self):
        """Test FunctionConditionEvaluator with custom parameters"""
        custom_params = {"threshold": 0.9, "mode": "strict"}

        evaluator = FunctionConditionEvaluator(
            function_name="advanced_check",
            module_path="custom.validators",
            parameters=custom_params,
            timeout_seconds=60
        )

        assert evaluator.parameters == custom_params
        assert evaluator.timeout_seconds == 60

    def test_prepare_arguments(self):
        """Test _prepare_arguments creates correct structure"""
        params = {"key": "value"}
        evaluator = FunctionConditionEvaluator(
            function_name="test",
            module_path="test",
            parameters=params
        )

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-001"
        )

        args = evaluator._prepare_arguments(context)

        assert "context" in args
        assert "parameters" in args
        assert args["context"] == context
        assert args["parameters"] == params

    def test_prepare_arguments_with_empty_parameters(self):
        """Test _prepare_arguments with no parameters"""
        evaluator = FunctionConditionEvaluator(
            function_name="test",
            module_path="test"
        )

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-001"
        )

        args = evaluator._prepare_arguments(context)

        assert args["parameters"] == {}


class TestRoutingEdgeCasesIntegration:
    """Integration tests for routing edge cases"""

    @pytest.mark.asyncio
    async def test_agent_evaluator_with_empty_context(self):
        """Test agent evaluator with completely empty context"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Check: {context}"
        )

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="",
            execution_id=""
        )

        # Should still work with empty context
        result = await evaluator.evaluate(context)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_agent_evaluator_with_complex_context(self):
        """Test agent evaluator with nested complex data"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Analyze: {context}",
            context_fields=["nested_data"]
        )

        context = RoutingContext(
            pipeline_data={
                "nested_data": {
                    "level1": {
                        "level2": {
                            "value": 42
                        }
                    },
                    "array": [1, 2, 3]
                }
            },
            step_results={},
            current_step_id="step1",
            execution_id="exec-001"
        )

        result = await evaluator.evaluate(context)
        assert isinstance(result, bool)

    def test_routing_context_with_none_values(self):
        """Test RoutingContext handles None values appropriately"""
        context = RoutingContext(
            pipeline_data={"key": None},
            step_results={"step": None},
            current_step_id="step1",
            execution_id="exec-001",
            metadata=None
        )

        assert context.pipeline_data["key"] is None
        assert context.step_results["step"] is None
        assert context.metadata is None
