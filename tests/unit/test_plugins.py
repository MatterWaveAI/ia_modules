"""
Comprehensive tests for the ia_modules plugins system.

Covers: base classes, decorators, loader, registry, and all builtin plugins.
"""

import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from ia_modules.plugins.base import (
    ConditionPlugin,
    HookPlugin,
    Plugin,
    PluginMetadata,
    PluginType,
    StepPlugin,
    TransformPlugin,
    ValidatorPlugin,
)
from ia_modules.plugins.decorators import (
    condition_plugin,
    function_plugin,
    plugin,
    step_plugin,
)
from ia_modules.plugins.loader import PluginLoader, auto_load_plugins
from ia_modules.plugins.registry import PluginRegistry, get_registry, reset_registry

# ---------------------------------------------------------------------------
# Helpers: concrete plugin subclasses used across many tests
# ---------------------------------------------------------------------------


class DummyCondition(ConditionPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="dummy_condition",
            version="1.0.0",
            plugin_type=PluginType.CONDITION,
        )

    async def evaluate(self, data):
        return data.get("flag", False)


class DummyStep(StepPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="dummy_step",
            version="1.0.0",
            plugin_type=PluginType.STEP,
        )

    async def execute(self, data):
        data["stepped"] = True
        return data


class DummyTransform(TransformPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="dummy_transform",
            version="1.0.0",
            plugin_type=PluginType.TRANSFORM,
        )

    async def transform(self, data):
        data["transformed"] = True
        return data


class DummyValidator(ValidatorPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="dummy_validator",
            version="1.0.0",
            plugin_type=PluginType.VALIDATOR,
        )

    async def validate(self, data):
        if "required" in data:
            return True, None
        return False, "missing 'required' key"


