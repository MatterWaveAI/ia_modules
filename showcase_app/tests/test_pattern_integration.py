"""
Integration tests for Pattern Service — hits the REAL backend API.

NO MOCKS. These tests verify the full stack:
  API endpoint → PatternService → llm_call → LLMStep → SubprocessExecutor → opencode CLI

The test fixture starts the backend server via WSL automatically, waits for
it to be healthy, runs the tests, then shuts it down.

Run:
  pytest showcase_app/tests/test_pattern_integration.py -v -s

These are slow (real LLM calls ~10-30s each) and require infrastructure,
so they are NOT run in CI. Use the unit tests (test_pattern_service.py)
for fast feedback.
"""

import os
import subprocess
import sys
import time
import pytest
import httpx

pytestmark = pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Live integration tests require running backend + LLM API key"
)

BASE_URL = "http://localhost:7331"

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")

# How to start the backend when it isn't already running on BASE_URL. Override with
# SHOWCASE_BACKEND_CMD, e.g. to run it inside WSL or a particular virtualenv.
BACKEND_CMD = os.environ.get("SHOWCASE_BACKEND_CMD", f'"{sys.executable}" main.py')


def _health_check(timeout: float = 30) -> bool:
    """Poll /health until the server is up or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


@pytest.fixture(scope="session")
def backend_server():
    """Start the backend server in WSL, yield when healthy, kill on teardown."""
    # Check if already running (e.g. dev started it manually)
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=3)
        if r.status_code == 200:
            yield "external"
            return
    except Exception:
        pass

    # Start the server
    proc = subprocess.Popen(
        BACKEND_CMD,
        shell=True,
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    if not _health_check(timeout=30):
        # Dump whatever stdout we got for debugging
        proc.kill()
        out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
        pytest.fail(f"Backend failed to start within 30s.\nOutput:\n{out}")

    yield "managed"

    # Teardown — kill the WSL process tree
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass
    proc.wait(timeout=10)


@pytest.mark.usefixtures("backend_server")
class TestPatternIntegrationLive:
    """Hit the real API — verifies full LLM stack end-to-end."""

    @pytest.mark.asyncio
    async def test_reflection_live(self):
        """Reflection pattern: real LLM critique + improvement."""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
            resp = await client.post("/api/patterns/reflection", json={
                "initial_output": "AI is useful for many things.",
                "criteria": {
                    "clarity": "Should be clear and specific",
                    "completeness": "Should cover key aspects"
                },
                "max_iterations": 2
            })

        assert resp.status_code == 200, f"API error: {resp.text}"
        data = resp.json()

        assert data["pattern"] == "reflection"
        assert data["initial_output"] == "AI is useful for many things."
        assert len(data["iterations"]) >= 1
        assert 0 <= data["final_quality_score"] <= 1
        # The LLM should have actually produced a critique
        assert len(data["iterations"][0]["critique"]) > 20, "Critique seems empty — LLM may not be responding"
        assert data["final_output"], "No final output"

    @pytest.mark.asyncio
    async def test_tool_use_live(self):
        """Tool use pattern: real LLM tool selection."""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
            resp = await client.post("/api/patterns/tool-use", json={
                "task": "Analyze sentiment of customer reviews",
                "available_tools": ["web_search", "database_query", "llm_analyzer", "python_executor"]
            })

        assert resp.status_code == 200, f"API error: {resp.text}"
        data = resp.json()

        assert data["pattern"] == "tool_use"
        assert data["task"] == "Analyze sentiment of customer reviews"
        # LLM should select at least one tool
        assert len(data["selected_tools"]) >= 1 or data["reasoning"], "No tools selected and no reasoning"

    @pytest.mark.asyncio
    async def test_agentic_rag_live(self):
        """Agentic RAG: real LLM document evaluation and query refinement."""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
            resp = await client.post("/api/patterns/agentic-rag", json={
                "query": "machine learning applications in healthcare",
                "max_refinements": 2
            })

        assert resp.status_code == 200, f"API error: {resp.text}"
        data = resp.json()

        assert data["pattern"] == "agentic_rag"
        assert len(data["iterations"]) >= 1
        # LLM should have evaluated documents
        first_iter = data["iterations"][0]
        assert "average_relevance" in first_iter
        assert first_iter["documents_retrieved"] >= 1

    @pytest.mark.asyncio
    async def test_metacognition_live(self):
        """Metacognition: real LLM performance analysis."""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
            resp = await client.post("/api/patterns/metacognition", json={
                "execution_trace": [
                    {"step": "search", "status": "success", "duration": 1.2},
                    {"step": "analyze", "status": "error", "duration": 5.0, "error": "timeout"},
                    {"step": "retry_analyze", "status": "success", "duration": 2.1}
                ],
                "performance_metrics": {
                    "accuracy": 0.75,
                    "speed": 0.4,
                    "reliability": 0.6
                }
            })

        assert resp.status_code == 200, f"API error: {resp.text}"
        data = resp.json()

        assert data["pattern"] == "metacognition"
        assert "performance_assessment" in data
        assert 0 <= data["confidence_level"] <= 1
