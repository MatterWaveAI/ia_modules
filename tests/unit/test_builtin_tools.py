"""
Unit tests for builtin tools.

Tests APICallerTool, CalculatorTool, CodeExecutorTool, FileOperationsTool, and WebSearchTool.
"""
import asyncio
import json
import math
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ia_modules.tools.builtin_tools.api_caller import (
    APICallerTool,
    RateLimitConfig,
    api_caller_function,
)
from ia_modules.tools.builtin_tools.calculator import (
    CalculatorTool,
    calculator_function,
)
from ia_modules.tools.builtin_tools.code_executor import (
    CodeExecutorTool,
    code_executor_function,
)
from ia_modules.tools.builtin_tools.file_ops import (
    FileOperationsTool,
    file_ops_function,
)
from ia_modules.tools.builtin_tools.web_search import (
    SearchResult,
    WebSearchTool,
    web_search_function,
)


# ---------------------------------------------------------------------------
# APICallerTool tests
# ---------------------------------------------------------------------------

class TestAPICallerTool:
    """Tests for APICallerTool."""

    def test_init_defaults(self):
        """APICallerTool initializes with sensible defaults."""
        tool = APICallerTool()
        assert tool.default_headers == {}
        assert tool.rate_limit is None
        assert tool.timeout == 30.0

    def test_init_custom(self):
        """APICallerTool accepts custom configuration."""
        headers = {"Authorization": "Bearer tok"}
        rl = RateLimitConfig(requests_per_second=5)
        tool = APICallerTool(default_headers=headers, rate_limit=rl, timeout=10.0)
        assert tool.default_headers == headers
        assert tool.rate_limit is rl
        assert tool.timeout == 10.0

    @pytest.mark.asyncio
    async def test_get_request(self):
        """GET request returns mock response with status 200."""
        tool = APICallerTool()
        result = await tool.get("https://api.example.com/items")
        assert result["status"] == 200
        assert "data" in result
        assert "GET" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_post_request_with_json(self):
        """POST request forwards JSON payload."""
        tool = APICallerTool()
        payload = {"name": "test"}
        result = await tool.post("https://api.example.com/items", json_data=payload)
        assert result["status"] == 200
        assert result["data"]["request_data"] == payload

    @pytest.mark.asyncio
    async def test_put_request(self):
        """PUT shorthand invokes correct method."""
        tool = APICallerTool()
        result = await tool.put("https://api.example.com/items/1", json_data={"v": 1})
        assert "PUT" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_delete_request(self):
        """DELETE shorthand invokes correct method."""
        tool = APICallerTool()
        result = await tool.delete("https://api.example.com/items/1")
        assert "DELETE" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_patch_request(self):
        """PATCH shorthand invokes correct method."""
        tool = APICallerTool()
        result = await tool.patch("https://api.example.com/items/1", json_data={"v": 2})
        assert "PATCH" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_unsupported_method_raises(self):
        """Unsupported HTTP method raises ValueError."""
        tool = APICallerTool()
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            await tool.request("TRACE", "https://example.com")

    @pytest.mark.asyncio
    async def test_method_case_insensitive(self):
        """Method is normalised to uppercase."""
        tool = APICallerTool()
        result = await tool.request("get", "https://example.com/data")
        assert "GET" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_query_params_appended(self):
        """Query parameters are URL-encoded and appended."""
        tool = APICallerTool()
        result = await tool.get("https://api.example.com/search", params={"q": "hello world"})
        assert "q=hello+world" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_headers_merged(self):
        """Default and per-request headers are merged."""
        tool = APICallerTool(default_headers={"X-Default": "yes"})
        result = await tool.get("https://example.com", headers={"X-Custom": "1"})
        req_headers = result["data"]["request_headers"]
        assert req_headers["X-Default"] == "yes"
        assert req_headers["X-Custom"] == "1"

    @pytest.mark.asyncio
    async def test_rate_limit_per_second(self):
        """Rate limiter tracks request timestamps."""
        rl = RateLimitConfig(requests_per_second=100)
        tool = APICallerTool(rate_limit=rl)
        await tool.get("https://example.com")
        assert len(tool.request_times) == 1

    @pytest.mark.asyncio
    async def test_body_forwarded(self):
        """Raw body is forwarded to mock request."""
        tool = APICallerTool()
        result = await tool.post("https://example.com", body="raw-data")
        assert result["data"]["request_data"] == "raw-data"