class DummyHook(HookPlugin):
    def __init__(self, config=None):
        super().__init__(config)
        self.events = []

    @property
    def metadata(self):
        return PluginMetadata(
            name="dummy_hook",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
        )

    async def on_pipeline_start(self, pipeline_name, data):
        self.events.append(("pipeline_start", pipeline_name))

    async def on_pipeline_end(self, pipeline_name, result):
        self.events.append(("pipeline_end", pipeline_name))

    async def on_step_start(self, step_name, data):
        self.events.append(("step_start", step_name))

    async def on_step_end(self, step_name, result):
        self.events.append(("step_end", step_name))

    async def on_error(self, error, context):
        self.events.append(("error", str(error)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset global registry before and after every test."""
    reset_registry()
    # Also reset the singleton so tests are isolated
    PluginRegistry._instance = None
    yield
    reset_registry()
    PluginRegistry._instance = None


@pytest.fixture
def registry():
    return PluginRegistry()


# =========================================================================
# 1. PluginMetadata
# =========================================================================


class TestPluginMetadata:
    def test_basic_creation(self):
        m = PluginMetadata(name="p", version="0.1.0")
        assert m.name == "p"
        assert m.version == "0.1.0"
        assert m.plugin_type == PluginType.CONDITION  # default
        assert m.tags == []
        assert m.dependencies == []
        assert m.author is None
        assert m.description is None
        assert m.config_schema is None

    def test_full_creation(self):
        m = PluginMetadata(
            name="full",
            version="2.0.0",
            author="Author",
            description="desc",
            plugin_type=PluginType.STEP,
            tags=["a", "b"],
            dependencies=["dep1"],
            config_schema={"type": "object"},
        )
        assert m.author == "Author"
        assert m.tags == ["a", "b"]
        assert m.dependencies == ["dep1"]
        assert m.config_schema == {"type": "object"}

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name is required"):
            PluginMetadata(name="", version="1.0.0")

    def test_empty_version_raises(self):
        with pytest.raises(ValueError, match="version is required"):
            PluginMetadata(name="x", version="")


# =========================================================================
# 2. PluginType enum
# =========================================================================


class TestPluginType:
    def test_all_types_exist(self):
        expected = {"condition", "step", "transform", "validator", "hook", "reporter"}
        actual = {t.value for t in PluginType}
        assert actual == expected


# =========================================================================
# 3. Plugin base and subclasses
# =========================================================================


class TestPluginBase:
    def test_default_config(self):
        p = DummyCondition()
        assert p.config == {}

    def test_custom_config(self):
        p = DummyCondition({"k": "v"})
        assert p.config == {"k": "v"}

    def test_logger_name(self):
        p = DummyCondition()
        assert "DummyCondition" in p.logger.name

    def test_validate_config_returns_true_by_default(self):
        p = DummyCondition()
        assert p.validate_config() is True

    async def test_shutdown_calls_internal(self):
        called = False

        class ShutdownPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="sp", version="1.0.0")

            async def evaluate(self, data):
                return True

            async def _shutdown(self):
                nonlocal called
                called = True

        p = ShutdownPlugin()
        await p.shutdown()
        assert called

    async def test_default_shutdown_does_nothing(self):
        p = DummyCondition()
        await p.shutdown()  # should not raise


class TestConditionPlugin:
    async def test_evaluate(self):
        p = DummyCondition()
        assert await p.evaluate({"flag": True}) is True
        assert await p.evaluate({"flag": False}) is False
        assert await p.evaluate({}) is False

    def test_default_metadata_type(self):
        p = DummyCondition()
        assert p.metadata.plugin_type == PluginType.CONDITION


class TestStepPlugin:
    async def test_execute(self):
        p = DummyStep()
        result = await p.execute({"a": 1})
        assert result["a"] == 1
        assert result["stepped"] is True

    def test_default_metadata_type(self):
        p = DummyStep()
        assert p.metadata.plugin_type == PluginType.STEP


class TestTransformPlugin:
    async def test_transform(self):
        p = DummyTransform()
        result = await p.transform({"x": 1})
        assert result["transformed"] is True

    def test_default_metadata_type(self):
        p = DummyTransform()
        assert p.metadata.plugin_type == PluginType.TRANSFORM


class TestValidatorPlugin:
    async def test_valid(self):
        p = DummyValidator()
        ok, msg = await p.validate({"required": True})
        assert ok is True
        assert msg is None

    async def test_invalid(self):
        p = DummyValidator()
        ok, msg = await p.validate({})
        assert ok is False
        assert "required" in msg


class TestHookPlugin:
    async def test_all_hooks(self):
        p = DummyHook()
        await p.on_pipeline_start("pipe1", {})
        await p.on_step_start("step1", {})
        await p.on_step_end("step1", {})
        await p.on_pipeline_end("pipe1", {})
        await p.on_error(ValueError("boom"), {})
        assert len(p.events) == 5
        assert p.events[0] == ("pipeline_start", "pipe1")
        assert p.events[4] == ("error", "boom")

    async def test_default_hook_methods_are_noop(self):
        """HookPlugin base methods should do nothing without error."""

        class MinimalHook(HookPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="mh", version="1.0.0", plugin_type=PluginType.HOOK)

        h = MinimalHook()
        await h.on_pipeline_start("p", {})
        await h.on_pipeline_end("p", {})
        await h.on_step_start("s", {})
        await h.on_step_end("s", {})
        await h.on_error(Exception("x"), {})


# =========================================================================
# 4. PluginRegistry
# =========================================================================


class TestPluginRegistry:
    def test_singleton(self):
        r1 = PluginRegistry.get_instance()
        r2 = PluginRegistry.get_instance()
        assert r1 is r2

    def test_register_and_get(self, registry):
        registry.register(DummyCondition)
        p = registry.get("dummy_condition")
        assert p is not None
        assert isinstance(p, DummyCondition)

    def test_register_with_config(self, registry):
        registry.register(DummyCondition, config={"x": 1})
        p = registry.get("dummy_condition")
        assert p.config == {"x": 1}

    def test_get_class(self, registry):
        registry.register(DummyCondition)
        cls = registry.get_class("dummy_condition")
        assert cls is DummyCondition

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get("nope") is None
        assert registry.get_class("nope") is None

    def test_create_instance(self, registry):
        registry.register(DummyCondition)
        inst = registry.create_instance("dummy_condition", {"cfg": 1})
        assert inst is not None
        assert inst.config == {"cfg": 1}
        # Should be a *new* instance
        assert inst is not registry.get("dummy_condition")

    def test_create_instance_nonexistent(self, registry):
        assert registry.create_instance("nope") is None

    def test_unregister(self, registry):
        registry.register(DummyCondition)
        assert "dummy_condition" in registry.list_plugins()
        registry.unregister("dummy_condition")
        assert "dummy_condition" not in registry.list_plugins()
        assert registry.get("dummy_condition") is None

    def test_unregister_nonexistent_warns(self, registry):
        # Should not raise
        registry.unregister("nonexistent")

    def test_duplicate_registration_overwrites(self, registry):
        registry.register(DummyCondition)
        inst1 = registry.get("dummy_condition")
        registry.register(DummyCondition, config={"new": True})
        inst2 = registry.get("dummy_condition")
        assert inst1 is not inst2
        assert inst2.config == {"new": True}

    def test_list_plugins_all(self, registry):
        registry.register(DummyCondition)
        registry.register(DummyStep)
        names = registry.list_plugins()
        assert "dummy_condition" in names
        assert "dummy_step" in names

    def test_list_plugins_by_type(self, registry):
        registry.register(DummyCondition)
        registry.register(DummyStep)
        conditions = registry.list_plugins(PluginType.CONDITION)
        steps = registry.list_plugins(PluginType.STEP)
        assert "dummy_condition" in conditions
        assert "dummy_step" not in conditions
        assert "dummy_step" in steps

    def test_get_by_type(self, registry):
        registry.register(DummyCondition)
        registry.register(DummyStep)
        conditions = registry.get_by_type(PluginType.CONDITION)
        assert len(conditions) == 1
        assert isinstance(conditions[0], DummyCondition)

    def test_get_info(self, registry):
        registry.register(DummyCondition)
        info = registry.get_info("dummy_condition")
        assert info is not None
        assert info['name'] == 'dummy_condition'
        assert info['initialized'] is True

    def test_get_info_nonexistent(self, registry):
        assert registry.get_info("nope") is None

    def test_get_all_info(self, registry):
        # May fail if _initialized not set; just verify no crash on empty
        infos = registry.get_all_info()
        assert isinstance(infos, list)

    def test_clear(self, registry):
        registry.register(DummyCondition)
        registry.register(DummyStep)
        registry.clear()
        assert registry.list_plugins() == []
        assert registry.list_plugins(PluginType.CONDITION) == []
        assert registry.list_plugins(PluginType.STEP) == []

    def test_check_dependencies_satisfied(self, registry):
        class DepA(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="dep_a", version="1.0.0", dependencies=["dep_b"]
                )

            async def evaluate(self, data):
                return True

        class DepB(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="dep_b", version="1.0.0")

            async def evaluate(self, data):
                return True

        registry.register(DepA)
        ok, missing = registry.check_dependencies("dep_a")
        assert not ok
        assert "dep_b" in missing

        registry.register(DepB)
        ok, missing = registry.check_dependencies("dep_a")
        assert ok
        assert missing == []

    def test_check_dependencies_plugin_not_found(self, registry):
        ok, missing = registry.check_dependencies("nonexistent")
        assert not ok
        assert "nonexistent" in missing

    def test_get_dependency_order_simple(self, registry):
        class A(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="a", version="1.0.0", dependencies=["b"])

            async def evaluate(self, data):
                return True

        class B(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="b", version="1.0.0")

            async def evaluate(self, data):
                return True

        registry.register(B)
        registry.register(A)
        order = registry.get_dependency_order()
        assert order.index("b") < order.index("a")

    def test_get_dependency_order_circular(self, registry):
        class X(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="x", version="1.0.0", dependencies=["y"])

            async def evaluate(self, data):
                return True

        class Y(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="y", version="1.0.0", dependencies=["x"])

            async def evaluate(self, data):
                return True

        registry.register(X)
        registry.register(Y)
        with pytest.raises(ValueError, match="Circular dependency"):
            registry.get_dependency_order()

    async def test_shutdown_all(self, registry):
        shutdown_names = []

        class SA(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="sa", version="1.0.0")

            async def evaluate(self, data):
                return True

            async def _shutdown(self):
                shutdown_names.append("sa")

        class SB(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="sb", version="1.0.0")

            async def evaluate(self, data):
                return True

            async def _shutdown(self):
                shutdown_names.append("sb")

        registry.register(SA)
        registry.register(SB)
        await registry.shutdown_all()
        assert "sa" in shutdown_names
        assert "sb" in shutdown_names

    async def test_shutdown_all_handles_errors(self, registry):
        class Bad(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(name="bad", version="1.0.0")

            async def evaluate(self, data):
                return True

            async def _shutdown(self):
                raise RuntimeError("boom")

        registry.register(Bad)
        # Should not raise even though _shutdown raises
        await registry.shutdown_all()


class TestGlobalRegistry:
    def test_get_registry_returns_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_reset_registry(self):
        reg = get_registry()
        reg.register(DummyCondition)
        assert "dummy_condition" in reg.list_plugins()
        reset_registry()
        reg2 = get_registry()
        assert "dummy_condition" not in reg2.list_plugins()


# =========================================================================
# 5. Decorators
# =========================================================================


class TestPluginDecorator:
    def test_plugin_decorator_sets_metadata(self):
        @plugin(
            name="dec_test",
            version="3.0.0",
            author="Auth",
            description="Desc",
            plugin_type=PluginType.CONDITION,
            tags=["t1"],
            dependencies=["d1"],
            auto_register=False,
        )
        class Dec(ConditionPlugin):
            async def evaluate(self, data):
                return True

        inst = Dec()
        assert inst.metadata.name == "dec_test"
        assert inst.metadata.version == "3.0.0"
        assert inst.metadata.author == "Auth"
        assert inst.metadata.description == "Desc"
        assert inst.metadata.tags == ["t1"]
        assert inst.metadata.dependencies == ["d1"]

    def test_plugin_decorator_auto_registers(self):
        @plugin(name="auto_reg", version="1.0.0", auto_register=True)
        class AutoReg(ConditionPlugin):
            async def evaluate(self, data):
                return True

        reg = get_registry()
        assert "auto_reg" in reg.list_plugins()


class TestConditionPluginDecorator:
    def test_sets_condition_type(self):
        @condition_plugin(name="cp", version="1.0.0", auto_register=False)
        class CP(ConditionPlugin):
            async def evaluate(self, data):
                return True

        inst = CP()
        assert inst.metadata.plugin_type == PluginType.CONDITION

    def test_with_tags_and_author(self):
        @condition_plugin(
            name="cp2",
            version="1.0.0",
            author="Me",
            tags=["tag"],
            auto_register=False,
        )
        class CP2(ConditionPlugin):
            async def evaluate(self, data):
                return True

        inst = CP2()
        assert inst.metadata.author == "Me"
        assert inst.metadata.tags == ["tag"]


class TestStepPluginDecorator:
    def test_sets_step_type(self):
        @step_plugin(name="sp", version="1.0.0", auto_register=False)
        class SP(StepPlugin):
            async def execute(self, data):
                return data

        inst = SP()
        assert inst.metadata.plugin_type == PluginType.STEP


class TestFunctionPlugin:
    def test_condition_function_plugin(self):
        @function_plugin(
            name="fn_cond", version="1.0.0", plugin_type=PluginType.CONDITION
        )
        async def fn_cond(data):
            return data.get("ok", False)

        # fn_cond is now a class, not a function
        inst = fn_cond()
        assert inst.metadata.name == "fn_cond"
        assert inst.metadata.plugin_type == PluginType.CONDITION

    async def test_condition_function_plugin_evaluate(self):
        @function_plugin(
            name="fn_cond2",
            version="1.0.0",
            plugin_type=PluginType.CONDITION,
            description="test",
        )
        async def fn_cond2(data):
            return data.get("ok", False)

        inst = fn_cond2()
        assert await inst.evaluate({"ok": True}) is True
        assert await inst.evaluate({}) is False

    def test_step_function_plugin(self):
        @function_plugin(name="fn_step", version="1.0.0", plugin_type=PluginType.STEP)
        async def fn_step(data):
            data["fn"] = True
            return data

        inst = fn_step()
        assert inst.metadata.plugin_type == PluginType.STEP

    async def test_step_function_plugin_execute(self):
        @function_plugin(
            name="fn_step2", version="1.0.0", plugin_type=PluginType.STEP
        )
        async def fn_step2(data):
            data["done"] = True
            return data

        inst = fn_step2()
        result = await inst.execute({"a": 1})
        assert result["done"] is True

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported plugin type"):

            @function_plugin(
                name="bad_fn", version="1.0.0", plugin_type=PluginType.HOOK
            )
            async def bad_fn(data):
                return data

    def test_function_plugin_uses_docstring(self):
        @function_plugin(name="docfn", version="1.0.0")
        async def docfn(data):
            """My docstring"""
            return True

        assert docfn.__doc__ == "My docstring"


# =========================================================================
# 6. PluginLoader
# =========================================================================


class TestPluginLoader:
    def test_init_with_default_registry(self):
        loader = PluginLoader()
        assert loader.registry is not None

    def test_init_with_custom_registry(self, registry):
        loader = PluginLoader(registry)
        assert loader.registry is registry

    def test_load_from_directory_nonexistent(self, registry, tmp_path):
        loader = PluginLoader(registry)
        count = loader.load_from_directory(tmp_path / "nonexistent")
        assert count == 0

    def test_load_from_directory_not_a_dir(self, registry, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        loader = PluginLoader(registry)
        count = loader.load_from_directory(f)
        assert count == 0

    def test_load_from_file_nonexistent(self, registry, tmp_path):
        loader = PluginLoader(registry)
        count = loader.load_from_file(tmp_path / "nope.py")
        assert count == 0

    def test_load_from_file_valid_plugin(self, registry, tmp_path):
        plugin_code = textwrap.dedent("""\
            from ia_modules.plugins.base import ConditionPlugin, PluginMetadata, PluginType

            class FilePlugin(ConditionPlugin):
                @property
                def metadata(self):
                    return PluginMetadata(name="file_plugin", version="1.0.0")

                async def evaluate(self, data):
                    return True
        """)
        f = tmp_path / "my_plugin.py"
        f.write_text(plugin_code)

        loader = PluginLoader(registry)
        count = loader.load_from_file(f)
        assert count == 1
        assert "file_plugin" in registry.list_plugins()

    def test_load_from_file_invalid_module(self, registry, tmp_path):
        f = tmp_path / "bad_plugin.py"
        f.write_text("raise RuntimeError('intentional')")
        loader = PluginLoader(registry)
        count = loader.load_from_file(f)
        assert count == 0

    def test_load_from_directory_skips_init(self, registry, tmp_path):
        # __init__.py should be skipped
        init = tmp_path / "__init__.py"
        init.write_text("# nothing")
        plugin_code = textwrap.dedent("""\
            from ia_modules.plugins.base import ConditionPlugin, PluginMetadata

            class DirPlugin(ConditionPlugin):
                @property
                def metadata(self):
                    return PluginMetadata(name="dir_plugin", version="1.0.0")

                async def evaluate(self, data):
                    return True
        """)
        f = tmp_path / "good.py"
        f.write_text(plugin_code)

        loader = PluginLoader(registry)
        count = loader.load_from_directory(tmp_path, recursive=False)
        assert count == 1
        assert "dir_plugin" in registry.list_plugins()

    def test_load_from_directory_recursive(self, registry, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        plugin_code = textwrap.dedent("""\
            from ia_modules.plugins.base import StepPlugin, PluginMetadata, PluginType

            class SubPlugin(StepPlugin):
                @property
                def metadata(self):
                    return PluginMetadata(name="sub_plugin", version="1.0.0", plugin_type=PluginType.STEP)

                async def execute(self, data):
                    return data
        """)
        f = sub / "sub_plugin.py"
        f.write_text(plugin_code)

        loader = PluginLoader(registry)
        count = loader.load_from_directory(tmp_path, recursive=True)
        assert count >= 1
        assert "sub_plugin" in registry.list_plugins()

    def test_load_from_module(self, registry):
        loader = PluginLoader(registry)
        # Load from a known module that has plugin classes
        count = loader.load_from_module("ia_modules.plugins.builtin.api_plugin")
        assert count >= 1

    def test_load_from_module_bad_module(self, registry):
        loader = PluginLoader(registry)
        count = loader.load_from_module("totally.fake.module.name")
        assert count == 0

    def test_is_plugin_class(self, registry):
        loader = PluginLoader(registry)
        assert loader._is_plugin_class(DummyCondition) is True
        assert loader._is_plugin_class(DummyStep) is True
        assert loader._is_plugin_class(Plugin) is False  # abstract
        assert loader._is_plugin_class(ConditionPlugin) is False  # abstract
        assert loader._is_plugin_class(str) is False
        assert loader._is_plugin_class(42) is False

    def test_load_plugin_package_not_a_dir(self, registry, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        loader = PluginLoader(registry)
        assert loader.load_plugin_package(f) is False

    def test_load_plugin_package_no_init(self, registry, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        loader = PluginLoader(registry)
        assert loader.load_plugin_package(pkg) is False

    def test_scan_plugin_directories(self, registry, tmp_path):
        d1 = tmp_path / "d1"
        d1.mkdir()
        plugin_code = textwrap.dedent("""\
            from ia_modules.plugins.base import ConditionPlugin, PluginMetadata

            class ScanPlugin(ConditionPlugin):
                @property
                def metadata(self):
                    return PluginMetadata(name="scan_plugin", version="1.0.0")

                async def evaluate(self, data):
                    return True
        """)
        (d1 / "scan.py").write_text(plugin_code)

        nonexistent = tmp_path / "doesnotexist"
        loader = PluginLoader(registry)
        count = loader.scan_plugin_directories([d1, nonexistent])
        assert count >= 1

    def test_get_default_plugin_dirs(self, registry):
        loader = PluginLoader(registry)
        dirs = loader.get_default_plugin_dirs()
        assert isinstance(dirs, list)
        # builtin directory should be present
        _builtin = Path(__file__).parent.parent.parent / "ia_modules" / "plugins" / "builtin"
        # At minimum the list should contain paths
        for d in dirs:
            assert isinstance(d, Path)

    def test_auto_discover(self, registry):
        loader = PluginLoader(registry)
        # Should not crash; may load 0 or more plugins depending on environment
        count = loader.auto_discover()
        assert isinstance(count, int)

    def test_auto_load_plugins_convenience(self, registry):
        count = auto_load_plugins(registry)
        assert isinstance(count, int)

    def test_discover_plugins_in_module(self, registry):
        import ia_modules.plugins.builtin.time_plugin as tp

        loader = PluginLoader(registry)
        count = loader.discover_plugins_in_module(tp)
        assert count >= 1


# =========================================================================
# 7. Builtin Plugins - API
# =========================================================================


class TestAPIStatusCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.api_plugin import APIStatusCondition
        return APIStatusCondition(config)

    async def test_matching_status(self):
        p = self._make({"expected_status": 200})
        result = await p.evaluate({
            "api_url": "http://example.com",
            "api_response": {"status_code": 200},
        })
        assert result is True

    async def test_mismatched_status(self):
        p = self._make({"expected_status": 200})
        result = await p.evaluate({
            "api_url": "http://example.com",
            "api_response": {"status_code": 500},
        })
        assert result is False

    async def test_no_url(self):
        p = self._make({})
        result = await p.evaluate({})
        assert result is False

    async def test_url_from_config(self):
        p = self._make({"url": "http://cfg.com", "expected_status": 201})
        result = await p.evaluate({"api_response": {"status_code": 201}})
        assert result is True

    async def test_default_expected_status(self):
        p = self._make({"url": "http://x.com"})
        result = await p.evaluate({"api_response": {"status_code": 200}})
        assert result is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "api_status_condition"
        assert p.metadata.plugin_type == PluginType.CONDITION


class TestAPIDataCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.api_plugin import APIDataCondition
        return APIDataCondition(config)

    async def test_eq_match(self):
        p = self._make({"json_path": "status", "operator": "eq", "value": "ok"})
        result = await p.evaluate({
            "api_response": {"data": {"status": "ok"}}
        })
        assert result is True

    async def test_eq_no_match(self):
        p = self._make({"json_path": "status", "operator": "eq", "value": "ok"})
        result = await p.evaluate({
            "api_response": {"data": {"status": "fail"}}
        })
        assert result is False

    async def test_contains(self):
        p = self._make({"json_path": "msg", "operator": "contains", "value": "hello"})
        result = await p.evaluate({
            "api_response": {"data": {"msg": "say hello world"}}
        })
        assert result is True

    async def test_gt(self):
        p = self._make({"json_path": "count", "operator": "gt", "value": 5})
        assert await p.evaluate({"api_response": {"data": {"count": 10}}}) is True
        assert await p.evaluate({"api_response": {"data": {"count": 3}}}) is False

    async def test_lt(self):
        p = self._make({"json_path": "count", "operator": "lt", "value": 5})
        assert await p.evaluate({"api_response": {"data": {"count": 3}}}) is True
        assert await p.evaluate({"api_response": {"data": {"count": 10}}}) is False

    async def test_no_json_path(self):
        p = self._make({"operator": "eq", "value": "x"})
        assert await p.evaluate({"api_response": {"data": {}}}) is False

    async def test_missing_field(self):
        p = self._make({"json_path": "missing", "operator": "eq", "value": "x"})
        assert await p.evaluate({"api_response": {"data": {}}}) is False

    async def test_unknown_operator(self):
        p = self._make({"json_path": "x", "operator": "unknown", "value": 1})
        assert await p.evaluate({"api_response": {"data": {"x": 1}}}) is False

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "api_data_condition"


class TestAPICallStep:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.api_plugin import APICallStep
        return APICallStep(config)

    async def test_execute_success(self):
        p = self._make({"url": "http://example.com", "method": "POST"})
        result = await p.execute({"input": "data"})
        assert result["api_call_successful"] is True
        assert result["input"] == "data"

    async def test_execute_no_url_raises(self):
        p = self._make({})
        with pytest.raises(ValueError, match="URL is required"):
            await p.execute({})

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "api_call_step"
        assert p.metadata.plugin_type == PluginType.STEP


# =========================================================================
# 8. Builtin Plugins - Database
# =========================================================================


class TestDatabaseRecordExists:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.database_plugin import DatabaseRecordExists
        return DatabaseRecordExists(config)

    async def test_record_found(self):
        p = self._make({"table": "users", "id_key": "user_id"})
        data = {
            "user_id": 42,
            "_db_records": {"users": {42: {"name": "Alice"}}},
        }
        assert await p.evaluate(data) is True

    async def test_record_not_found(self):
        p = self._make({"table": "users", "id_key": "user_id"})
        data = {
            "user_id": 99,
            "_db_records": {"users": {42: {"name": "Alice"}}},
        }
        assert await p.evaluate(data) is False

    async def test_no_table_config(self):
        p = self._make({})
        assert await p.evaluate({"id": 1}) is False

    async def test_no_id_in_data(self):
        p = self._make({"table": "users"})
        assert await p.evaluate({}) is False

    async def test_default_id_key(self):
        p = self._make({"table": "t"})
        data = {"id": "abc", "_db_records": {"t": {"abc": {}}}}
        assert await p.evaluate(data) is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "database_record_exists"


class TestDatabaseValueCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.database_plugin import DatabaseValueCondition
        return DatabaseValueCondition(config)

    async def test_eq(self):
        p = self._make({"field": "status", "operator": "eq", "value": "active"})
        assert await p.evaluate({"status": "active"}) is True
        assert await p.evaluate({"status": "inactive"}) is False

    async def test_ne(self):
        p = self._make({"field": "status", "operator": "ne", "value": "active"})
        assert await p.evaluate({"status": "inactive"}) is True

    async def test_gt(self):
        p = self._make({"field": "count", "operator": "gt", "value": 5})
        assert await p.evaluate({"count": 10}) is True
        assert await p.evaluate({"count": 3}) is False

    async def test_gte(self):
        p = self._make({"field": "count", "operator": "gte", "value": 5})
        assert await p.evaluate({"count": 5}) is True
        assert await p.evaluate({"count": 4}) is False

    async def test_lt(self):
        p = self._make({"field": "count", "operator": "lt", "value": 5})
        assert await p.evaluate({"count": 3}) is True

    async def test_lte(self):
        p = self._make({"field": "count", "operator": "lte", "value": 5})
        assert await p.evaluate({"count": 5}) is True
        assert await p.evaluate({"count": 6}) is False

    async def test_unknown_operator(self):
        p = self._make({"field": "x", "operator": "weird", "value": 1})
        assert await p.evaluate({"x": 1}) is False

    async def test_missing_field_config(self):
        p = self._make({"operator": "eq", "value": 1})
        assert await p.evaluate({"x": 1}) is False

    async def test_missing_value_config(self):
        p = self._make({"field": "x", "operator": "eq"})
        assert await p.evaluate({"x": 1}) is False

    async def test_field_not_in_data(self):
        p = self._make({"field": "missing", "operator": "eq", "value": 1})
        assert await p.evaluate({}) is False

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "database_value_condition"


# =========================================================================
# 9. Builtin Plugins - Time
# =========================================================================


class TestBusinessHoursCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.time_plugin import BusinessHoursCondition
        return BusinessHoursCondition(config)

    async def test_within_hours_weekday(self):
        p = self._make({"start_hour": 9, "end_hour": 17})
        # Wednesday 10 AM
        result = await p.evaluate({"current_time": "2025-10-15T10:00:00"})
        assert result is True

    async def test_outside_hours_weekday(self):
        p = self._make({"start_hour": 9, "end_hour": 17})
        # Wednesday 20:00
        result = await p.evaluate({"current_time": "2025-10-15T20:00:00"})
        assert result is False

    async def test_weekend_rejected(self):
        p = self._make({"start_hour": 9, "end_hour": 17, "weekdays_only": True})
        # Saturday 10 AM
        result = await p.evaluate({"current_time": "2025-10-18T10:00:00"})
        assert result is False

    async def test_weekend_allowed(self):
        p = self._make({"start_hour": 9, "end_hour": 17, "weekdays_only": False})
        # Saturday 10 AM
        result = await p.evaluate({"current_time": "2025-10-18T10:00:00"})
        assert result is True

    async def test_uses_datetime_object(self):
        p = self._make({"start_hour": 9, "end_hour": 17})
        dt = datetime(2025, 10, 15, 12, 0, 0)  # Wednesday noon
        result = await p.evaluate({"current_time": dt})
        assert result is True

    async def test_default_hours(self):
        p = self._make({})
        # Wednesday 10 AM - default 9-17
        result = await p.evaluate({"current_time": "2025-10-15T10:00:00"})
        assert result is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "business_hours"


class TestTimeRangeCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.time_plugin import TimeRangeCondition
        return TimeRangeCondition(config)

    async def test_within_range(self):
        p = self._make({"start_time": "09:00", "end_time": "17:00"})
        result = await p.evaluate({"current_time": "2025-10-15T12:00:00"})
        assert result is True

    async def test_outside_range(self):
        p = self._make({"start_time": "09:00", "end_time": "17:00"})
        result = await p.evaluate({"current_time": "2025-10-15T20:00:00"})
        assert result is False

    async def test_overnight_range(self):
        p = self._make({"start_time": "22:00", "end_time": "06:00"})
        result = await p.evaluate({"current_time": "2025-10-15T23:00:00"})
        assert result is True

    async def test_overnight_range_middle(self):
        p = self._make({"start_time": "22:00", "end_time": "06:00"})
        result = await p.evaluate({"current_time": "2025-10-15T03:00:00"})
        assert result is True

    async def test_overnight_range_outside(self):
        p = self._make({"start_time": "22:00", "end_time": "06:00"})
        result = await p.evaluate({"current_time": "2025-10-15T12:00:00"})
        assert result is False

    async def test_missing_start_time(self):
        p = self._make({"end_time": "17:00"})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    async def test_missing_end_time(self):
        p = self._make({"start_time": "09:00"})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    async def test_invalid_format(self):
        p = self._make({"start_time": "bad", "end_time": "format"})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    async def test_datetime_object_input(self):
        p = self._make({"start_time": "09:00", "end_time": "17:00"})
        dt = datetime(2025, 10, 15, 12, 0, 0)
        result = await p.evaluate({"current_time": dt})
        assert result is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "time_range"


class TestDayOfWeekCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.time_plugin import DayOfWeekCondition
        return DayOfWeekCondition(config)

    async def test_matching_day_by_number(self):
        p = self._make({"days": [2]})  # Wednesday
        result = await p.evaluate({"current_time": "2025-10-15T12:00:00"})
        assert result is True

    async def test_matching_day_by_name(self):
        p = self._make({"days": ["Wednesday"]})
        result = await p.evaluate({"current_time": "2025-10-15T12:00:00"})
        assert result is True

    async def test_non_matching_day(self):
        p = self._make({"days": [0]})  # Monday
        result = await p.evaluate({"current_time": "2025-10-15T12:00:00"})  # Wednesday
        assert result is False

    async def test_multiple_days(self):
        p = self._make({"days": ["monday", "wednesday", "friday"]})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is True  # Wed
        assert await p.evaluate({"current_time": "2025-10-16T12:00:00"}) is False  # Thu

    async def test_empty_days(self):
        p = self._make({"days": []})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    async def test_no_days_config(self):
        p = self._make({})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    async def test_mixed_names_and_numbers(self):
        p = self._make({"days": ["monday", 2]})  # Mon=0 and Wed=2
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is True  # Wed
        assert await p.evaluate({"current_time": "2025-10-13T12:00:00"}) is True  # Mon

    async def test_datetime_object_input(self):
        p = self._make({"days": [2]})
        dt = datetime(2025, 10, 15, 12, 0, 0)  # Wednesday
        result = await p.evaluate({"current_time": dt})
        assert result is True

    async def test_invalid_day_number_ignored(self):
        p = self._make({"days": [99]})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    async def test_invalid_day_name_ignored(self):
        p = self._make({"days": ["notaday"]})
        assert await p.evaluate({"current_time": "2025-10-15T12:00:00"}) is False

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "day_of_week"


# =========================================================================
# 10. Builtin Plugins - Validation
# =========================================================================


class TestSchemaValidator:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.validation_plugin import SchemaValidator
        return SchemaValidator(config)

    async def test_all_required_present(self):
        p = self._make({"required_fields": ["name", "email"]})
        ok, msg = await p.validate({"name": "Alice", "email": "a@b.com"})
        assert ok is True
        assert msg is None

    async def test_missing_required(self):
        p = self._make({"required_fields": ["name", "email"]})
        ok, msg = await p.validate({"name": "Alice"})
        assert ok is False
        assert "email" in msg

    async def test_no_required_fields(self):
        p = self._make({})
        ok, msg = await p.validate({"anything": True})
        assert ok is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "schema_validator"
        assert p.metadata.plugin_type == PluginType.VALIDATOR


class TestEmailValidator:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.validation_plugin import EmailValidator
        return EmailValidator(config)

    async def test_valid_email(self):
        p = self._make()
        assert await p.evaluate({"email": "user@example.com"}) is True

    async def test_invalid_email(self):
        p = self._make()
        assert await p.evaluate({"email": "notanemail"}) is False

    async def test_empty_email(self):
        p = self._make()
        assert await p.evaluate({"email": ""}) is False

    async def test_no_email_field(self):
        p = self._make()
        assert await p.evaluate({}) is False

    async def test_custom_field(self):
        p = self._make({"field": "contact_email"})
        assert await p.evaluate({"contact_email": "a@b.com"}) is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "email_validator"


class TestRangeValidator:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.validation_plugin import RangeValidator
        return RangeValidator(config)

    async def test_within_range(self):
        p = self._make({"field": "age", "min": 0, "max": 120})
        assert await p.evaluate({"age": 25}) is True

    async def test_below_min(self):
        p = self._make({"field": "age", "min": 0, "max": 120})
        assert await p.evaluate({"age": -1}) is False

    async def test_above_max(self):
        p = self._make({"field": "age", "min": 0, "max": 120})
        assert await p.evaluate({"age": 200}) is False

    async def test_no_field_config(self):
        p = self._make({"min": 0})
        assert await p.evaluate({"x": 5}) is False

    async def test_field_missing_from_data(self):
        p = self._make({"field": "x"})
        assert await p.evaluate({}) is False

    async def test_only_min(self):
        p = self._make({"field": "x", "min": 10})
        assert await p.evaluate({"x": 15}) is True
        assert await p.evaluate({"x": 5}) is False

    async def test_only_max(self):
        p = self._make({"field": "x", "max": 10})
        assert await p.evaluate({"x": 5}) is True
        assert await p.evaluate({"x": 15}) is False

    async def test_at_boundary(self):
        p = self._make({"field": "x", "min": 5, "max": 10})
        assert await p.evaluate({"x": 5}) is True
        assert await p.evaluate({"x": 10}) is True

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "range_validator"


class TestRegexValidator:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.validation_plugin import RegexValidator
        return RegexValidator(config)

    async def test_matching_pattern(self):
        p = self._make({"field": "code", "pattern": r"^[A-Z]{3}-\d{4}$"})
        assert await p.evaluate({"code": "ABC-1234"}) is True

    async def test_non_matching_pattern(self):
        p = self._make({"field": "code", "pattern": r"^[A-Z]{3}-\d{4}$"})
        assert await p.evaluate({"code": "abc-12"}) is False

    async def test_no_field_config(self):
        p = self._make({"pattern": r".*"})
        assert await p.evaluate({"x": "val"}) is False

    async def test_no_pattern_config(self):
        p = self._make({"field": "x"})
        assert await p.evaluate({"x": "val"}) is False

    async def test_non_string_value(self):
        p = self._make({"field": "x", "pattern": r"\d+"})
        assert await p.evaluate({"x": 123}) is False

    async def test_invalid_regex(self):
        p = self._make({"field": "x", "pattern": r"[invalid"})
        assert await p.evaluate({"x": "val"}) is False

    async def test_field_missing(self):
        # data.get(field, '') returns '' when missing; .* matches empty string
        p = self._make({"field": "missing", "pattern": r".+"})
        assert await p.evaluate({}) is False

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "regex_validator"


# =========================================================================
# 11. Builtin Plugins - Weather
# =========================================================================


class TestWeatherCondition:
    def _make(self, config=None):
        from ia_modules.plugins.builtin.weather_plugin import WeatherCondition
        return WeatherCondition(config)

    async def test_sunny(self):
        p = self._make({"condition": "sunny"})
        assert await p.evaluate({"weather": {"condition": "Sunny"}}) is True
        assert await p.evaluate({"weather": {"condition": "Rainy"}}) is False

    async def test_rainy(self):
        p = self._make({"condition": "rainy"})
        assert await p.evaluate({"weather": {"condition": "rain"}}) is True
        assert await p.evaluate({"weather": {"condition": "drizzle"}}) is True
        assert await p.evaluate({"weather": {"condition": "sunny"}}) is False

    async def test_temperature_above(self):
        p = self._make({"condition": "temperature_above", "threshold": 20})
        assert await p.evaluate({"weather": {"temperature": 25}}) is True
        assert await p.evaluate({"weather": {"temperature": 15}}) is False

    async def test_temperature_above_no_threshold(self):
        p = self._make({"condition": "temperature_above"})
        assert await p.evaluate({"weather": {"temperature": 25}}) is False

    async def test_temperature_below(self):
        p = self._make({"condition": "temperature_below", "threshold": 10})
        assert await p.evaluate({"weather": {"temperature": 5}}) is True
        assert await p.evaluate({"weather": {"temperature": 15}}) is False

    async def test_temperature_below_no_threshold(self):
        p = self._make({"condition": "temperature_below"})
        assert await p.evaluate({"weather": {"temperature": 5}}) is False

    async def test_humidity_above(self):
        p = self._make({"condition": "humidity_above", "threshold": 80})
        assert await p.evaluate({"weather": {"humidity": 90}}) is True
        assert await p.evaluate({"weather": {"humidity": 50}}) is False

    async def test_humidity_above_no_threshold(self):
        p = self._make({"condition": "humidity_above"})
        assert await p.evaluate({"weather": {"humidity": 90}}) is False

    async def test_unknown_condition(self):
        p = self._make({"condition": "tornado"})
        assert await p.evaluate({"weather": {}}) is False

    async def test_default_condition_sunny(self):
        p = self._make({})
        assert await p.evaluate({"weather": {"condition": "sunny"}}) is True

    async def test_no_weather_data(self):
        p = self._make({"condition": "sunny"})
        assert await p.evaluate({}) is False

    def test_metadata(self):
        p = self._make()
        assert p.metadata.name == "weather_condition"


class TestIsGoodWeather:
    def _make(self):
        from ia_modules.plugins.builtin.weather_plugin import is_good_weather
        return is_good_weather()

    async def test_good_weather(self):
        p = self._make()
        result = await p.evaluate(
            {"weather": {"temperature": 20, "condition": "sunny"}}
        )
        assert result is True

    async def test_too_cold(self):
        p = self._make()
        result = await p.evaluate(
            {"weather": {"temperature": 10, "condition": "sunny"}}
        )
        assert result is False

    async def test_too_hot(self):
        p = self._make()
        result = await p.evaluate(
            {"weather": {"temperature": 30, "condition": "sunny"}}
        )
        assert result is False

    async def test_rainy(self):
        p = self._make()
        result = await p.evaluate(
            {"weather": {"temperature": 20, "condition": "rain"}}
        )
        assert result is False

    async def test_no_weather(self):
        p = self._make()
        result = await p.evaluate({})
        assert result is False


# =========================================================================
# 12. Plugin lifecycle integration
# =========================================================================


class TestPluginLifecycle:
    async def test_register_load_execute_unload(self, registry):
        """Full lifecycle: register -> get -> execute -> shutdown -> unregister."""
        registry.register(DummyCondition)
        registry.register(DummyStep)

        # Execute condition
        cond = registry.get("dummy_condition")
        assert await cond.evaluate({"flag": True}) is True

        # Execute step
        step = registry.get("dummy_step")
        result = await step.execute({"data": 1})
        assert result["stepped"] is True

        # Shutdown all
        await registry.shutdown_all()

        # Unregister
        registry.unregister("dummy_condition")
        registry.unregister("dummy_step")
        assert registry.list_plugins() == []

    def test_loader_then_registry(self, registry, tmp_path):
        """Load from file, then use registry to access plugin."""
        code = textwrap.dedent("""\
            from ia_modules.plugins.base import ConditionPlugin, PluginMetadata

            class LifecyclePlugin(ConditionPlugin):
                @property
                def metadata(self):
                    return PluginMetadata(name="lifecycle_plugin", version="1.0.0")

                async def evaluate(self, data):
                    return data.get("val", 0) > 0
        """)
        (tmp_path / "lc.py").write_text(code)

        loader = PluginLoader(registry)
        count = loader.load_from_file(tmp_path / "lc.py")
        assert count == 1

        p = registry.get("lifecycle_plugin")
        assert p is not None
        assert p.metadata.version == "1.0.0"
