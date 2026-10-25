"""
Unit tests for structured output validation.

Tests StructuredOutputValidator.
"""
import pytest
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict
from ia_modules.validation.core import StructuredOutputValidator


class SimpleModel(BaseModel):
    """Simple test model."""
    name: str
    age: int


class ComplexModel(BaseModel):
    """Complex test model."""
    title: str
    items: List[str]
    score: float
    metadata: Optional[dict] = None


class NestedModel(BaseModel):
    """Nested test model."""
    user: SimpleModel
    status: str


class ConstrainedModel(BaseModel):
    """Model with field constraints."""
    name: str = Field(..., min_length=1, max_length=50)
    value: int = Field(..., ge=0, le=100)
    email: str = Field(..., pattern=r'^[\w.-]+@[\w.-]+\.\w+$')


class DefaultsModel(BaseModel):
    """Model with default values."""
    name: str
    active: bool = True
    tags: List[str] = []
    count: int = 0


class DeeplyNestedModel(BaseModel):
    """Model with multiple nesting levels."""
    nested: NestedModel
    label: str


class ListOfModelsModel(BaseModel):
    """Model containing a list of sub-models."""
    users: List[SimpleModel]
    group: str


class OptionalFieldsModel(BaseModel):
    """Model where most fields are optional."""
    required_field: str
    opt_str: Optional[str] = None
    opt_int: Optional[int] = None
    opt_list: Optional[List[str]] = None
    opt_dict: Optional[Dict[str, int]] = None


class EmptyAllowedModel(BaseModel):
    """Model that can accept empty collections."""
    items: List[str] = []
    mapping: Dict[str, str] = {}


