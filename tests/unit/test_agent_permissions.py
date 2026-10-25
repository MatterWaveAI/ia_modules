"""Tests for ia_modules.agents.permissions — token-based enforcement."""

import pytest
from ia_modules.agents.permissions import enforce_agent_claims, ClaimsViolation


class TestEnforceCwd:
    """CWD enforcement via allowed_cwd patterns and app_id fallback."""

    def test_allowed_cwd_exact_match(self, tmp_path):
        cwd = str(tmp_path)
        claims = {"a2a": {"allowed_cwd": [cwd]}}
        enforce_agent_claims(claims, cwd)  # should not raise

    def test_allowed_cwd_child_dir(self, tmp_path):
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        claims = {"a2a": {"allowed_cwd": [str(tmp_path)]}}
        enforce_agent_claims(claims, str(child))  # should not raise

    def test_allowed_cwd_glob_strip(self, tmp_path):
        child = tmp_path / "workspace"
        child.mkdir()
        claims = {"a2a": {"allowed_cwd": [f"{tmp_path}/*"]}}
        enforce_agent_claims(claims, str(child))  # should not raise

    def test_allowed_cwd_string_not_list(self, tmp_path):
        claims = {"a2a": {"allowed_cwd": str(tmp_path)}}
        enforce_agent_claims(claims, str(tmp_path))  # should not raise

    def test_allowed_cwd_rejects_outside(self, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        claims = {"a2a": {"allowed_cwd": [str(allowed)]}}
        with pytest.raises(ClaimsViolation, match="not permitted"):
            enforce_agent_claims(claims, str(other))

    def test_app_id_fallback_pass(self, tmp_path):
        app_id = "my-app-123"
        cwd = tmp_path / "apps" / app_id / "workspace"
        cwd.mkdir(parents=True)
        claims = {"app_id": app_id}
        enforce_agent_claims(claims, str(cwd))  # should not raise

    def test_app_id_fallback_fail(self, tmp_path):
        claims = {"app_id": "my-app-123"}
        with pytest.raises(ClaimsViolation, match="does not match app_id"):
            enforce_agent_claims(claims, str(tmp_path))

    def test_no_cwd_constraints_passes(self, tmp_path):
        claims = {}
        enforce_agent_claims(claims, str(tmp_path))  # should not raise

    def test_empty_a2a_no_allowed_cwd_passes(self, tmp_path):
        claims = {"a2a": {}}
        enforce_agent_claims(claims, str(tmp_path))  # should not raise


class TestEnforceMode:
    """Mode enforcement via allowed_modes."""

    def test_allowed_mode(self):
        claims = {"a2a": {"allowed_modes": ["research", "plan"]}}
        enforce_agent_claims(claims, "/tmp", mode="research")  # should not raise

    def test_disallowed_mode(self):
        claims = {"a2a": {"allowed_modes": ["research"]}}
        with pytest.raises(ClaimsViolation, match="Mode 'execute'"):
            enforce_agent_claims(claims, "/tmp", mode="execute")

    def test_no_mode_constraint(self):
        claims = {"a2a": {}}
        enforce_agent_claims(claims, "/tmp", mode="execute")  # should not raise

    def test_mode_none_skips_check(self):
        claims = {"a2a": {"allowed_modes": ["research"]}}
        enforce_agent_claims(claims, "/tmp", mode=None)  # should not raise


class TestEnforceTools:
    """Tool enforcement via allowed_tools."""

    def test_allowed_tools(self):
        claims = {"a2a": {"allowed_tools": ["Read", "Glob", "Grep"]}}
        enforce_agent_claims(claims, "/tmp", tools=["Read", "Glob"])  # should not raise

    def test_disallowed_tools(self):
        claims = {"a2a": {"allowed_tools": ["Read", "Glob"]}}
        with pytest.raises(ClaimsViolation, match="Bash"):
            enforce_agent_claims(claims, "/tmp", tools=["Read", "Bash"])

    def test_no_tools_constraint(self):
        claims = {"a2a": {}}
        enforce_agent_claims(claims, "/tmp", tools=["Bash", "Write"])  # should not raise

    def test_tools_none_skips_check(self):
        claims = {"a2a": {"allowed_tools": ["Read"]}}
        enforce_agent_claims(claims, "/tmp", tools=None)  # should not raise

    def test_multiple_disallowed(self):
        claims = {"a2a": {"allowed_tools": ["Read"]}}
        with pytest.raises(ClaimsViolation, match="Bash"):
            enforce_agent_claims(claims, "/tmp", tools=["Bash", "Write"])


class TestCombined:
    """Combined enforcement — all checks run together."""

    def test_all_pass(self, tmp_path):
        claims = {
            "a2a": {
                "allowed_cwd": [str(tmp_path)],
                "allowed_modes": ["research"],
                "allowed_tools": ["Read", "Glob"],
            }
        }
        enforce_agent_claims(claims, str(tmp_path), mode="research", tools=["Read"])

    def test_cwd_fails_first(self, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        claims = {
            "a2a": {
                "allowed_cwd": [str(tmp_path / "allowed")],
                "allowed_modes": ["research"],
            }
        }
        with pytest.raises(ClaimsViolation, match="not permitted"):
            enforce_agent_claims(claims, str(other), mode="research")

    def test_empty_claims_all_pass(self, tmp_path):
        enforce_agent_claims({}, str(tmp_path), mode="execute", tools=["Bash"])
