"""
Tests for Plugin System

Tests plugin base classes, registry, loader, and decorators.
"""

import pytest
from ia_modules.plugins.base import (
    PluginMetadata,
    PluginType,
    ConditionPlugin,
    StepPlugin
)
from ia_modules.plugins.registry import PluginRegistry, reset_registry
from ia_modules.plugins.decorators import condition_plugin, step_plugin


class TestPluginMetadata:
    """Test PluginMetadata"""

    def test_metadata_creation(self):
        """Test creating plugin metadata"""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            author="Test Author",
            description="Test Description",
            plugin_type=PluginType.CONDITION
        )

        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Test Author"
        assert metadata.plugin_type == PluginType.CONDITION

    def test_metadata_requires_name(self):
        """Test that name is required"""
        with pytest.raises(ValueError, match="name is required"):
            PluginMetadata(name="", version="1.0.0")

    def test_metadata_requires_version(self):
        """Test that version is required"""
        with pytest.raises(ValueError, match="version is required"):
            PluginMetadata(name="test", version="")


class TestPluginBase:
    """Test Plugin base class"""

    def test_plugin_initialization(self):
        """Test plugin initialization"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        plugin = TestPlugin({'key': 'value'})
        assert plugin.config == {'key': 'value'}

    @pytest.mark.asyncio
    async def test_plugin_shutdown(self):
        """Test plugin shutdown"""
        class TestPlugin(ConditionPlugin):
            def __init__(self, config=None):
                super().__init__(config)
                self.shutdown_called = False

            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def _shutdown(self):
                self.shutdown_called = True

            async def evaluate(self, data):
                return True

        plugin = TestPlugin()
        await plugin.shutdown()
        assert plugin.shutdown_called

    def test_plugin_get_info(self):
        """Test getting plugin info"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test_plugin",
                    version="2.0.0",
                    author="Test Author",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        plugin = TestPlugin()

        # Metadata is accessed via plugin.metadata
        assert plugin.metadata.name == "test_plugin"
        assert plugin.metadata.version == "2.0.0"
        assert plugin.metadata.author == "Test Author"
        assert plugin.metadata.plugin_type == PluginType.CONDITION


class TestConditionPlugin:
    """Test ConditionPlugin"""

    @pytest.mark.asyncio
    async def test_condition_plugin_evaluate(self):
        """Test condition plugin evaluation"""
        class SimpleCondition(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="simple",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return data.get('value', 0) > 10

        plugin = SimpleCondition()
        assert await plugin.evaluate({'value': 15}) is True
        assert await plugin.evaluate({'value': 5}) is False


class TestStepPlugin:
    """Test StepPlugin"""

    @pytest.mark.asyncio
    async def test_step_plugin_execute(self):
        """Test step plugin execution"""
        class SimpleStep(StepPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="simple_step",
                    version="1.0.0",
                    plugin_type=PluginType.STEP
                )

            async def execute(self, data):
                data['processed'] = True
                return data

        plugin = SimpleStep()
        result = await plugin.execute({'value': 10})

        assert result['value'] == 10
        assert result['processed'] is True


class TestPluginRegistry:
    """Test PluginRegistry"""

    def setup_method(self):
        """Reset registry before each test"""
        reset_registry()

    def test_registry_singleton(self):
        """Test registry singleton pattern"""
        registry1 = PluginRegistry.get_instance()
        registry2 = PluginRegistry.get_instance()
        assert registry1 is registry2

    def test_register_plugin(self):
        """Test registering a plugin"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        registry = PluginRegistry()
        registry.register(TestPlugin)

        assert "test" in registry.list_plugins()
        assert registry.get("test") is not None

    def test_unregister_plugin(self):
        """Test unregistering a plugin"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        registry = PluginRegistry()
        registry.register(TestPlugin)
        assert "test" in registry.list_plugins()

        registry.unregister("test")
        assert "test" not in registry.list_plugins()

    def test_get_plugin(self):
        """Test getting plugin instance"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        registry = PluginRegistry()
        registry.register(TestPlugin)

        plugin = registry.get("test")
        assert plugin is not None
        assert plugin.metadata.name == "test"

    def test_get_plugin_class(self):
        """Test getting plugin class"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        registry = PluginRegistry()
        registry.register(TestPlugin)

        plugin_class = registry.get_class("test")
        assert plugin_class is TestPlugin

    def test_create_instance(self):
        """Test creating new plugin instance"""
        class TestPlugin(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        registry = PluginRegistry()
        registry.register(TestPlugin)

        instance = registry.create_instance("test", {'custom': 'config'})
        assert instance is not None
        assert instance.config == {'custom': 'config'}

    def test_list_plugins_by_type(self):
        """Test listing plugins by type"""
        class Condition1(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="condition1",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        class Step1(StepPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="step1",
                    version="1.0.0",
                    plugin_type=PluginType.STEP
                )

            async def execute(self, data):
                return data

        registry = PluginRegistry()
        registry.register(Condition1)
        registry.register(Step1)

        conditions = registry.list_plugins(PluginType.CONDITION)
        steps = registry.list_plugins(PluginType.STEP)

        assert "condition1" in conditions
        assert "step1" in steps
        assert "step1" not in conditions

    def test_check_dependencies(self):
        """Test checking plugin dependencies"""
        class PluginA(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="plugin_a",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION,
                    dependencies=["plugin_b"]
                )

            async def evaluate(self, data):
                return True

        class PluginB(ConditionPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="plugin_b",
                    version="1.0.0",
                    plugin_type=PluginType.CONDITION
                )

            async def evaluate(self, data):
                return True

        registry = PluginRegistry()
        registry.register(PluginA)

        # Dependencies not satisfied
        satisfied, missing = registry.check_dependencies("plugin_a")
        assert not satisfied
        assert "plugin_b" in missing

        # Now satisfy dependencies
        registry.register(PluginB)
        satisfied, missing = registry.check_dependencies("plugin_a")
        assert satisfied
        assert len(missing) == 0


class TestPluginDecorators:
    """Test plugin decorators"""

    def setup_method(self):
        """Reset registry before each test"""
        reset_registry()

    def test_condition_plugin_decorator(self):
        """Test @condition_plugin decorator"""
        @condition_plugin(
            name="test_condition",
            version="1.0.0",
            description="Test condition",
            auto_register=False
        )
        class TestCondition(ConditionPlugin):
            async def evaluate(self, data):
                return data.get('test', False)

        instance = TestCondition()
        assert instance.metadata.name == "test_condition"
        assert instance.metadata.version == "1.0.0"
        assert instance.metadata.description == "Test condition"
        assert instance.metadata.plugin_type == PluginType.CONDITION

    def test_step_plugin_decorator(self):
        """Test @step_plugin decorator"""
        @step_plugin(
            name="test_step",
            version="2.0.0",
            author="Test Author",
            auto_register=False
        )
        class TestStep(StepPlugin):
            async def execute(self, data):
                return data

        instance = TestStep()
        assert instance.metadata.name == "test_step"
        assert instance.metadata.version == "2.0.0"
        assert instance.metadata.author == "Test Author"
        assert instance.metadata.plugin_type == PluginType.STEP