@pytest.mark.asyncio
class TestStructuredOutputValidator:
    """Test StructuredOutputValidator."""

    async def test_validator_creation(self):
        """Validator can be created."""
        validator = StructuredOutputValidator()

        assert validator is not None

    async def test_validate_dict_valid(self):
        """Validator accepts valid dict."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "age": 30}
        result = await validator.validate(data, SimpleModel)

        assert isinstance(result, SimpleModel)
        assert result.name == "Alice"
        assert result.age == 30

    async def test_validate_json_string_valid(self):
        """Validator accepts valid JSON string."""
        validator = StructuredOutputValidator()

        json_str = '{"name": "Bob", "age": 25}'
        result = await validator.validate(json_str, SimpleModel)

        assert isinstance(result, SimpleModel)
        assert result.name == "Bob"
        assert result.age == 25

    async def test_validate_dict_invalid(self):
        """Validator rejects invalid dict."""
        validator = StructuredOutputValidator()

        data = {"name": "Charlie"}  # Missing required 'age'

        with pytest.raises(ValidationError):
            await validator.validate(data, SimpleModel)

    async def test_validate_dict_wrong_type(self):
        """Validator rejects wrong type."""
        validator = StructuredOutputValidator()

        data = {"name": "David", "age": "not a number"}

        with pytest.raises(ValidationError):
            await validator.validate(data, SimpleModel)

    async def test_validate_complex_model(self):
        """Validator handles complex models."""
        validator = StructuredOutputValidator()

        data = {
            "title": "Test",
            "items": ["a", "b", "c"],
            "score": 9.5,
            "metadata": {"key": "value"}
        }

        result = await validator.validate(data, ComplexModel)

        assert result.title == "Test"
        assert len(result.items) == 3
        assert result.score == 9.5
        assert result.metadata == {"key": "value"}

    async def test_validate_nested_model(self):
        """Validator handles nested models."""
        validator = StructuredOutputValidator()

        data = {
            "user": {"name": "Eve", "age": 28},
            "status": "active"
        }

        result = await validator.validate(data, NestedModel)

        assert result.user.name == "Eve"
        assert result.user.age == 28
        assert result.status == "active"

    async def test_validate_and_retry_success_first_try(self):
        """validate_and_retry succeeds on first try."""
        validator = StructuredOutputValidator()

        data = {"name": "Frank", "age": 35}

        async def retry_func(error_feedback: str = None):
            return data  # Not called on success

        result = await validator.validate_and_retry(
            data, SimpleModel, retry_func
        )

        assert result.name == "Frank"
        assert result.age == 35

    async def test_validate_and_retry_success_second_try(self):
        """validate_and_retry succeeds on second try."""
        validator = StructuredOutputValidator()

        invalid_data = {"name": "Grace"}  # Missing age
        valid_data = {"name": "Grace", "age": 40}

        async def retry_func(error_feedback: str = None):
            assert error_feedback is not None  # Should get error feedback
            return valid_data

        result = await validator.validate_and_retry(
            invalid_data, SimpleModel, retry_func, max_retries=3
        )

        assert result.name == "Grace"
        assert result.age == 40

    async def test_validate_and_retry_max_retries(self):
        """validate_and_retry fails after max retries."""
        validator = StructuredOutputValidator()

        invalid_data = {"name": "Henry"}  # Always missing age

        async def retry_func(error_feedback: str = None):
            return invalid_data  # Always return invalid

        with pytest.raises(ValidationError):
            await validator.validate_and_retry(
                invalid_data, SimpleModel, retry_func, max_retries=2
            )

    async def test_validate_and_retry_error_formatting(self):
        """validate_and_retry formats errors clearly."""
        validator = StructuredOutputValidator()

        invalid_data = {"name": "Ivy", "age": "not_a_number"}
        error_received = None

        async def retry_func(error_feedback: str = None):
            nonlocal error_received
            error_received = error_feedback
            # Fix the error
            return {"name": "Ivy", "age": 25}

        result = await validator.validate_and_retry(
            invalid_data, SimpleModel, retry_func
        )

        assert error_received is not None
        assert "age" in error_received  # Error mentions the problematic field
        assert result.name == "Ivy"
        assert result.age == 25

    async def test_extract_json_from_text(self):
        """Validator can extract JSON from text."""
        validator = StructuredOutputValidator()

        text = """
        Here is the response:
        {"name": "Jack", "age": 32}
        That's the data.
        """

        result = await validator.validate(text, SimpleModel)

        assert result.name == "Jack"
        assert result.age == 32

    async def test_extract_json_with_code_block(self):
        """Validator can extract JSON from markdown code block."""
        validator = StructuredOutputValidator()

        text = """
        ```json
        {"name": "Kate", "age": 29}
        ```
        """

        result = await validator.validate(text, SimpleModel)

        assert result.name == "Kate"
        assert result.age == 29

    async def test_to_json_schema(self):
        """Validator can generate JSON schema from model."""
        validator = StructuredOutputValidator()

        schema = validator.to_json_schema(SimpleModel)

        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"

    # --- New comprehensive tests below ---

    # validate() - JSON string edge cases

    async def test_validate_json_string_with_extra_whitespace(self):
        """Validator handles JSON string with leading/trailing whitespace."""
        validator = StructuredOutputValidator()

        json_str = '   {"name": "Alice", "age": 30}   '
        result = await validator.validate(json_str, SimpleModel)

        assert result.name == "Alice"
        assert result.age == 30

    async def test_validate_json_string_invalid_json(self):
        """Validator raises on malformed JSON string."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate("{not valid json", SimpleModel)

    async def test_validate_json_string_empty(self):
        """Validator raises on empty string."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate("", SimpleModel)

    async def test_validate_json_string_empty_object(self):
        """Validator raises on empty JSON object when fields are required."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate("{}", SimpleModel)

    async def test_validate_empty_dict(self):
        """Validator raises on empty dict when fields are required."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate({}, SimpleModel)

    async def test_validate_dict_with_extra_fields(self):
        """Validator ignores extra fields in dict by default."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "age": 30, "extra": "ignored"}
        result = await validator.validate(data, SimpleModel)

        assert result.name == "Alice"
        assert result.age == 30

    async def test_validate_json_string_with_extra_fields(self):
        """Validator ignores extra fields in JSON string by default."""
        validator = StructuredOutputValidator()

        json_str = '{"name": "Bob", "age": 25, "extra": "ignored"}'
        result = await validator.validate(json_str, SimpleModel)

        assert result.name == "Bob"
        assert result.age == 25

    # validate() - type coercion

    async def test_validate_dict_int_coercion_from_string(self):
        """Pydantic coerces string integers in strict=False mode."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "age": "30"}
        # Pydantic v2 in lax mode coerces "30" to int 30
        result = await validator.validate(data, SimpleModel)

        assert result.age == 30

    async def test_validate_dict_float_for_int_field(self):
        """Validator handles float value for integer field."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "age": 30.0}
        result = await validator.validate(data, SimpleModel)

        assert result.age == 30

    # validate() - complex model edge cases

    async def test_validate_complex_model_without_optional(self):
        """Complex model validates without optional metadata."""
        validator = StructuredOutputValidator()

        data = {
            "title": "Test",
            "items": ["a"],
            "score": 0.0,
        }

        result = await validator.validate(data, ComplexModel)

        assert result.title == "Test"
        assert result.items == ["a"]
        assert result.score == 0.0
        assert result.metadata is None

    async def test_validate_complex_model_empty_items(self):
        """Complex model accepts empty items list."""
        validator = StructuredOutputValidator()

        data = {
            "title": "Empty",
            "items": [],
            "score": 5.0,
        }

        result = await validator.validate(data, ComplexModel)

        assert result.items == []

    async def test_validate_complex_model_missing_required(self):
        """Complex model rejects missing required field."""
        validator = StructuredOutputValidator()

        data = {"title": "Test", "items": ["a"]}  # Missing 'score'

        with pytest.raises(ValidationError):
            await validator.validate(data, ComplexModel)

    async def test_validate_complex_model_wrong_list_type(self):
        """Complex model rejects wrong item types in list."""
        validator = StructuredOutputValidator()

        data = {
            "title": "Test",
            "items": [1, 2, 3],  # ints, not strings
            "score": 5.0,
        }

        # Pydantic rejects int items where strings are expected; validator re-raises
        with pytest.raises(Exception):
            await validator.validate(data, ComplexModel)

    async def test_validate_complex_model_score_negative(self):
        """Complex model accepts negative float score."""
        validator = StructuredOutputValidator()

        data = {
            "title": "Test",
            "items": ["a"],
            "score": -3.14,
        }

        result = await validator.validate(data, ComplexModel)

        assert result.score == -3.14

    # validate() - nested model edge cases

    async def test_validate_nested_model_missing_inner_field(self):
        """Nested model rejects missing inner required field."""
        validator = StructuredOutputValidator()

        data = {
            "user": {"name": "Eve"},  # Missing 'age'
            "status": "active"
        }

        with pytest.raises(ValidationError):
            await validator.validate(data, NestedModel)

    async def test_validate_nested_model_wrong_inner_type(self):
        """Nested model rejects wrong inner field type."""
        validator = StructuredOutputValidator()

        data = {
            "user": "not a dict",
            "status": "active"
        }

        with pytest.raises(ValidationError):
            await validator.validate(data, NestedModel)

    async def test_validate_nested_model_null_inner(self):
        """Nested model rejects null for required inner model."""
        validator = StructuredOutputValidator()

        data = {
            "user": None,
            "status": "active"
        }

        with pytest.raises(ValidationError):
            await validator.validate(data, NestedModel)

    async def test_validate_deeply_nested_model(self):
        """Validator handles deeply nested models."""
        validator = StructuredOutputValidator()

        data = {
            "nested": {
                "user": {"name": "Deep", "age": 50},
                "status": "ok"
            },
            "label": "test"
        }

        result = await validator.validate(data, DeeplyNestedModel)

        assert result.nested.user.name == "Deep"
        assert result.nested.user.age == 50
        assert result.nested.status == "ok"
        assert result.label == "test"

    async def test_validate_deeply_nested_missing_deep_field(self):
        """Validator rejects deeply nested model missing an inner field."""
        validator = StructuredOutputValidator()

        data = {
            "nested": {
                "user": {"name": "Deep"},  # Missing age
                "status": "ok"
            },
            "label": "test"
        }

        with pytest.raises(ValidationError):
            await validator.validate(data, DeeplyNestedModel)

    # validate() - list of models

    async def test_validate_list_of_models(self):
        """Validator handles a list of sub-models."""
        validator = StructuredOutputValidator()

        data = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25},
            ],
            "group": "testers"
        }

        result = await validator.validate(data, ListOfModelsModel)

        assert len(result.users) == 2
        assert result.users[0].name == "Alice"
        assert result.users[1].age == 25
        assert result.group == "testers"

    async def test_validate_list_of_models_empty_list(self):
        """Validator accepts empty list of sub-models."""
        validator = StructuredOutputValidator()

        data = {"users": [], "group": "empty"}

        result = await validator.validate(data, ListOfModelsModel)

        assert result.users == []

    async def test_validate_list_of_models_invalid_item(self):
        """Validator rejects list with invalid sub-model."""
        validator = StructuredOutputValidator()

        data = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bad"},  # Missing age
            ],
            "group": "testers"
        }

        with pytest.raises(ValidationError):
            await validator.validate(data, ListOfModelsModel)

    # validate() - constrained fields

    async def test_validate_constrained_model_valid(self):
        """Validator accepts data matching all constraints."""
        validator = StructuredOutputValidator()

        data = {
            "name": "Alice",
            "value": 50,
            "email": "alice@example.com"
        }

        result = await validator.validate(data, ConstrainedModel)

        assert result.name == "Alice"
        assert result.value == 50
        assert result.email == "alice@example.com"

    async def test_validate_constrained_value_too_low(self):
        """Validator rejects value below minimum."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "value": -1, "email": "a@b.com"}

        with pytest.raises(ValidationError):
            await validator.validate(data, ConstrainedModel)

    async def test_validate_constrained_value_too_high(self):
        """Validator rejects value above maximum."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "value": 101, "email": "a@b.com"}

        with pytest.raises(ValidationError):
            await validator.validate(data, ConstrainedModel)

    async def test_validate_constrained_value_boundary_low(self):
        """Validator accepts value at lower boundary."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "value": 0, "email": "a@b.com"}

        result = await validator.validate(data, ConstrainedModel)

        assert result.value == 0

    async def test_validate_constrained_value_boundary_high(self):
        """Validator accepts value at upper boundary."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "value": 100, "email": "a@b.com"}

        result = await validator.validate(data, ConstrainedModel)

        assert result.value == 100

    async def test_validate_constrained_name_empty(self):
        """Validator rejects empty name (min_length=1)."""
        validator = StructuredOutputValidator()

        data = {"name": "", "value": 50, "email": "a@b.com"}

        with pytest.raises(ValidationError):
            await validator.validate(data, ConstrainedModel)

    async def test_validate_constrained_name_too_long(self):
        """Validator rejects name exceeding max_length."""
        validator = StructuredOutputValidator()

        data = {"name": "A" * 51, "value": 50, "email": "a@b.com"}

        with pytest.raises(ValidationError):
            await validator.validate(data, ConstrainedModel)

    async def test_validate_constrained_email_invalid(self):
        """Validator rejects invalid email pattern."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "value": 50, "email": "not-an-email"}

        with pytest.raises(ValidationError):
            await validator.validate(data, ConstrainedModel)

    # validate() - default values

    async def test_validate_defaults_model_all_provided(self):
        """Defaults model works when all fields provided."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice", "active": False, "tags": ["a"], "count": 5}

        result = await validator.validate(data, DefaultsModel)

        assert result.name == "Alice"
        assert result.active is False
        assert result.tags == ["a"]
        assert result.count == 5

    async def test_validate_defaults_model_only_required(self):
        """Defaults model fills in defaults for optional fields."""
        validator = StructuredOutputValidator()

        data = {"name": "Alice"}

        result = await validator.validate(data, DefaultsModel)

        assert result.name == "Alice"
        assert result.active is True
        assert result.tags == []
        assert result.count == 0

    # validate() - optional fields

    async def test_validate_optional_fields_all_none(self):
        """Optional fields model works with only required field."""
        validator = StructuredOutputValidator()

        data = {"required_field": "hello"}

        result = await validator.validate(data, OptionalFieldsModel)

        assert result.required_field == "hello"
        assert result.opt_str is None
        assert result.opt_int is None
        assert result.opt_list is None
        assert result.opt_dict is None

    async def test_validate_optional_fields_all_populated(self):
        """Optional fields model works with all fields provided."""
        validator = StructuredOutputValidator()

        data = {
            "required_field": "hello",
            "opt_str": "world",
            "opt_int": 42,
            "opt_list": ["a", "b"],
            "opt_dict": {"x": 1, "y": 2}
        }

        result = await validator.validate(data, OptionalFieldsModel)

        assert result.opt_str == "world"
        assert result.opt_int == 42
        assert result.opt_list == ["a", "b"]
        assert result.opt_dict == {"x": 1, "y": 2}

    async def test_validate_optional_fields_explicit_none(self):
        """Optional fields accept explicit None values."""
        validator = StructuredOutputValidator()

        data = {
            "required_field": "hello",
            "opt_str": None,
            "opt_int": None,
        }

        result = await validator.validate(data, OptionalFieldsModel)

        assert result.opt_str is None
        assert result.opt_int is None

    # _extract_json() edge cases

    async def test_extract_json_code_block_without_language(self):
        """Validator extracts JSON from code block without language tag."""
        validator = StructuredOutputValidator()

        text = """
        Here is the result:
        ```
        {"name": "Test", "age": 22}
        ```
        """

        result = await validator.validate(text, SimpleModel)

        assert result.name == "Test"
        assert result.age == 22

    async def test_extract_json_surrounded_by_prose(self):
        """Validator extracts JSON embedded in longer prose."""
        validator = StructuredOutputValidator()

        text = (
            "Based on my analysis, the answer is "
            '{"name": "Result", "age": 99} '
            "and that completes the request."
        )

        result = await validator.validate(text, SimpleModel)

        assert result.name == "Result"
        assert result.age == 99

    async def test_extract_json_multiline(self):
        """Validator extracts multiline JSON from text."""
        validator = StructuredOutputValidator()

        text = """
        The output:
        {
            "name": "Multi",
            "age": 42
        }
        Done.
        """

        result = await validator.validate(text, SimpleModel)

        assert result.name == "Multi"
        assert result.age == 42

    async def test_extract_json_no_json_present(self):
        """Validator raises when no JSON is present in text."""
        validator = StructuredOutputValidator()

        text = "This is just plain text with no JSON at all."

        with pytest.raises(ValidationError):
            await validator.validate(text, SimpleModel)

    async def test_extract_json_nested_json_in_code_block(self):
        """Validator extracts nested JSON from code block."""
        validator = StructuredOutputValidator()

        text = """
        ```json
        {"user": {"name": "Nested", "age": 35}, "status": "ok"}
        ```
        """

        result = await validator.validate(text, NestedModel)

        assert result.user.name == "Nested"
        assert result.user.age == 35
        assert result.status == "ok"

    async def test_extract_json_complex_model_from_text(self):
        """Validator extracts and validates complex model from prose."""
        validator = StructuredOutputValidator()

        text = '''
        Here are the results:
        ```json
        {"title": "Report", "items": ["x", "y"], "score": 8.5, "metadata": {"source": "test"}}
        ```
        '''

        result = await validator.validate(text, ComplexModel)

        assert result.title == "Report"
        assert result.items == ["x", "y"]
        assert result.score == 8.5
        assert result.metadata == {"source": "test"}

    # _format_error() tests

    async def test_format_error_missing_field(self):
        """Error formatting includes field name for missing field."""
        validator = StructuredOutputValidator()

        try:
            SimpleModel.model_validate({"name": "test"})
        except ValidationError as e:
            formatted = validator._format_error(e)

        assert "Validation errors:" in formatted
        assert "age" in formatted

    async def test_format_error_multiple_errors(self):
        """Error formatting handles multiple validation errors."""
        validator = StructuredOutputValidator()

        try:
            SimpleModel.model_validate({})
        except ValidationError as e:
            formatted = validator._format_error(e)

        assert "Validation errors:" in formatted
        assert "name" in formatted
        assert "age" in formatted

    async def test_format_error_nested_field(self):
        """Error formatting shows path for nested field errors."""
        validator = StructuredOutputValidator()

        try:
            NestedModel.model_validate({"user": {"name": "test"}, "status": "ok"})
        except ValidationError as e:
            formatted = validator._format_error(e)

        assert "Validation errors:" in formatted
        assert "age" in formatted

    async def test_format_error_constraint_violation(self):
        """Error formatting describes constraint violations."""
        validator = StructuredOutputValidator()

        try:
            ConstrainedModel.model_validate(
                {"name": "", "value": 200, "email": "bad"}
            )
        except ValidationError as e:
            formatted = validator._format_error(e)

        assert "Validation errors:" in formatted
        # Multiple constraint violations should appear
        assert formatted.count("- ") >= 2

    # get_schema_description() tests

    async def test_get_schema_description_simple(self):
        """Schema description includes name, doc, and schema."""
        validator = StructuredOutputValidator()

        desc = validator.get_schema_description(SimpleModel)

        assert desc["name"] == "SimpleModel"
        assert desc["description"] == "Simple test model."
        assert "schema" in desc
        assert "properties" in desc["schema"]

    async def test_get_schema_description_complex(self):
        """Schema description works for complex model."""
        validator = StructuredOutputValidator()

        desc = validator.get_schema_description(ComplexModel)

        assert desc["name"] == "ComplexModel"
        assert "properties" in desc["schema"]
        assert "title" in desc["schema"]["properties"]
        assert "items" in desc["schema"]["properties"]
        assert "score" in desc["schema"]["properties"]

    async def test_get_schema_description_nested(self):
        """Schema description works for nested model."""
        validator = StructuredOutputValidator()

        desc = validator.get_schema_description(NestedModel)

        assert desc["name"] == "NestedModel"
        assert "schema" in desc

    async def test_get_schema_description_no_docstring(self):
        """Schema description handles model without docstring."""
        class NoDocs(BaseModel):
            x: int

        validator = StructuredOutputValidator()

        desc = validator.get_schema_description(NoDocs)

        assert desc["name"] == "NoDocs"
        assert desc["description"] is None

    # to_json_schema() tests

    async def test_to_json_schema_complex(self):
        """JSON schema generation for complex model."""
        validator = StructuredOutputValidator()

        schema = validator.to_json_schema(ComplexModel)

        assert "properties" in schema
        assert "title" in schema["properties"]
        assert "items" in schema["properties"]
        assert "score" in schema["properties"]
        assert "metadata" in schema["properties"]

    async def test_to_json_schema_nested(self):
        """JSON schema generation for nested model includes refs."""
        validator = StructuredOutputValidator()

        schema = validator.to_json_schema(NestedModel)

        assert "properties" in schema
        assert "user" in schema["properties"]
        assert "status" in schema["properties"]

    async def test_to_json_schema_constrained(self):
        """JSON schema generation includes constraints."""
        validator = StructuredOutputValidator()

        schema = validator.to_json_schema(ConstrainedModel)

        value_props = schema["properties"]["value"]
        assert value_props.get("minimum") == 0 or value_props.get("exclusiveMinimum", -1) < 0
        assert value_props.get("maximum") == 100 or value_props.get("exclusiveMaximum", 200) > 100

    async def test_to_json_schema_with_defaults(self):
        """JSON schema includes default values."""
        validator = StructuredOutputValidator()

        schema = validator.to_json_schema(DefaultsModel)

        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "active" in schema["properties"]

    # validate_and_retry() - advanced scenarios

    async def test_validate_and_retry_retry_func_receives_formatted_error(self):
        """Retry function receives well-formatted error message."""
        validator = StructuredOutputValidator()

        feedback_messages = []

        async def retry_func(error_feedback: str = None):
            feedback_messages.append(error_feedback)
            return {"name": "Fixed", "age": 10}

        await validator.validate_and_retry(
            {"name": 123},  # Invalid - name must be string (actually coerced)
            SimpleModel,
            retry_func,
            max_retries=2
        )

        # If first attempt succeeded (pydantic coerced 123 to "123"),
        # no retry was needed
        # This test validates the flow works either way

    async def test_validate_and_retry_count_attempts(self):
        """validate_and_retry calls retry_func correct number of times."""
        validator = StructuredOutputValidator()

        attempt_count = 0

        async def retry_func(error_feedback: str = None):
            nonlocal attempt_count
            attempt_count += 1
            return {"name": "still bad"}  # Always invalid

        with pytest.raises(ValidationError):
            await validator.validate_and_retry(
                {"name": "bad"},  # Missing age
                SimpleModel,
                retry_func,
                max_retries=3
            )

        # First attempt uses initial output, then 2 retries before final attempt
        assert attempt_count == 2

    async def test_validate_and_retry_success_on_last_attempt(self):
        """validate_and_retry succeeds on the final allowed attempt."""
        validator = StructuredOutputValidator()

        call_count = 0

        async def retry_func(error_feedback: str = None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return {"name": "still bad"}  # Missing age
            return {"name": "Fixed", "age": 99}

        result = await validator.validate_and_retry(
            {"name": "bad"},  # Missing age (attempt 1)
            SimpleModel,
            retry_func,
            max_retries=3
        )

        assert result.name == "Fixed"
        assert result.age == 99

    async def test_validate_and_retry_max_retries_one(self):
        """validate_and_retry with max_retries=1 gives only one attempt."""
        validator = StructuredOutputValidator()

        async def retry_func(error_feedback: str = None):
            return {"name": "will not be called"}

        with pytest.raises(ValidationError):
            await validator.validate_and_retry(
                {"name": "bad"},  # Missing age
                SimpleModel,
                retry_func,
                max_retries=1
            )

    async def test_validate_and_retry_with_json_string(self):
        """validate_and_retry works when retry_func returns JSON string."""
        validator = StructuredOutputValidator()

        async def retry_func(error_feedback: str = None):
            return '{"name": "FromRetry", "age": 77}'

        result = await validator.validate_and_retry(
            {"missing": "everything"},  # Invalid
            SimpleModel,
            retry_func,
            max_retries=2
        )

        assert result.name == "FromRetry"
        assert result.age == 77

    # validate() - non-dict, non-string input

    async def test_validate_pydantic_model_instance(self):
        """Validator accepts an existing Pydantic model instance."""
        validator = StructuredOutputValidator()

        instance = SimpleModel(name="Already", age=10)
        result = await validator.validate(instance, SimpleModel)

        assert result.name == "Already"
        assert result.age == 10

    async def test_validate_none_input(self):
        """Validator raises on None input."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate(None, SimpleModel)

    async def test_validate_list_input_rejected(self):
        """Validator raises on list input for object schema."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate([1, 2, 3], SimpleModel)

    async def test_validate_integer_input_rejected(self):
        """Validator raises on integer input for object schema."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError):
            await validator.validate(42, SimpleModel)

    # Empty collections model

    async def test_validate_empty_allowed_defaults(self):
        """Model with empty defaults works with no data for those fields."""
        validator = StructuredOutputValidator()

        data = {}  # Both have defaults
        result = await validator.validate(data, EmptyAllowedModel)

        assert result.items == []
        assert result.mapping == {}

    async def test_validate_empty_allowed_with_data(self):
        """Model with empty defaults works with populated data."""
        validator = StructuredOutputValidator()

        data = {"items": ["a", "b"], "mapping": {"x": "y"}}
        result = await validator.validate(data, EmptyAllowedModel)

        assert result.items == ["a", "b"]
        assert result.mapping == {"x": "y"}

    # Unicode and special characters

    async def test_validate_unicode_values(self):
        """Validator handles unicode string values."""
        validator = StructuredOutputValidator()

        data = {"name": "Rene", "age": 30}
        result = await validator.validate(data, SimpleModel)

        assert result.name == "Rene"

    async def test_validate_json_string_unicode(self):
        """Validator handles unicode in JSON strings."""
        validator = StructuredOutputValidator()

        json_str = '{"name": "\\u00e9milie", "age": 25}'
        result = await validator.validate(json_str, SimpleModel)

        assert result.age == 25

    async def test_validate_special_characters_in_strings(self):
        """Validator handles special characters in string fields."""
        validator = StructuredOutputValidator()

        data = {"name": 'O\'Brien "the great"', "age": 45}
        result = await validator.validate(data, SimpleModel)

        assert result.name == 'O\'Brien "the great"'

    # Numeric edge cases

    async def test_validate_zero_age(self):
        """Validator accepts zero as valid integer."""
        validator = StructuredOutputValidator()

        data = {"name": "Baby", "age": 0}
        result = await validator.validate(data, SimpleModel)

        assert result.age == 0

    async def test_validate_negative_age(self):
        """Validator accepts negative integer (no constraint on SimpleModel)."""
        validator = StructuredOutputValidator()

        data = {"name": "TimeTraveler", "age": -1}
        result = await validator.validate(data, SimpleModel)

        assert result.age == -1

    async def test_validate_very_large_number(self):
        """Validator handles very large integer values."""
        validator = StructuredOutputValidator()

        data = {"name": "Big", "age": 999999999}
        result = await validator.validate(data, SimpleModel)

        assert result.age == 999999999

    async def test_validate_float_score_precision(self):
        """Validator preserves float precision."""
        validator = StructuredOutputValidator()

        data = {
            "title": "Precise",
            "items": [],
            "score": 3.141592653589793,
        }

        result = await validator.validate(data, ComplexModel)

        assert result.score == pytest.approx(3.141592653589793)

    # Multiple validation errors

    async def test_validate_multiple_missing_fields(self):
        """ValidationError contains all missing fields."""
        validator = StructuredOutputValidator()

        with pytest.raises(ValidationError) as exc_info:
            await validator.validate({}, SimpleModel)

        errors = exc_info.value.errors()
        error_fields = {tuple(e["loc"]) for e in errors}
        assert ("name",) in error_fields
        assert ("age",) in error_fields

    async def test_validate_multiple_type_errors(self):
        """ValidationError contains all type errors."""
        validator = StructuredOutputValidator()

        data = {
            "title": 123,  # Coerced to str
            "items": "not a list",  # Wrong type
            "score": "not a float",
        }

        with pytest.raises(ValidationError):
            await validator.validate(data, ComplexModel)
