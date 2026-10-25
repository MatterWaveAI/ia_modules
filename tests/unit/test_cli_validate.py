"""
Tests for Pipeline Validation CLI

Tests comprehensive validation including:
- Structure validation
- Step validation
- Flow validation
- Template validation
- Error/warning reporting
"""

from ia_modules.cli.validate import (
    validate_pipeline,
    ValidationResult
)


class TestValidationResult:
    """Test ValidationResult data class"""

    def test_initial_state(self):
        """Test initial validation result state"""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.info == []

    def test_add_error(self):
        """Test adding error marks as invalid"""
        result = ValidationResult(is_valid=True)
        result.add_error("Test error")
        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test adding warning doesn't affect validity"""
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning")
        assert result.is_valid is True
        assert "Test warning" in result.warnings

    def test_add_info(self):
        """Test adding info message"""
        result = ValidationResult(is_valid=True)
        result.add_info("Test info")
        assert result.is_valid is True
        assert "Test info" in result.info

    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = ValidationResult(is_valid=False)
        result.add_error("Error 1")
        result.add_warning("Warning 1")
        result.add_info("Info 1")

        d = result.to_dict()
        assert d['is_valid'] is False
        assert d['errors'] == ["Error 1"]
        assert d['warnings'] == ["Warning 1"]
        assert d['info'] == ["Info 1"]


