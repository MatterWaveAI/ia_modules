"""KeycloakAdapter — IDP adapter for external Keycloak (or compatible) IDPs.

Used when AGENT_AUTH_MODE=oidc. Calls the Keycloak Admin REST API to
register/update clients, and the token endpoint for client_credentials.

This adapter can be used with any OIDC provider that has a compatible
admin API. For providers with different admin APIs (Auth0, Cognito),
create a new adapter implementing IDPAdapter.
"""

import json
import logging
import os
import time

import httpx

from .adapter import IDPAdapter, ClientCredentials

logger = logging.getLogger(__name__)

# Minimum seconds between discovery refreshes triggered by a signature
# failure. Without this, a burst of requests carrying bogus tokens would
# cause a thundering herd of OIDC discovery + JWKS fetches against the
# IdP. 60s is short enough that a real key rotation is picked up
# promptly and long enough that a probing attacker can't DoS the IdP. ([32])
_JWKS_REFRESH_COOLDOWN_SECONDS = 60.0


# All env reads go through these helpers so tests can monkeypatch
# after import and operators can change configuration without
# restarting just because a module-level capture got baked in.

def _env(name: str) -> str:
    return os.getenv(name, "")


def _looks_like_signature_failure(exc: Exception) -> bool:
    """Heuristic for "this JWTError was a signature mismatch".

    python-jose raises ``JWSError`` / ``JWSSignatureError`` for bad
    signatures, but the error class hierarchy has varied over minor
    versions — match on the class name and message substring to
    cover every release the showcase might be pinned to. We only
    retry after a signature failure ([32]); expired tokens and
    audience mismatches are not helped by a fresh JWKS.
    """
    name = type(exc).__name__
    if "Signature" in name or "JWSError" in name:
        return True
    msg = str(exc).lower()
    return "signature" in msg


def _required_audience() -> str:
    """Return the expected JWT audience. Raises if not configured.

    We deliberately refuse to fall back to a default here — a wrong
    default silently validates or silently rejects tokens depending on
    realm configuration. Failing loud is the only safe option.
    """
    aud = os.getenv("A2A_AUDIENCE", "").strip()
    if not aud:
        raise ValueError(
            "A2A_AUDIENCE is not set. KeycloakAdapter needs an explicit "
            "audience to validate tokens against — set A2A_AUDIENCE to "
            "the client id the backend expects tokens to be issued for."
        )
    return aud


