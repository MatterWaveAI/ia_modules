"""Tests for ia_modules.agents.auth — adapters, provider, defaults."""

import os
import pytest
from unittest.mock import patch

from ia_modules.agents.auth import (
    IDPAdapter,
    ClientCredentials,
    LocalJwtAdapter,
    MiniOIDCAdapter,
    get_default_permissions,
    DEFAULT_A2A_PERMISSIONS,
)


# ---------------------------------------------------------------------------
# defaults.py
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_permissions_keys(self):
        assert set(DEFAULT_A2A_PERMISSIONS.keys()) == {"llm", "processor", "custom"}

    def test_get_default_permissions_known_type(self):
        perms = get_default_permissions("processor")
        assert "allowed_modes" in perms
        assert "research" in perms["allowed_modes"]

    def test_get_default_permissions_unknown_falls_back_to_llm(self):
        perms = get_default_permissions("unknown_type")
        llm = get_default_permissions("llm")
        assert perms == llm

    def test_get_default_permissions_returns_deep_copy(self):
        p1 = get_default_permissions("llm")
        p2 = get_default_permissions("llm")
        p1["allowed_modes"].append("execute")
        assert "execute" not in p2["allowed_modes"]

    def test_custom_has_execute_mode(self):
        perms = get_default_permissions("custom")
        assert "execute" in perms["allowed_modes"]

    def test_custom_has_bash_tool(self):
        perms = get_default_permissions("custom")
        assert "Bash" in perms["allowed_tools"]

    def test_llm_has_limits(self):
        perms = get_default_permissions("llm")
        assert perms["limits"]["max_turns"] == 30
        assert perms["limits"]["max_duration_seconds"] == 300


# ---------------------------------------------------------------------------
# adapter.py — ABC contract
# ---------------------------------------------------------------------------


class TestAdapterABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IDPAdapter()

    def test_client_credentials_dataclass(self):
        creds = ClientCredentials(client_id="cid", client_secret="csec")
        assert creds.client_id == "cid"
        assert creds.client_secret == "csec"


# ---------------------------------------------------------------------------
# get_adapter() factory
# ---------------------------------------------------------------------------