class TestStructureValidation:
    """Test basic pipeline structure validation"""

    def test_valid_minimal_pipeline(self):
        """Test minimal valid pipeline"""
        pipeline = {
            "name": "test_pipeline",
            "steps": [
                {
                    "name": "step1",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step"
                }
            ],
            "flow": {
                "start_at": "step1"
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_missing_name(self):
        """Test error when name is missing"""
        pipeline = {
            "steps": [],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("name" in error.lower() for error in result.errors)

    def test_missing_steps(self):
        """Test error when steps is missing"""
        pipeline = {
            "name": "test",
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("steps" in error.lower() for error in result.errors)

    def test_missing_flow(self):
        """Test error when flow is missing"""
        pipeline = {
            "name": "test",
            "steps": []
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("flow" in error.lower() for error in result.errors)

    def test_invalid_name_type(self):
        """Test error when name is not a string"""
        pipeline = {
            "name": 123,
            "steps": [],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("name" in error.lower() and "string" in error.lower() for error in result.errors)

    def test_empty_name(self):
        """Test error when name is empty"""
        pipeline = {
            "name": "   ",
            "steps": [],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("name" in error.lower() and "empty" in error.lower() for error in result.errors)

    def test_steps_not_list(self):
        """Test error when steps is not a list"""
        pipeline = {
            "name": "test",
            "steps": "not a list",
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("steps" in error.lower() and "list" in error.lower() for error in result.errors)

    def test_flow_not_dict(self):
        """Test error when flow is not a dict"""
        pipeline = {
            "name": "test",
            "steps": [],
            "flow": []
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("flow" in error.lower() and "object" in error.lower() for error in result.errors)

    def test_empty_steps_warning(self):
        """Test warning when steps list is empty"""
        pipeline = {
            "name": "test",
            "steps": [],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert any("no steps" in warning.lower() for warning in result.warnings)


class TestStepValidation:
    """Test step definition validation"""

    def test_valid_step(self):
        """Test valid step definition"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "valid_step",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step",
                    "config": {}
                }
            ],
            "flow": {"start_at": "valid_step"}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_step_missing_name(self):
        """Test error when step is missing name"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "module": "test.module",
                    "class": "TestStep"
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("missing 'name'" in error.lower() for error in result.errors)

    def test_duplicate_step_names(self):
        """Test error when step names are duplicated"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "test", "class": "Step1"},
                {"name": "step1", "module": "test", "class": "Step2"}
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("duplicate" in error.lower() and "step1" in error.lower() for error in result.errors)

    def test_invalid_step_name_format(self):
        """Test warning for invalid step name format"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step-with-dashes", "module": "test", "class": "Step"}
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert any("naming convention" in warning.lower() for warning in result.warnings)

    def test_step_missing_module(self):
        """Test error when step is missing module"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "class": "Step"}
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("missing 'module'" in error.lower() for error in result.errors)

    def test_step_missing_class(self):
        """Test error when step is missing class"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "test"}
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("missing 'class'" in error.lower() for error in result.errors)

    def test_invalid_step_config(self):
        """Test error when step config is not a dict"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "config": "not a dict"
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("config" in error.lower() and "object" in error.lower() for error in result.errors)

    def test_step_import_valid(self):
        """Test successful step module import"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step"
                }
            ],
            "flow": {"start_at": "step1"}
        }
        result = validate_pipeline(pipeline)
        assert any("importable" in info.lower() for info in result.info)

    def test_step_import_invalid(self):
        """Test error when step module cannot be imported"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "nonexistent.module",
                    "class": "Step"
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("cannot be imported" in error.lower() for error in result.errors)


class TestStepInputValidation:
    """Test step input definition validation"""

    def test_valid_inputs(self):
        """Test valid input definitions"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "inputs": [
                        {"name": "input1", "source": "{pipeline_input}"},
                        {"name": "input2", "source": "{parameters.param1}"}
                    ]
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        # Should not have input-related errors
        assert not any("input" in error.lower() and "must be" in error.lower() for error in result.errors)

    def test_inputs_not_list(self):
        """Test error when inputs is not a list"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "inputs": "not a list"
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        # A warning, not an error: the runner does not read step inputs
        assert any("inputs should be a list" in warning.lower() for warning in result.warnings)

    def test_input_missing_name(self):
        """Test error when input is missing name"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "inputs": [
                        {"source": "{pipeline_input}"}
                    ]
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("missing 'name'" in error.lower() for error in result.errors)

    def test_input_missing_source(self):
        """Test error when input is missing source"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "inputs": [
                        {"name": "input1"}
                    ]
                }
            ],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("missing 'source'" in error.lower() for error in result.errors)


class TestFlowValidation:
    """Test flow definition validation"""

    def test_valid_linear_flow(self):
        """Test valid linear flow with paths"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "step2", "module": "ia_modules.pipeline.core", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "step2"},
                    {"from_step": "step2", "to_step": "end_with_success"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_valid_graph_flow(self):
        """Test valid graph flow with transitions"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "step2", "module": "ia_modules.pipeline.core", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from": "step1", "to": "step2"},
                    {"from": "step2", "to": "end_success"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_missing_start_at(self):
        """Test error when start_at is missing"""
        pipeline = {
            "name": "test",
            "steps": [{"name": "step1", "module": "test", "class": "Step"}],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("start_at" in error.lower() for error in result.errors)

    def test_invalid_start_step(self):
        """Test error when start step doesn't exist"""
        pipeline = {
            "name": "test",
            "steps": [{"name": "step1", "module": "test", "class": "Step"}],
            "flow": {
                "start_at": "nonexistent_step"
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("not defined" in error.lower() for error in result.errors)

    def test_invalid_path_from_step(self):
        """Test error when path references undefined from_step"""
        pipeline = {
            "name": "test",
            "steps": [{"name": "step1", "module": "test", "class": "Step"}],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "nonexistent", "to_step": "step1"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("not defined" in error.lower() for error in result.errors)

    def test_invalid_path_to_step(self):
        """Test error when path references undefined to_step"""
        pipeline = {
            "name": "test",
            "steps": [{"name": "step1", "module": "test", "class": "Step"}],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "nonexistent"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("not defined" in error.lower() for error in result.errors)

    def test_no_paths_or_transitions_warning(self):
        """Test warning when flow has no paths or transitions"""
        pipeline = {
            "name": "test",
            "steps": [{"name": "step1", "module": "test", "class": "Step"}],
            "flow": {
                "start_at": "step1"
            }
        }
        result = validate_pipeline(pipeline)
        assert any("no 'paths' or 'transitions'" in warning.lower() for warning in result.warnings)

    def test_unreachable_steps(self):
        """Test warning for unreachable steps"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "test", "class": "Step"},
                {"name": "step2", "module": "test", "class": "Step"},
                {"name": "step3", "module": "test", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "step2"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert any("unreachable" in warning.lower() and "step3" in warning.lower() for warning in result.warnings)

    def test_cycle_detection(self):
        """Test warning for cycles in flow"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "test", "class": "Step"},
                {"name": "step2", "module": "test", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "step2"},
                    {"from_step": "step2", "to_step": "step1"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert any("cycle" in warning.lower() for warning in result.warnings)


class TestConditionValidation:
    """Test condition validation"""

    def test_valid_field_equals_condition(self):
        """Test valid field_equals condition"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "step2", "module": "ia_modules.pipeline.core", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {
                        "from_step": "step1",
                        "to_step": "step2",
                        "condition": {
                            "type": "field_equals",
                            "field": "status",
                            "value": "success"
                        }
                    }
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_condition_missing_type(self):
        """Test error when condition is missing type"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "test", "class": "Step"},
                {"name": "step2", "module": "test", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {
                        "from_step": "step1",
                        "to_step": "step2",
                        "condition": {"field": "status"}
                    }
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("missing 'type'" in error.lower() for error in result.errors)

    def test_unknown_condition_type_warning(self):
        """Test warning for unknown condition type"""
        pipeline = {
            "name": "test",
            "steps": [
                {"name": "step1", "module": "test", "class": "Step"},
                {"name": "step2", "module": "test", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {
                        "from_step": "step1",
                        "to_step": "step2",
                        "condition": {"type": "unknown_type"}
                    }
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert any("unknown condition type" in warning.lower() for warning in result.warnings)


class TestTemplateValidation:
    """Test template reference validation"""

    def test_valid_parameter_reference(self):
        """Test valid parameter template reference"""
        pipeline = {
            "name": "test",
            "parameters": {
                "api_key": "test_key"
            },
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "config": {
                        "key": "{{ parameters.api_key }}"
                    }
                }
            ],
            "flow": {"start_at": "step1"}
        }
        result = validate_pipeline(pipeline)
        # Should not have warnings about undefined parameters
        assert not any("undefined parameter" in warning.lower() for warning in result.warnings)

    def test_undefined_parameter_reference(self):
        """Test warning for undefined parameter reference"""
        pipeline = {
            "name": "test",
            "parameters": {},
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "config": {
                        "key": "{{ parameters.nonexistent }}"
                    }
                }
            ],
            "flow": {"start_at": "step1"}
        }
        result = validate_pipeline(pipeline)
        assert any("undefined parameter" in warning.lower() for warning in result.warnings)

    def test_undefined_step_reference(self):
        """Test error for undefined step reference"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "test",
                    "class": "Step",
                    "inputs": [
                        {
                            "name": "input1",
                            "source": "{{ steps.nonexistent.output }}"
                        }
                    ]
                }
            ],
            "flow": {"start_at": "step1"}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("undefined step" in error.lower() for error in result.errors)

    def test_parameters_not_dict(self):
        """Test error when parameters is not a dict"""
        pipeline = {
            "name": "test",
            "parameters": "not a dict",
            "steps": [],
            "flow": {}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is False
        assert any("parameters" in error.lower() and "object" in error.lower() for error in result.errors)


class TestStrictMode:
    """Test strict mode validation"""

    def test_strict_mode_warnings_as_errors(self):
        """Test that strict mode treats warnings as errors"""
        pipeline = {
            "name": "test",
            "steps": [],
            "flow": {}
        }
        result = validate_pipeline(pipeline, strict=True)
        assert result.is_valid is False
        # Empty steps warning should become an error
        assert any("[STRICT]" in error for error in result.errors)

    def test_strict_mode_valid_pipeline(self):
        """Test that valid pipelines pass in strict mode"""
        pipeline = {
            "name": "test",
            "steps": [
                {
                    "name": "step1",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step"
                }
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "end_with_success"}
                ]
            }
        }
        result = validate_pipeline(pipeline, strict=True)
        assert result.is_valid is True


class TestComplexPipelines:
    """Test validation of complex pipeline scenarios"""

    def test_parallel_execution_pipeline(self):
        """Test pipeline with parallel execution"""
        pipeline = {
            "name": "parallel_test",
            "steps": [
                {"name": "step1", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "step2", "module": "ia_modules.pipeline.core", "class": "Step", "parallel": True},
                {"name": "step3", "module": "ia_modules.pipeline.core", "class": "Step", "parallel": True},
                {"name": "step4", "module": "ia_modules.pipeline.core", "class": "Step"}
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "step2"},
                    {"from_step": "step1", "to_step": "step3"},
                    {"from_step": "step2", "to_step": "step4"},
                    {"from_step": "step3", "to_step": "step4"}
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_error_handling_pipeline(self):
        """Test pipeline with error handling configuration"""
        pipeline = {
            "name": "error_test",
            "steps": [
                {
                    "name": "step1",
                    "module": "ia_modules.pipeline.core",
                    "class": "Step",
                    "config": {
                        "error_handling": {
                            "continue_on_error": True,
                            "enable_fallback": True,
                            "retry": {
                                "max_attempts": 3,
                                "initial_delay": 1.0
                            }
                        }
                    }
                }
            ],
            "flow": {"start_at": "step1"}
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True

    def test_conditional_routing_pipeline(self):
        """Test pipeline with complex conditional routing"""
        pipeline = {
            "name": "conditional_test",
            "steps": [
                {"name": "validate", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "process_success", "module": "ia_modules.pipeline.core", "class": "Step"},
                {"name": "process_failure", "module": "ia_modules.pipeline.core", "class": "Step"}
            ],
            "flow": {
                "start_at": "validate",
                "paths": [
                    {
                        "from": "validate",
                        "to": "process_success",
                        "condition": {
                            "type": "field_equals",
                            "field": "status",
                            "value": "valid"
                        }
                    },
                    {
                        "from": "validate",
                        "to": "process_failure",
                        "condition": {
                            "type": "field_equals",
                            "field": "status",
                            "value": "invalid"
                        }
                    }
                ]
            }
        }
        result = validate_pipeline(pipeline)
        assert result.is_valid is True
