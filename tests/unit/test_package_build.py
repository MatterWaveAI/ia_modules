"""
Unit tests for package build configuration.

These tests validate that the pyproject.toml configuration correctly
discovers and includes all Python packages in the built wheel.
"""

import subprocess
import sys
import zipfile
from pathlib import Path


import pytest

try:
    from build.__main__ import main as _build_main  # noqa: F401
    _has_build = True
except (ImportError, ModuleNotFoundError):
    _has_build = False


class TestPackageBuild:
    """Tests for validating package build configuration."""

    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        # Navigate up from tests/unit to project root
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def expected_packages(self):
        """List of expected subpackages under ia_modules/ that should be in the wheel."""
        return {
            'agents',
            'checkpoint',
            'cli',
            'database',
            'guardrails',
            'memory',
            'pipeline',
            'plugins',
            'reliability',
            'scheduler',
            'telemetry',
            'tools',
            'utils',
            'validation',
        }

    def test_pyproject_has_automatic_package_discovery(self, project_root):
        """Verify pyproject.toml uses automatic package discovery."""
        pyproject_path = project_root / "pyproject.toml"
        content = pyproject_path.read_text()
        
        # Should have the find configuration
        assert "[tool.setuptools.packages.find]" in content
        
        # Should NOT have explicit package listing
        assert 'packages = [' not in content
        
    def test_pyproject_excludes_test_directories(self, project_root):
        """Verify test directories are excluded from package discovery."""
        pyproject_path = project_root / "pyproject.toml"
        content = pyproject_path.read_text()
        
        # Should exclude tests, docs, etc.
        assert '"tests*"' in content or "'tests*'" in content
        assert '"docs*"' in content or "'docs*'" in content
        assert '"examples*"' in content or "'examples*'" in content

    @pytest.mark.slow
    @pytest.mark.skipif(not _has_build, reason="'build' package not installed")
    def test_build_wheel_includes_all_packages(self, project_root, expected_packages, tmp_path):
        """
        Build a wheel and verify all expected packages are included.
        
        This is a slower integration-style test that actually builds the wheel.
        Run with: pytest -m slow
        """
        # Build the wheel
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            pytest.fail(f"Wheel build failed:\n{result.stderr}")
        
        # Find the built wheel
        wheel_files = list(tmp_path.glob("*.whl"))
        assert len(wheel_files) == 1, f"Expected 1 wheel, found {len(wheel_files)}"
        
        wheel_path = wheel_files[0]
        
        # Extract and check contents
        with zipfile.ZipFile(wheel_path, 'r') as whl:
            # Get all files under ia_modules/
            all_files = whl.namelist()
            
            # Get subdirectories under ia_modules/
            ia_modules_subdirs = {
                parts[1]
                for name in all_files
                if name.startswith('ia_modules/') and len(parts := name.split('/')) > 1 and parts[1]
            }
            
            # Verify all expected packages are present under ia_modules/
            missing_packages = expected_packages - ia_modules_subdirs
            assert not missing_packages, f"Missing packages in wheel: {missing_packages}"
            
            # Verify no test files leaked in
            # Look for actual test files: test_*.py (but not *_test_utils.py or *_testing.py)
            # or files in tests/ directories
            test_files = []
            for f in all_files:
                if not f.endswith('.py'):
                    continue
                # Skip build artifacts
                if f.startswith('build/'):
                    continue
                # Check if it's in a tests directory
                if '/tests/' in f or f.startswith('tests/'):
                    test_files.append(f)
                    continue
                # Check if it's a test_*.py file (but not utility modules like test_utils.py)
                parts = f.split('/')
                filename = parts[-1] if parts else f
                if filename.startswith('test_') and filename not in ['test_utils.py', 'test_helpers.py']:
                    test_files.append(f)
            
            assert not test_files, f"Test files should not be in wheel: {test_files[:5]}"

    @pytest.mark.slow
    @pytest.mark.skipif(not _has_build, reason="'build' package not installed")
    def test_wheel_contains_python_files(self, project_root, tmp_path):
        """
        Verify the built wheel contains actual Python files, not just metadata.
        
        This catches issues like the broken 0.1.1 release that only had dist-info.
        """
        # Build the wheel
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            pytest.fail(f"Wheel build failed:\n{result.stderr}")
        
        wheel_files = list(tmp_path.glob("*.whl"))
        wheel_path = wheel_files[0]
        
        # Check wheel contents
        with zipfile.ZipFile(wheel_path, 'r') as whl:
            all_files = whl.namelist()
            
            # Count Python files (excluding dist-info)
            python_files = [
                f for f in all_files 
                if f.endswith('.py') and not f.startswith('ia_modules-')
            ]
            
            # Should have many Python files (at least 100+)
            assert len(python_files) > 100, (
                f"Wheel should contain many Python files, found only {len(python_files)}. "
                f"This might indicate a packaging issue similar to the 0.1.1 bug."
            )
            
            # Verify core modules are present
            core_files = {
                'ia_modules/pipeline/core.py',
                'ia_modules/agents/core.py',
                'ia_modules/pipeline/runner.py',
                'ia_modules/pipeline/services.py',
            }
            
            for core_file in core_files:
                assert core_file in all_files, f"Core file {core_file} missing from wheel"

    def test_importable_after_install(self, project_root):
        """
        Test that key modules can be imported after installation.
        
        This assumes the package is already installed in the current environment.
        Skip if not installed.
        """
        try:
            # Try importing various submodules using importlib
            import importlib.util
            
            modules_to_check = [
                'ia_modules.agents.core',
                'ia_modules.pipeline.core', 
                'ia_modules.pipeline.services',
                'ia_modules.tools.core',
                'ia_modules.memory.core'
            ]
            
            for module_name in modules_to_check:
                spec = importlib.util.find_spec(module_name)
                assert spec is not None, f"Module {module_name} not found"
            
            # If we get here, imports work
            assert True
            
        except ImportError as e:
            pytest.skip(f"Package not installed in current environment: {e}")

    def test_version_is_set(self, project_root):
        """Verify version is set in pyproject.toml."""
        pyproject_path = project_root / "pyproject.toml"
        content = pyproject_path.read_text()
        
        # Should have a version
        assert 'version = ' in content
        
        # Version should not be 0.1.1 (the broken release)
        assert 'version = "0.1.1"' not in content

    def test_required_metadata_present(self, project_root):
        """Verify all required metadata is in pyproject.toml."""
        pyproject_path = project_root / "pyproject.toml"
        content = pyproject_path.read_text()
        
        required_fields = [
            'name = ',
            'version = ',
            'description = ',
            'authors = ',
            'readme = ',
            'license = ',
        ]
        
        for field in required_fields:
            assert field in content, f"Missing required field: {field}"