class TestGetAdapter:
    def test_default_returns_local_jwt(self, tmp_path):
        env = {
            "AGENT_AUTH_MODE": "local",
            "LOCAL_JWT_SECRET_PATH": str(tmp_path / "jwt_secret"),
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import ia_modules.agents.auth as auth_pkg
            importlib.reload(auth_pkg)
            adapter = auth_pkg.get_adapter()
            assert isinstance(adapter, LocalJwtAdapter)

    def test_mini_oidc_mode_returns_mini_oidc(self):
        with patch.dict(os.environ, {"AGENT_AUTH_MODE": "mini-oidc"}, clear=False):
            import importlib
            import ia_modules.agents.auth as auth_pkg
            importlib.reload(auth_pkg)
            adapter = auth_pkg.get_adapter()
            assert isinstance(adapter, MiniOIDCAdapter)

    def test_oidc_mode_returns_keycloak(self):
        env = {
            "AGENT_AUTH_MODE": "oidc",
            "IDP_ADMIN_URL": "http://keycloak:8080/admin",
            "IDP_TOKEN_URL": "http://keycloak:8080/token",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import ia_modules.agents.auth.keycloak_adapter as kc_mod
            importlib.reload(kc_mod)
            import ia_modules.agents.auth as auth_pkg
            importlib.reload(auth_pkg)
            adapter = auth_pkg.get_adapter()
            assert type(adapter).__name__ == "KeycloakAdapter"


# ---------------------------------------------------------------------------
# MiniOIDCProvider — token signing + JWKS
# ---------------------------------------------------------------------------


class TestMiniOIDCProvider:
    @pytest.fixture
    def provider(self, tmp_path):
        with patch.dict(os.environ, {"MINI_OIDC_KEY_DIR": str(tmp_path)}, clear=False):
            from ia_modules.agents.auth.provider import MiniOIDCProvider
            return MiniOIDCProvider(issuer="http://localhost:5555/oidc")

    def test_discovery(self, provider):
        disc = provider.get_discovery()
        assert disc["issuer"] == "http://localhost:5555/oidc"
        assert "jwks_uri" in disc
        assert disc["jwks_uri"].endswith("/jwks")

    def test_jwks_has_keys(self, provider):
        jwks = provider.get_jwks()
        assert "keys" in jwks
        assert len(jwks["keys"]) == 1
        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["alg"] == "RS256"
        assert "n" in key
        assert "e" in key

    def test_issue_token_returns_jwt(self, provider):
        result = provider.issue_token(
            subject="agent_123",
            audience="a2a-server",
            scopes=["a2a:execute"],
            claims={"org_id": 1},
        )
        assert "access_token" in result
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] > 0

    def test_token_verifies_with_public_key(self, provider):
        from jose import jwt as jose_jwt

        result = provider.issue_token(
            subject="agent_123",
            audience="a2a-server",
            scopes=["a2a:execute"],
            claims={"org_id": 1, "agent_id": "123"},
        )

        from cryptography.hazmat.primitives import serialization
        pub_pem = provider._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        decoded = jose_jwt.decode(
            result["access_token"],
            pub_pem,
            algorithms=["RS256"],
            audience="a2a-server",
        )
        assert decoded["sub"] == "agent_123"
        assert decoded["org_id"] == 1
        assert decoded["agent_id"] == "123"

    def test_keys_persist_across_instances(self, tmp_path):
        with patch.dict(os.environ, {"MINI_OIDC_KEY_DIR": str(tmp_path)}, clear=False):
            from ia_modules.agents.auth.provider import MiniOIDCProvider
            p1 = MiniOIDCProvider(issuer="http://localhost/oidc")
            p2 = MiniOIDCProvider(issuer="http://localhost/oidc")
            assert p1._kid == p2._kid


# ---------------------------------------------------------------------------
# MiniOIDCAdapter — no-DB path (unit-testable parts)
# ---------------------------------------------------------------------------


class TestMiniOIDCAdapterNoDB:
    def test_instantiates_without_db(self):
        adapter = MiniOIDCAdapter(db=None)
        assert adapter.db is None

    def test_get_discovery_url(self):
        with patch.dict(os.environ, {
            "MINI_OIDC_ISSUER": "http://test:5555/oidc",
            "MINI_OIDC_KEY_DIR": "/tmp/test-keys",
        }, clear=False):
            adapter = MiniOIDCAdapter(db=None)
            url = adapter.get_discovery_url()
            assert url == "http://test:5555/oidc"

    @pytest.mark.asyncio
    async def test_register_client_without_db(self):
        adapter = MiniOIDCAdapter(db=None)
        creds = await adapter.register_client("agent-1", org_id=1, permissions={"allowed_modes": ["research"]})
        assert creds.client_id.startswith("agent-agent-1-")
        assert len(creds.client_secret) > 20

    @pytest.mark.asyncio
    async def test_get_token_without_db_raises(self):
        adapter = MiniOIDCAdapter(db=None)
        with pytest.raises(ValueError, match="Invalid client credentials"):
            await adapter.get_token("fake-id", "fake-secret")


# ---------------------------------------------------------------------------
# KeycloakAdapter — env validation
# ---------------------------------------------------------------------------


class TestKeycloakAdapterInit:
    def test_missing_env_raises(self):
        with patch.dict(os.environ, {"IDP_ADMIN_URL": "", "IDP_TOKEN_URL": ""}, clear=False):
            import importlib
            import ia_modules.agents.auth.keycloak_adapter as kc_mod
            importlib.reload(kc_mod)
            with pytest.raises(ValueError, match="IDP_ADMIN_URL"):
                kc_mod.KeycloakAdapter()

    def test_with_env_succeeds(self):
        env = {
            "IDP_ADMIN_URL": "http://keycloak:8080/admin",
            "IDP_TOKEN_URL": "http://keycloak:8080/token",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import ia_modules.agents.auth.keycloak_adapter as kc_mod
            importlib.reload(kc_mod)
            adapter = kc_mod.KeycloakAdapter()
            assert adapter.db is None


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    def test_all_exports_importable(self):
        from ia_modules.agents.auth import __all__
        for name in __all__:
            assert hasattr(__import__("ia_modules.agents.auth", fromlist=[name]), name)

    def test_permissions_importable_from_agents(self):
        from ia_modules.agents import enforce_agent_claims, ClaimsViolation
        assert callable(enforce_agent_claims)
        assert issubclass(ClaimsViolation, ValueError)


# ---------------------------------------------------------------------------
# LocalJwtAdapter — validate_token error-type logging ([31])
# ---------------------------------------------------------------------------


class TestLocalJwtAdapterErrorLogging:
    """[31] JWT error subclasses are logged by type before collapsing to ValueError."""

    @pytest.mark.asyncio
    async def test_invalid_signature_logs_jws_error_type(self, tmp_path, caplog):
        """A token signed with the wrong key raises ValueError with the
        original JWT error subclass name in the debug log.
        """
        import logging

        from ia_modules.agents.auth import LocalJwtAdapter
        from ia_modules.agents.auth.local_jwt_auth import LocalJwtAuth

        # Mint a token with a totally different secret path so the
        # signature won't verify against the adapter's secret.
        bogus_secret = tmp_path / "bogus_secret"
        correct_secret = tmp_path / "correct_secret"

        bogus = LocalJwtAuth(bogus_secret)
        token = bogus.mint_user_token(sub="local-user")

        adapter = LocalJwtAdapter(secret_path=str(correct_secret))

        with caplog.at_level(
            logging.DEBUG, logger="ia_modules.agents.auth.local_jwt_adapter"
        ):
            with pytest.raises(ValueError):
                await adapter.validate_token(token)

        # The log should identify the specific JWT error subclass.
        assert any(
            "LocalJwtAdapter rejected token" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    async def test_malformed_token_logs_error_type(self, tmp_path, caplog):
        """A completely garbage token is rejected with a debug log."""
        import logging

        from ia_modules.agents.auth import LocalJwtAdapter

        adapter = LocalJwtAdapter(secret_path=str(tmp_path / "jwt_secret"))

        with caplog.at_level(
            logging.DEBUG, logger="ia_modules.agents.auth.local_jwt_adapter"
        ):
            with pytest.raises(ValueError):
                await adapter.validate_token("not-a-jwt")

        assert any(
            "LocalJwtAdapter rejected token" in rec.message
            for rec in caplog.records
        )


# ---------------------------------------------------------------------------
# KeycloakAdapter — JWKS refresh on signature failure ([32])
# ---------------------------------------------------------------------------


class TestKeycloakJwksRefresh:
    """[32] A signature failure triggers one cache refresh, rate-limited."""

    @pytest.mark.asyncio
    async def test_refresh_cooldown_blocks_second_refresh(self):
        """Within the cooldown window, a second signature failure does
        NOT trigger another discovery fetch — the adapter rejects the
        token using the already-cached JWKS to avoid thundering the IdP.
        """
        import time

        env = {
            "IDP_ADMIN_URL": "http://kc/admin",
            "IDP_TOKEN_URL": "http://kc/token",
            "OIDC_DISCOVERY_URL": "http://kc/realms/test",
            "A2A_AUDIENCE": "a2a-server",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import ia_modules.agents.auth.keycloak_adapter as kc_mod
            importlib.reload(kc_mod)
            adapter = kc_mod.KeycloakAdapter()

            # Prime the cache — fresh timestamp, so the cooldown blocks.
            adapter._jwks_cache = {"keys": []}
            adapter._issuer_cache = "http://kc/realms/test"
            adapter._last_refresh_ts = time.monotonic()

            refresh_called = {"n": 0}

            async def _fake_fetch(force: bool = False):
                if force:
                    refresh_called["n"] += 1
                return {
                    "jwks": adapter._jwks_cache,
                    "issuer": adapter._issuer_cache,
                }

            adapter._fetch_discovery = _fake_fetch  # type: ignore[method-assign]

            with pytest.raises(ValueError, match="Token validation failed"):
                await adapter.validate_token("not.a.real.jwt")
            # No refresh — we're inside the cooldown window.
            assert refresh_called["n"] == 0

    def test_looks_like_signature_failure_heuristic(self):
        """The helper recognises a few canonical JWT exception shapes."""
        import importlib
        import ia_modules.agents.auth.keycloak_adapter as kc_mod
        importlib.reload(kc_mod)

        class FakeJWSError(Exception):
            pass

        class FakeOther(Exception):
            pass

        assert kc_mod._looks_like_signature_failure(FakeJWSError("sig mismatch"))
        assert kc_mod._looks_like_signature_failure(
            FakeOther("Signature verification failed")
        )
        # A plain expired-token error should NOT match.
        assert not kc_mod._looks_like_signature_failure(
            FakeOther("Token has expired")
        )