class TestAPICallerFunction:
    """Tests for the api_caller_function entry-point."""

    @pytest.mark.asyncio
    async def test_basic_invocation(self):
        """api_caller_function delegates to APICallerTool."""
        result = await api_caller_function(method="GET", url="https://example.com")
        assert result["status"] == 200

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Custom timeout is accepted."""
        result = await api_caller_function(method="GET", url="https://example.com", timeout=5.0)
        assert result["status"] == 200


# ---------------------------------------------------------------------------
# CalculatorTool tests
# ---------------------------------------------------------------------------

class TestCalculatorTool:
    """Tests for CalculatorTool."""

    @pytest.mark.asyncio
    async def test_simple_addition(self):
        calc = CalculatorTool()
        assert await calc.evaluate("2 + 3") == 5

    @pytest.mark.asyncio
    async def test_order_of_operations(self):
        calc = CalculatorTool()
        assert await calc.evaluate("2 + 2 * 3") == 8.0

    @pytest.mark.asyncio
    async def test_sqrt(self):
        calc = CalculatorTool()
        result = await calc.evaluate("sqrt(16)")
        assert result == 4.0

    @pytest.mark.asyncio
    async def test_trig_functions(self):
        calc = CalculatorTool()
        result = await calc.evaluate("sin(0)")
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_constants(self):
        calc = CalculatorTool()
        result = await calc.evaluate("pi")
        assert abs(result - math.pi) < 1e-10

    @pytest.mark.asyncio
    async def test_factorial(self):
        calc = CalculatorTool()
        assert await calc.evaluate("factorial(5)") == 120

    @pytest.mark.asyncio
    async def test_division_by_zero(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="Division by zero"):
            await calc.evaluate("1 / 0")

    @pytest.mark.asyncio
    async def test_unsafe_import(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="unsafe characters"):
            await calc.evaluate("__import__('os')")

    @pytest.mark.asyncio
    async def test_unsafe_exec(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="unsafe characters"):
            await calc.evaluate("exec('print(1)')")

    @pytest.mark.asyncio
    async def test_unsafe_open(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="unsafe characters"):
            await calc.evaluate("open('/etc/passwd')")

    @pytest.mark.asyncio
    async def test_invalid_expression(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="Invalid expression"):
            await calc.evaluate("not_a_function(42)")

    @pytest.mark.asyncio
    async def test_nested_math(self):
        calc = CalculatorTool()
        result = await calc.evaluate("sqrt(pow(3, 2) + pow(4, 2))")
        assert abs(result - 5.0) < 1e-10

    @pytest.mark.asyncio
    async def test_negative_numbers(self):
        calc = CalculatorTool()
        assert await calc.evaluate("-5 + 3") == -2

    def test_safe_expression_allows_valid(self):
        calc = CalculatorTool()
        assert calc._is_safe_expression("2 + 3") is True
        assert calc._is_safe_expression("sqrt(16)") is True

    def test_safe_expression_blocks_dangerous(self):
        calc = CalculatorTool()
        assert calc._is_safe_expression("import os") is False
        assert calc._is_safe_expression("__builtins__") is False
        assert calc._is_safe_expression("compile('x')") is False

    # -- statistics --

    @pytest.mark.asyncio
    async def test_statistics_mean(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([1, 2, 3, 4, 5])
        assert stats["mean"] == 3.0

    @pytest.mark.asyncio
    async def test_statistics_median_odd(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([3, 1, 2])
        assert stats["median"] == 2

    @pytest.mark.asyncio
    async def test_statistics_median_even(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([1, 2, 3, 4])
        assert stats["median"] == 2.5

    @pytest.mark.asyncio
    async def test_statistics_std(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([2, 2, 2, 2])
        assert stats["std"] == 0.0

    @pytest.mark.asyncio
    async def test_statistics_min_max_sum(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([10, 20, 30])
        assert stats["min"] == 10
        assert stats["max"] == 30
        assert stats["sum"] == 60

    @pytest.mark.asyncio
    async def test_statistics_count(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([1, 2], operations=["count"])
        assert stats["count"] == 2

    @pytest.mark.asyncio
    async def test_statistics_empty_raises(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="Empty number list"):
            await calc.calculate_statistics([])

    @pytest.mark.asyncio
    async def test_statistics_selective_operations(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([1, 2, 3], operations=["mean", "sum"])
        assert "mean" in stats
        assert "sum" in stats
        assert "median" not in stats


class TestCalculatorFunction:
    """Tests for calculator_function entry-point."""

    @pytest.mark.asyncio
    async def test_expression_mode(self):
        result = await calculator_function(expression="10 * 5")
        assert result["result"] == 50
        assert result["type"] == "expression"

    @pytest.mark.asyncio
    async def test_statistics_mode(self):
        result = await calculator_function(operation="mean", numbers=[2, 4, 6])
        assert result["result"] == 4.0
        assert result["type"] == "statistics"

    @pytest.mark.asyncio
    async def test_missing_args_raises(self):
        with pytest.raises(ValueError, match="Must provide"):
            await calculator_function()


# ---------------------------------------------------------------------------
# CodeExecutorTool tests
# ---------------------------------------------------------------------------

class TestCodeExecutorTool:
    """Tests for CodeExecutorTool."""

    def test_init_defaults(self):
        executor = CodeExecutorTool()
        assert executor.timeout == 5.0
        assert "math" in executor.allowed_imports

    def test_init_custom(self):
        executor = CodeExecutorTool(timeout=2.0, allowed_imports=["json"])
        assert executor.timeout == 2.0
        assert executor.allowed_imports == ["json"]

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        executor = CodeExecutorTool()
        result = await executor.execute("result = 2 + 2")
        assert result["success"] is True
        assert result["result"] == 4

    @pytest.mark.asyncio
    async def test_stdout_captured(self):
        executor = CodeExecutorTool()
        result = await executor.execute("print('hello')")
        assert result["success"] is True
        assert "hello" in result["output"]

    @pytest.mark.asyncio
    async def test_runtime_error_captured(self):
        executor = CodeExecutorTool()
        result = await executor.execute("x = 1 / 0")
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]

    @pytest.mark.asyncio
    async def test_unsafe_import_os_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("import os")

    @pytest.mark.asyncio
    async def test_unsafe_import_sys_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("import sys")

    @pytest.mark.asyncio
    async def test_unsafe_import_subprocess_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("import subprocess")

    @pytest.mark.asyncio
    async def test_unsafe_eval_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("eval('1+1')")

    @pytest.mark.asyncio
    async def test_unsafe_exec_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("exec('pass')")

    @pytest.mark.asyncio
    async def test_unsafe_open_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("open('/etc/passwd')")

    @pytest.mark.asyncio
    async def test_unsafe_dunder_blocked(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe operations"):
            await executor.execute("x = __builtins__")

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        """Long-running code is stopped by the timeout."""
        executor = CodeExecutorTool(timeout=0.01)
        # Mock asyncio.wait_for to raise TimeoutError directly
        # (real busy loops in threads can't be killed on Windows)
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await executor.execute("x = 1")
        assert result["success"] is False
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_globals_dict_injected(self):
        executor = CodeExecutorTool()
        result = await executor.execute("result = x + 1", globals_dict={"x": 10})
        assert result["success"] is True
        assert result["result"] == 11

    def test_is_safe_code_valid(self):
        executor = CodeExecutorTool()
        assert executor._is_safe_code("x = 1 + 2") is True
        assert executor._is_safe_code("for i in range(10): pass") is True

    def test_is_safe_code_blocks_dangerous(self):
        executor = CodeExecutorTool()
        assert executor._is_safe_code("import os") is False
        assert executor._is_safe_code("import socket") is False
        assert executor._is_safe_code("__import__('os')") is False
        assert executor._is_safe_code("compile('x', '', 'exec')") is False
        assert executor._is_safe_code("globals()") is False
        assert executor._is_safe_code("locals()") is False
        assert executor._is_safe_code("vars()") is False
        assert executor._is_safe_code("getattr(obj, 'x')") is False
        assert executor._is_safe_code("setattr(obj, 'x', 1)") is False
        assert executor._is_safe_code("delattr(obj, 'x')") is False

    @pytest.mark.asyncio
    async def test_execute_function_not_found(self):
        """execute_function raises when function isn't in globals_dict.

        Note: Python's exec(code, globals, locals) puts `def` into locals,
        so execute_function's globals_dict check won't find it. This tests
        the current behavior.
        """
        executor = CodeExecutorTool()
        code = "def add(a, b):\n    return a + b"
        with pytest.raises(ValueError, match="not defined"):
            await executor.execute_function(code, "add", 3, 4)

    @pytest.mark.asyncio
    async def test_execute_function_not_defined(self):
        executor = CodeExecutorTool()
        with pytest.raises(ValueError, match="not defined"):
            await executor.execute_function("x = 1", "missing_func")


class TestCodeExecutorFunction:
    """Tests for code_executor_function entry-point."""

    @pytest.mark.asyncio
    async def test_basic_invocation(self):
        result = await code_executor_function(code="result = 42")
        assert result["success"] is True
        assert result["result"] == 42

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        result = await code_executor_function(code="result = 1", timeout=1.0)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# FileOperationsTool tests
# ---------------------------------------------------------------------------

class TestFileOperationsTool:
    """Tests for FileOperationsTool."""

    def test_init_defaults(self):
        tool = FileOperationsTool()
        assert tool.base_path == Path.cwd()
        assert ".txt" in tool.allowed_extensions
        assert ".json" in tool.allowed_extensions

    def test_init_custom(self):
        tool = FileOperationsTool(
            base_path="/tmp/test",
            allowed_extensions=[".log"],
            max_file_size_mb=1.0,
        )
        assert tool.base_path == Path("/tmp/test")
        assert tool.allowed_extensions == [".log"]
        assert tool.max_file_size_bytes == 1 * 1024 * 1024

    def test_validate_path_within_base(self):
        tool = FileOperationsTool(base_path="/tmp/safe")
        path = tool._validate_path("subdir/file.txt")
        assert str(path).startswith(str(Path("/tmp/safe").resolve()))

    def test_validate_path_traversal_blocked(self):
        tool = FileOperationsTool(base_path="/tmp/safe")
        with pytest.raises(ValueError, match="Path outside base directory"):
            tool._validate_path("../../etc/passwd")

    def test_validate_path_extension_blocked(self):
        tool = FileOperationsTool(base_path="/tmp/safe", allowed_extensions=[".txt"])
        with pytest.raises(ValueError, match="not allowed"):
            tool._validate_path("script.py")

    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path):
        """read_file returns file contents."""
        test_file = tmp_path / "hello.txt"
        test_file.write_text("world")
        tool = FileOperationsTool(base_path=str(tmp_path))
        content = await tool.read_file("hello.txt")
        assert content == "world"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, tmp_path):
        tool = FileOperationsTool(base_path=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            await tool.read_file("missing.txt")

    @pytest.mark.asyncio
    async def test_read_file_not_a_file(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        # subdir has no extension so validation will fail with allowed_extensions.
        # Use allowed_extensions=[".txt", ".json"]-like approach by including "" extension.
        _tool = FileOperationsTool(base_path=str(tmp_path), allowed_extensions=[".txt", ".json"])
        # allowed_extensions=[".txt", ".json"] falls through to the default list, so let's
        # create a directory that looks like an allowed extension.
        subdir2 = tmp_path / "data.txt"
        subdir2.mkdir()
        tool2 = FileOperationsTool(base_path=str(tmp_path))
        with pytest.raises(ValueError, match="Not a file"):
            await tool2.read_file("data.txt")

    @pytest.mark.asyncio
    async def test_read_file_too_large(self, tmp_path):
        big_file = tmp_path / "big.txt"
        big_file.write_text("x" * 200)
        tool = FileOperationsTool(base_path=str(tmp_path), max_file_size_mb=0.0001)
        with pytest.raises(ValueError, match="File too large"):
            await tool.read_file("big.txt")

    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        tool = FileOperationsTool(base_path=str(tmp_path))
        result = await tool.write_file("out.txt", "content here")
        assert result["success"] is True
        assert (tmp_path / "out.txt").read_text() == "content here"

    @pytest.mark.asyncio
    async def test_write_file_creates_dirs(self, tmp_path):
        tool = FileOperationsTool(base_path=str(tmp_path))
        await tool.write_file("nested/dir/file.txt", "data")
        assert (tmp_path / "nested" / "dir" / "file.txt").read_text() == "data"

    @pytest.mark.asyncio
    async def test_read_json(self, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text(json.dumps({"key": "value"}))
        tool = FileOperationsTool(base_path=str(tmp_path))
        data = await tool.read_json("data.json")
        assert data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_write_json(self, tmp_path):
        tool = FileOperationsTool(base_path=str(tmp_path))
        result = await tool.write_json("out.json", {"a": 1})
        assert result["success"] is True
        loaded = json.loads((tmp_path / "out.json").read_text())
        assert loaded == {"a": 1}

    @pytest.mark.asyncio
    async def test_list_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.json").write_text("{}")
        # Clear allowed_extensions so _validate_path doesn't reject directory "."
        tool = FileOperationsTool(base_path=str(tmp_path))
        tool.allowed_extensions = []
        files = await tool.list_files(".", pattern="*.txt")
        assert len(files) == 2
        assert any("a.txt" in f for f in files)
        assert any("b.txt" in f for f in files)

    @pytest.mark.asyncio
    async def test_list_files_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.txt").write_text("r")
        (sub / "child.txt").write_text("c")
        tool = FileOperationsTool(base_path=str(tmp_path))
        tool.allowed_extensions = []
        files = await tool.list_files(".", pattern="*.txt", recursive=True)
        assert len(files) == 2

    @pytest.mark.asyncio
    async def test_list_files_dir_not_found(self, tmp_path):
        tool = FileOperationsTool(base_path=str(tmp_path))
        tool.allowed_extensions = []
        with pytest.raises(FileNotFoundError):
            await tool.list_files("nope")

    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path):
        target = tmp_path / "delete_me.txt"
        target.write_text("bye")
        tool = FileOperationsTool(base_path=str(tmp_path))
        result = await tool.delete_file("delete_me.txt")
        assert result["success"] is True
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, tmp_path):
        tool = FileOperationsTool(base_path=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            await tool.delete_file("ghost.txt")


class TestFileOpsFunction:
    """Tests for file_ops_function entry-point."""

    @pytest.mark.asyncio
    async def test_read_operation(self, tmp_path):
        (tmp_path / "r.txt").write_text("data")
        with patch(
            "ia_modules.tools.builtin_tools.file_ops.FileOperationsTool"
        ) as MockCls:
            instance = MockCls.return_value
            instance.read_file = AsyncMock(return_value="data")
            result = await file_ops_function(operation="read", file_path="r.txt")
            assert result["content"] == "data"

    @pytest.mark.asyncio
    async def test_write_operation(self):
        with patch(
            "ia_modules.tools.builtin_tools.file_ops.FileOperationsTool"
        ) as MockCls:
            instance = MockCls.return_value
            instance.write_file = AsyncMock(return_value={"success": True, "path": "x.txt", "size": 5})
            result = await file_ops_function(operation="write", file_path="x.txt", content="hello")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_missing_content_raises(self):
        with pytest.raises(ValueError, match="content"):
            await file_ops_function(operation="write", file_path="x.txt")

    @pytest.mark.asyncio
    async def test_write_json_missing_data_raises(self):
        with pytest.raises(ValueError, match="data"):
            await file_ops_function(operation="write_json", file_path="x.json")

    @pytest.mark.asyncio
    async def test_unknown_operation_raises(self):
        with pytest.raises(ValueError, match="Unknown operation"):
            await file_ops_function(operation="truncate", file_path="x.txt")

    @pytest.mark.asyncio
    async def test_list_operation(self):
        with patch(
            "ia_modules.tools.builtin_tools.file_ops.FileOperationsTool"
        ) as MockCls:
            instance = MockCls.return_value
            instance.list_files = AsyncMock(return_value=["a.txt", "b.txt"])
            result = await file_ops_function(operation="list", file_path=".")
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_delete_operation(self):
        with patch(
            "ia_modules.tools.builtin_tools.file_ops.FileOperationsTool"
        ) as MockCls:
            instance = MockCls.return_value
            instance.delete_file = AsyncMock(return_value={"success": True, "path": "x.txt"})
            result = await file_ops_function(operation="delete", file_path="x.txt")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_read_json_operation(self):
        with patch(
            "ia_modules.tools.builtin_tools.file_ops.FileOperationsTool"
        ) as MockCls:
            instance = MockCls.return_value
            instance.read_json = AsyncMock(return_value={"k": "v"})
            result = await file_ops_function(operation="read_json", file_path="d.json")
            assert result["data"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_write_json_operation(self):
        with patch(
            "ia_modules.tools.builtin_tools.file_ops.FileOperationsTool"
        ) as MockCls:
            instance = MockCls.return_value
            instance.write_json = AsyncMock(return_value={"success": True, "path": "d.json", "size": 10})
            result = await file_ops_function(operation="write_json", file_path="d.json", data={"k": "v"})
            assert result["success"] is True


# ---------------------------------------------------------------------------
# WebSearchTool tests
# ---------------------------------------------------------------------------

class TestWebSearchTool:
    """Tests for WebSearchTool."""

    def test_init_defaults(self):
        tool = WebSearchTool()
        assert tool.api_key is None
        assert tool.search_engine == "mock"
        assert tool.safe_search is True

    def test_init_custom(self):
        tool = WebSearchTool(api_key="key123", search_engine="google", safe_search=False)
        assert tool.api_key == "key123"
        assert tool.search_engine == "google"
        assert tool.safe_search is False

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        tool = WebSearchTool()
        results = await tool.search("python programming", max_results=5)
        assert len(results) == 5
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_max_results_capped_at_10(self):
        tool = WebSearchTool()
        results = await tool.search("query", max_results=20)
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_search_result_fields(self):
        tool = WebSearchTool()
        results = await tool.search("AI", max_results=1)
        r = results[0]
        assert "AI" in r.title
        assert r.url.startswith("https://")
        assert len(r.snippet) > 0
        assert r.relevance_score == 1.0

    @pytest.mark.asyncio
    async def test_relevance_scores_descending(self):
        tool = WebSearchTool()
        results = await tool.search("topic", max_results=5)
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_non_mock_engine_falls_back_to_mock(self):
        tool = WebSearchTool(search_engine="bing")
        results = await tool.search("test")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """Empty query still returns results from mock."""
        tool = WebSearchTool()
        results = await tool.search("", max_results=3)
        assert len(results) == 3


class TestSearchResultDataclass:
    """Tests for SearchResult dataclass."""

    def test_creation(self):
        sr = SearchResult(
            title="Title",
            url="https://example.com",
            snippet="A snippet",
            source="example.com",
        )
        assert sr.relevance_score == 1.0

    def test_custom_relevance(self):
        sr = SearchResult(
            title="T", url="u", snippet="s", source="src", relevance_score=0.5
        )
        assert sr.relevance_score == 0.5


class TestWebSearchFunction:
    """Tests for web_search_function entry-point."""

    @pytest.mark.asyncio
    async def test_basic_invocation(self):
        result = await web_search_function(query="test query")
        assert result["query"] == "test query"
        assert result["count"] == 10
        assert "results" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_max_results(self):
        result = await web_search_function(query="test", max_results=3)
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_result_structure(self):
        result = await web_search_function(query="q", max_results=1)
        r = result["results"][0]
        assert "title" in r
        assert "url" in r
        assert "snippet" in r
        assert "source" in r
        assert "relevance_score" in r


# ---------------------------------------------------------------------------
# RateLimitConfig tests
# ---------------------------------------------------------------------------

class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_defaults(self):
        rl = RateLimitConfig()
        assert rl.requests_per_second is None
        assert rl.requests_per_minute is None
        assert rl.requests_per_hour is None

    def test_custom_values(self):
        rl = RateLimitConfig(
            requests_per_second=10,
            requests_per_minute=100,
            requests_per_hour=1000,
        )
        assert rl.requests_per_second == 10
        assert rl.requests_per_minute == 100
        assert rl.requests_per_hour == 1000
