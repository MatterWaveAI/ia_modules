"""Shared test configuration for showcase tests.

Adds showcase_app/backend to sys.path so all tests can use
`from services.X import ...` without per-file sys.path hacks.

Registers a shared SubprocessExecutor so tests that import services
depending on ia_modules don't hit the "singleton not registered" error.
"""

import sys
import os

_tests_dir = os.path.dirname(__file__)
_backend_dir = os.path.abspath(os.path.join(_tests_dir, '..', 'backend'))
_showcase_dir = os.path.abspath(os.path.join(_tests_dir, '..'))
_repo_root = os.path.abspath(os.path.join(_tests_dir, '..', '..'))

for p in (_backend_dir, _showcase_dir, _repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

# Register shared executor if not already set (avoids RuntimeError in tests
# that import services depending on AgentOrchestrator/SubprocessExecutor).
from ia_modules.agents.subprocess_executor import set_shared_executor, SubprocessExecutor  # noqa: E402
import ia_modules.agents.subprocess_executor as _executor_mod  # noqa: E402

if _executor_mod._shared_executor is None:
    set_shared_executor(SubprocessExecutor(max_concurrent=1))
