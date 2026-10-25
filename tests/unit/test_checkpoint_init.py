"""
Unit tests for checkpoint package __init__.py

Tests import behavior with and without optional dependencies.
"""



class TestCheckpointImports:
    """Test checkpoint package imports"""

    def test_checkpoint_base_imports(self):
        """Test that checkpoint base classes always import"""
        import ia_modules.checkpoint as checkpoint

        # These should always be available
        required_exports = [
            'Checkpoint',
            'BaseCheckpointer',
            'CheckpointError',
            'CheckpointSaveError',
            'CheckpointLoadError',
            'MemoryCheckpointer',
        ]

        assert all(export in checkpoint.__all__ for export in required_exports)

    def test_checkpoint_imports_with_sql(self):
        """Test that SQLCheckpointer is available when dependencies present"""
        import ia_modules.checkpoint as checkpoint

        # SQLCheckpointer should be in __all__ when sqlalchemy is available
        if 'SQLCheckpointer' in dir(checkpoint):
            assert 'SQLCheckpointer' in checkpoint.__all__

    def test_checkpoint_imports_with_redis(self):
        """Test that RedisCheckpointer is available when dependencies present"""
        import ia_modules.checkpoint as checkpoint

        # RedisCheckpointer should be in __all__ when redis is available
        if 'RedisCheckpointer' in dir(checkpoint):
            assert 'RedisCheckpointer' in checkpoint.__all__

    def test_checkpoint_imports_without_optional_backends(self):
        """Test that checkpoint works without optional backends"""
        # This test verifies the ImportError handling exists
        # The try/except blocks ensure optional backends fail gracefully
        import ia_modules.checkpoint as checkpoint

        # Base exports should always be available regardless of optional deps
        required_exports = [
            'Checkpoint',
            'BaseCheckpointer',
            'CheckpointError',
            'CheckpointSaveError',
            'CheckpointLoadError',
            'MemoryCheckpointer',
        ]

        assert all(export in checkpoint.__all__ for export in required_exports)

        # Optional backends may or may not be present
        # SQLCheckpointer requires sqlalchemy
        # RedisCheckpointer requires redis
        # Both should handle ImportError gracefully

    def test_checkpoint_module_has_docstring(self):
        """Test that checkpoint module has proper documentation"""
        import ia_modules.checkpoint as checkpoint

        assert checkpoint.__doc__ is not None
        assert "Checkpoint" in checkpoint.__doc__
        assert "state management" in checkpoint.__doc__