class KeycloakAdapter(IDPAdapter):
    """External Keycloak IDP adapter via Admin REST API."""

    def __init__(self, db=None):
        if not _env("IDP_ADMIN_URL") or not _env("IDP_TOKEN_URL"):
            raise ValueError(
                "AGENT_AUTH_MODE=oidc requires IDP_ADMIN_URL and IDP_TOKEN_URL env vars"
            )
        self.db = db
        self._jwks_cache: dict | None = None
        self._issuer_cache: str | None = None
        # Timestamp of the last successful discovery refresh, used to
        # rate-limit refreshes triggered by signature failures ([32]).
        self._last_refresh_ts: float = 0.0

    async def _get_admin_token(self) -> str:
        """Get an admin access token for Keycloak Admin REST API."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(
                _env("IDP_TOKEN_URL"),
                data={
                    "grant_type": "client_credentials",
                    "client_id": _env("IDP_ADMIN_CLIENT_ID"),
                    "client_secret": _env("IDP_ADMIN_CLIENT_SECRET"),
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def _find_client(self, admin_token: str, client_id: str) -> dict:
        """Find a Keycloak client by clientId, return the full client representation."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(
                f"{_env('IDP_ADMIN_URL')}/clients",
                params={"clientId": client_id},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()
            clients = resp.json()
            if not clients:
                raise ValueError(f"Keycloak client not found: {client_id}")
            return clients[0]

    async def _get_client_secret(self, admin_token: str, kc_id: str) -> str:
        """Retrieve the client secret from Keycloak Admin API."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(
                f"{_env('IDP_ADMIN_URL')}/clients/{kc_id}/client-secret",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()
            return resp.json()["value"]

    def _build_a2a_protocol_mappers(self, agent_id: str, permissions: dict, org_id: int) -> list:
        """Build Keycloak protocol mappers that inject a2a claims into JWTs."""
        return [
            {
                "name": "a2a-permissions",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-hardcoded-claim-mapper",
                "config": {
                    "claim.name": "a2a",
                    "claim.value": json.dumps(permissions),
                    "jsonType.label": "JSON",
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "false",
                },
            },
            {
                "name": "a2a-org-id",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-hardcoded-claim-mapper",
                "config": {
                    "claim.name": "org_id",
                    "claim.value": str(org_id),
                    "jsonType.label": "int",
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "false",
                },
            },
            {
                "name": "a2a-agent-id",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-hardcoded-claim-mapper",
                "config": {
                    "claim.name": "agent_id",
                    "claim.value": str(agent_id),
                    "jsonType.label": "String",
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "false",
                },
            },
        ]

    async def register_client(
        self,
        agent_id: str,
        org_id: int,
        permissions: dict,
    ) -> ClientCredentials:
        """Register a new Keycloak client for this agent."""
        admin_token = await self._get_admin_token()
        client_id = f"agent-{agent_id}"

        payload = {
            "clientId": client_id,
            "enabled": True,
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "clientAuthenticatorType": "client-secret",
            "protocol": "openid-connect",
            "attributes": {
                "a2a.permissions": json.dumps(permissions),
                "a2a.org_id": str(org_id),
                "a2a.agent_id": str(agent_id),
            },
            "protocolMappers": self._build_a2a_protocol_mappers(agent_id, permissions, org_id),
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(
                f"{_env('IDP_ADMIN_URL')}/clients",
                json=payload,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()

            location = resp.headers.get("Location", "")
            if location:
                secret_url = f"{location}/client-secret"
            else:
                kc_client = await self._find_client(admin_token, client_id)
                secret_url = f"{_env('IDP_ADMIN_URL')}/clients/{kc_client['id']}/client-secret"

            secret_resp = await client.post(
                secret_url,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            secret_resp.raise_for_status()
            client_secret = secret_resp.json()["value"]

        logger.info("Registered Keycloak client: %s for agent %s", client_id, agent_id)
        return ClientCredentials(client_id=client_id, client_secret=client_secret)

    async def update_client_claims(self, client_id: str, permissions: dict):
        """Update the a2a attributes and protocol mappers on an existing Keycloak client."""
        admin_token = await self._get_admin_token()
        kc_client = await self._find_client(admin_token, client_id)
        kc_id = kc_client["id"]

        kc_client.setdefault("attributes", {})
        kc_client["attributes"]["a2a.permissions"] = json.dumps(permissions)

        for mapper in kc_client.get("protocolMappers", []):
            if mapper.get("name") == "a2a-permissions":
                mapper["config"]["claim.value"] = json.dumps(permissions)

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.put(
                f"{_env('IDP_ADMIN_URL')}/clients/{kc_id}",
                json=kc_client,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()

        logger.info("Updated Keycloak client claims: %s", client_id)

    async def delete_client(self, client_id: str):
        """Delete a Keycloak client."""
        admin_token = await self._get_admin_token()

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            list_resp = await client.get(
                f"{_env('IDP_ADMIN_URL')}/clients",
                params={"clientId": client_id},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            list_resp.raise_for_status()
            clients = list_resp.json()
            if not clients:
                logger.warning("Keycloak client not found for deletion: %s", client_id)
                return

            kc_id = clients[0]["id"]
            resp = await client.delete(
                f"{_env('IDP_ADMIN_URL')}/clients/{kc_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()

        logger.info("Deleted Keycloak client: %s", client_id)

    async def get_token(
        self,
        client_id: str,
        client_secret: str,
        audience: str = "",
    ) -> str:
        """Request a client_credentials JWT from Keycloak."""
        audience = audience or _required_audience()

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(
                _env("IDP_TOKEN_URL"),
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "audience": audience,
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def issue_token_for_agent(self, agent_id: str, audience: str = "") -> str:
        """Issue a JWT for an agent — looks up client_id from DB, gets secret from Keycloak."""
        audience = audience or _required_audience()

        if not self.db:
            raise RuntimeError("KeycloakAdapter requires db for issue_token_for_agent")

        row = await self.db.fetch_one(
            """SELECT idp_client_id
               FROM agent_api_keys
               WHERE agent_id = :agent_id
                 AND idp_client_id IS NOT NULL
                 AND is_active = true
               LIMIT 1""",
            {"agent_id": str(agent_id)},
        )
        if not row:
            raise ValueError(f"No IDP-registered key found for agent {agent_id}")

        idp_client_id = dict(row)["idp_client_id"]

        admin_token = await self._get_admin_token()
        kc_client = await self._find_client(admin_token, idp_client_id)
        client_secret = await self._get_client_secret(admin_token, kc_client["id"])

        return await self.get_token(idp_client_id, client_secret, audience)

    async def _fetch_discovery(self, force: bool = False) -> dict:
        """Fetch the OIDC discovery document, caching the result.

        Cached for the lifetime of the adapter — two HTTP calls per
        request is a cheap DoS vector, and the discovery document is
        rarely refreshed in practice. Pass ``force=True`` to bypass
        the cache on a cache miss (e.g. a token signed by a key
        rotated in since we cached) — the caller is expected to
        rate-limit with ``_last_refresh_ts`` first. ([32])
        """
        if (
            not force
            and self._jwks_cache is not None
            and self._issuer_cache is not None
        ):
            return {"jwks": self._jwks_cache, "issuer": self._issuer_cache}

        discovery_url = self.get_discovery_url()
        if not discovery_url:
            raise ValueError("OIDC_DISCOVERY_URL not configured for token validation")

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            disc_resp = await client.get(f"{discovery_url}/.well-known/openid-configuration")
            disc_resp.raise_for_status()
            disc = disc_resp.json()

            jwks_uri = disc["jwks_uri"]
            issuer = disc["issuer"]

            jwks_resp = await client.get(jwks_uri)
            jwks_resp.raise_for_status()
            jwks_data = jwks_resp.json()

        self._jwks_cache = jwks_data
        self._issuer_cache = issuer
        self._last_refresh_ts = time.monotonic()
        return {"jwks": jwks_data, "issuer": issuer}

    async def validate_token(self, token: str, audience: str = "") -> dict:
        """Validate a JWT by checking signature, audience and issuer.

        Enforces:
          - Signature against the discovery-published JWKS
          - ``aud`` against the configured ``A2A_AUDIENCE`` (caller may
            override per call, but must not be empty)
          - ``iss`` against the discovery document's ``issuer`` field
          - ``exp`` / ``nbf`` (handled by ``jose.jwt.decode``)

        Missing ``A2A_AUDIENCE`` or ``OIDC_DISCOVERY_URL`` raises
        ``ValueError`` rather than silently falling back to a default.

        On a JWKS signature failure the adapter will refresh the
        cached discovery document and retry exactly once, subject to
        a ``_JWKS_REFRESH_COOLDOWN_SECONDS`` rate limit to avoid a
        thundering herd against the IdP when a flood of bogus tokens
        arrives. ([32])
        """
        from jose import jwt as jose_jwt, JWTError

        audience = audience or _required_audience()

        discovery = await self._fetch_discovery()

        try:
            return jose_jwt.decode(
                token,
                discovery["jwks"],
                algorithms=["RS256"],
                audience=audience,
                issuer=discovery["issuer"],
            )
        except JWTError as first_err:
            # If the first failure was a signature mismatch and the
            # cooldown window has elapsed, refresh discovery once and
            # retry. Any JWTError subclass can bubble — we only
            # refresh on signature failures because expired tokens
            # and audience mismatches won't be fixed by a new JWKS.
            if not _looks_like_signature_failure(first_err):
                raise ValueError(f"Token validation failed: {first_err}")

            now = time.monotonic()
            if now - self._last_refresh_ts < _JWKS_REFRESH_COOLDOWN_SECONDS:
                logger.debug(
                    "JWKS signature failure but refresh cooldown "
                    "still active; rejecting token"
                )
                raise ValueError(f"Token validation failed: {first_err}")

            logger.info("Signature failed — refreshing JWKS and retrying once")
            try:
                discovery = await self._fetch_discovery(force=True)
            except Exception as refresh_err:  # noqa: BLE001
                logger.warning("JWKS refresh failed: %s", refresh_err)
                raise ValueError(f"Token validation failed: {first_err}")

            try:
                return jose_jwt.decode(
                    token,
                    discovery["jwks"],
                    algorithms=["RS256"],
                    audience=audience,
                    issuer=discovery["issuer"],
                )
            except JWTError as retry_err:
                raise ValueError(f"Token validation failed: {retry_err}")

    def get_discovery_url(self) -> str:
        return _env("OIDC_DISCOVERY_URL")
