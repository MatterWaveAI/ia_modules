# Contributing to IA Modules

Thank you for your interest in contributing to IA Modules! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)
- [Release Process](#release-process)

## Code of Conduct

By participating in this project, you agree to:
- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other contributors

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Basic understanding of async/await in Python
- Familiarity with pipeline/workflow concepts (helpful but not required)

### Finding Issues to Work On

1. Check [GitHub Issues](https://github.com/matterwaveai/ia_modules/issues)
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to indicate you're working on it
4. If you want to work on something not listed, create an issue first to discuss

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/ia_modules.git
cd ia_modules
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install Development Dependencies

```bash
# Install package in editable mode with all dependencies
pip install -e ".[dev,all]"
```

### 4. Verify Installation

```bash
# Run tests to ensure everything works
pytest tests/ -v

# Verify tests pass
```

## Project Structure

```
ia_modules/
├── pipeline/           # Core pipeline framework
│   ├── core.py        # Step, Pipeline, ExecutionContext
│   ├── runner.py      # run_pipeline_from_json, create_pipeline_from_json
│   ├── routing.py     # Conditional routing
│   └── graph_pipeline_runner.py  # Graph execution
├── checkpoint/        # Checkpointing system
├── memory/           # Conversation memory
├── scheduler/        # Job scheduling
├── agents/           # Multi-agent orchestration
├── validation/       # Grounding and validation
├── reliability/      # Reliability metrics (EARF)
│   ├── metrics.py           # Core metrics, MetricStorage, MemoryMetricStorage
│   ├── sql_metric_storage.py  # SQL backend
│   ├── redis_metric_storage.py  # Redis backend
│   ├── slo_tracker.py       # SLO tracking
│   ├── replay.py            # Event replay
│   └── evidence_collector.py  # Evidence collection
├── cli/             # CLI tools
├── plugins/         # Plugin system
├── tools/           # Tool integrations
└── database/        # Database interfaces

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests
├── e2e/            # End-to-end tests
└── pipelines/      # Example pipelines
```

## Making Changes

### 1. Create a Branch

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Write clean, readable code
- Follow existing code style
- Add docstrings to public functions/classes
- Keep commits focused and atomic

### 3. Write Tests

**Every new feature or bug fix must include tests.**

```python
# tests/unit/test_your_feature.py
import pytest
from ia_modules.your_module import YourClass

@pytest.mark.asyncio
async def test_your_feature():
    """Test description."""
    instance = YourClass()
    result = await instance.do_something()
    assert result.success is True
```

### 4. Run Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_your_feature.py -v

# Run with coverage
pytest tests/ --cov=ia_modules --cov-report=html

# View coverage report
open htmlcov/index.html  # or xdg-open on Linux
```

### 5. Update Documentation

If your change affects:
- **Public API**: Update [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **CLI**: Update [docs/CLI_TOOL_DOCUMENTATION.md](docs/CLI_TOOL_DOCUMENTATION.md)
- **Features**: Update [docs/FEATURES.md](docs/FEATURES.md)
- **Usage**: Update [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

## Testing

### Test Structure

```python
# Good test structure
@pytest.mark.asyncio
async def test_feature_success_case():
    """Test that feature works in normal conditions."""
    # Arrange
    setup = create_test_setup()

    # Act
    result = await setup.execute()

    # Assert
    assert result.success is True
    assert result.data == expected_data

@pytest.mark.asyncio
async def test_feature_error_case():
    """Test that feature handles errors correctly."""
    # Arrange
    setup = create_failing_setup()

    # Act
    result = await setup.execute()

    # Assert
    assert result.success is False
    assert "error" in result.data
```

### Test Coverage Requirements

- **New features**: Minimum 80% coverage
- **Bug fixes**: Must include test that fails without fix
- **Critical paths**: Aim for 100% coverage

### Running Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Tests for specific module
pytest tests/unit/test_reliability*.py -v

# Quick smoke test
pytest tests/ -v -q --tb=short
```

## Documentation

### Docstring Style

We use Google-style docstrings:

```python
async def process_data(data: dict, validate: bool = True) -> StepResult:
    """Process input data and return result.

    This function validates and processes the input data according
    to the configured schema.

    Args:
        data: Input data dictionary to process
        validate: Whether to validate data against schema (default: True)

    Returns:
        StepResult containing processed data or error information

    Raises:
        ValidationError: If validation is enabled and data is invalid
        ProcessingError: If processing fails

    Example:
        >>> result = await process_data({"key": "value"})
        >>> print(result.success)
        True
    """
    # Implementation
```

### Adding Examples

When adding examples:

1. **Create working example** in `tests/pipelines/`
2. **Add to documentation** with explanation
3. **Reference in README** if applicable

Example structure:
```
tests/pipelines/your_example/
├── README.md           # Explanation
├── pipeline.json       # Pipeline definition
└── steps/             # Step implementations
    ├── __init__.py
    └── your_steps.py
```

## Submitting Changes

### 1. Commit Your Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature: brief description

- Detailed point 1
- Detailed point 2
- Fixes #123"
```

### Commit Message Guidelines

**Format:**
```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Maintenance tasks

**Example:**
```
feat: Add Redis storage backend for reliability metrics

- Implement RedisMetricStorage class
- Add connection pooling for performance
- Include comprehensive unit tests
- Update documentation with Redis examples

Closes #45
```

### 2. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 3. Create Pull Request

1. Go to GitHub and create a Pull Request
2. Fill in the PR template:
   - Description of changes
   - Related issue numbers
   - Testing performed
   - Documentation updates
3. Wait for CI checks to pass
4. Address review feedback

### PR Checklist

Before submitting, ensure:
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] No test coverage decrease
- [ ] Code follows project style
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Commit messages are clear
- [ ] PR description is complete

## Coding Standards

### Python Style

We follow [PEP 8](https://pep8.org/) with these additions:

**Line Length:**
- Maximum 100 characters (soft limit)
- 120 characters (hard limit)

**Imports:**
```python
# Standard library
import asyncio
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List

# Third-party
import pytest
from pydantic import BaseModel

# Local
from ia_modules.pipeline.core import Step
from ia_modules.reliability.metrics import ReliabilityMetrics
```

**Type Hints:**
```python
# Always use type hints for public APIs
async def run(
    self,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the step."""
    pass
```

**Async/Await:**
```python
# Prefer async/await over callbacks
async def process():
    result = await fetch_data()  # Good
    return process_result(result)

# Not this
def process(callback):
    fetch_data(lambda result: callback(process_result(result)))  # Avoid
```

### Error Handling

```python
# Be specific with exceptions
try:
    result = await process_data()
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    return StepResult(success=False, error=str(e))
except ProcessingError as e:
    logger.error(f"Processing failed: {e}")
    return StepResult(success=False, error=str(e))
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed information for debugging")
logger.info("General information about operation")
logger.warning("Warning about potential issue")
logger.error("Error that should be investigated")
logger.critical("Critical error requiring immediate attention")
```

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes (1.0.0 → 2.0.0)
- **MINOR**: New features, backward compatible (0.0.3 → 0.1.0)
- **PATCH**: Bug fixes, backward compatible (0.0.3 → 0.0.4)

### Release Checklist

For maintainers preparing releases:

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with release notes
3. **Run full test suite**: `pytest tests/ -v`
4. **Build package**: `python -m build`
5. **Test installation**: `pip install dist/ia_modules-*.whl`
6. **Create git tag**: `git tag -a v0.0.3 -m "Release v0.0.3"`
7. **Push tag**: `git push origin v0.0.3`
8. **Create GitHub release** with notes
9. **Publish to PyPI**: `twine upload dist/*`

## Getting Help

### Resources

- **Documentation**: [docs/](docs/)
- **API Reference**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Examples**: [tests/pipelines/](tests/pipelines/)

### Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Request Comments**: Code review and feedback

### Common Questions

**Q: How do I add a new storage backend?**
A: Implement the `MetricStorage` interface from `reliability/metrics.py`. See existing implementations for examples.

**Q: How do I add a new pipeline step?**
A: Extend `Step` (`ia_modules.pipeline.core`) and implement the async `run(self, data)` method. See `tests/pipelines/` for examples.

**Q: How do I add a new CLI command?**
A: Add an argparse subcommand in `cli/main.py` following the existing commands.

**Q: Where should I add my test?**
A: Unit tests in `tests/unit/`, integration tests in `tests/integration/`, example pipelines in `tests/pipelines/`.

## Recognition

Contributors are recognized in:
- [CHANGELOG.md](CHANGELOG.md) - Feature/fix credits
- GitHub contributors page
- Release notes

Thank you for contributing to IA Modules! 🎉
