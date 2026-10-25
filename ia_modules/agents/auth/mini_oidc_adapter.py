"""MiniOIDCAdapter — IDP adapter backed by local RSA signing + DB.

Used when AGENT_AUTH_MODE=local (default). No external IDP needed.
Registers "clients" as rows in agent_api_keys with idp_client_id
and idp_client_secret_hash columns. Tokens signed locally.
"""

import hashlib
import json
import logging
import os
import secrets
import uuid

from .adapter import IDPAdapter, ClientCredentials

logger = logging.getLogger(__name__)


def _audience() -> str:
    """Read A2A_AUDIENCE at call time with a local-default fallback.

    Unlike ``KeycloakAdapter`` we DO allow a default here — the mini
    adapter runs in-process and the platform operator is the same
    entity that issues and validates tokens, so there's no
    cross-realm substitution risk to guard against. The default
    matches what the mini provider mints.
    """
    return os.getenv("A2A_AUDIENCE", "a2a-server")


class MiniOIDCAdapter(IDPAdapter):
    """Local IDP adapter — stores client credentials in DB, signs JWTs locally."""

    def __init__(self, db=None):
        self.db = db
        self._provider = None  # Lazy — created when issuer URL is known

    def _get_provider(self):
        if self._provider is None:
            from .provider import MiniOIDCProvider
            issuer = os.getenv("MINI_OIDC_ISSUER", "")
            if not issuer:
                base = (os.getenv("IA_MODULES_BASE_URL") or os.getenv("FIBERWISE_BASE_URL")
                        or os.getenv("PLATFORM_BASE_URL", "http://localhost:5555"))
                issuer = f"{base}/oidc"
            self._provider = MiniOIDCProvider(issuer=issuer)
        return self._provider

    async def register_client(
        self,
        agent_id: str,
        org_id: int,
        permissions: dict,
    ) -> ClientCredentials:
        """Create IDP client credentials for an agent.

        Generates a client_id + client_secret and stores the hash in DB.
        The permissions dict is stored as a2a_permissions JSON.
        """
        client_id = f"agent-{agent_id}-{uuid.uuid4().hex[:8]}"
        client_secret = secrets.token_urlsafe(48)
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        if self.db:
            await self.db.execute(
                """UPDATE agent_api_keys
                   SET idp_client_id = :client_id,
                       idp_client_secret_hash = :secret_hash,
                       a2a_permissions = :permissions
                   WHERE agent_id = :agent_id AND is_active = true""",
                {
                    "client_id": client_id,
                    "secret_hash": secret_hash,
                    "permissions": json.dumps(permissions),
                    "agent_id": str(agent_id),
                },
            )

        logger.info("Registered mini OIDC client: %s for agent %s", client_id, agent_id)
        return ClientCredentials(client_id=client_id, client_secret=client_secret)

    async def update_client_claims(self, client_id: str, permissions: dict):
        """Update the a2a permissions for an existing client."""
        if self.db:
            await self.db.execute(
                """UPDATE agent_api_keys
                   SET a2a_permissions = :permissions
                   WHERE idp_client_id = :client_id""",
                {
                    "permissions": json.dumps(permissions),
                    "client_id": client_id,
                },
            )
        logger.info("Updated claims for mini OIDC client: %s", client_id)

    async def delete_client(self, client_id: str):
        """Clear IDP credentials (the key row itself is managed by the platform)."""
        if self.db:
            await self.db.execute(
                """UPDATE agent_api_keys
                   SET idp_client_id = NULL,
                       idp_client_secret_hash = NULL
                   WHERE idp_client_id = :client_id""",
                {"client_id": client_id},
            )
        logger.info("Deleted mini OIDC client: %s", client_id)

    async def get_token(
        self,
        client_id: str,
        client_secret: str,
        audience: str = "",
    ) -> str:
        """Validate client credentials and issue a signed JWT."""
        audience = audience or _audience()

        # Validate client_secret against stored hash
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        row = None
        if self.db:
            row = await self.db.fetch_one(
                """SELECT agent_id, organization_id, app_id, scopes, a2a_permissions
                   FROM agent_api_keys
                   WHERE idp_client_id = :client_id
                     AND idp_client_secret_hash = :secret_hash
                     AND is_active = true""",
                {"client_id": client_id, "secret_hash": secret_hash},
            )

        if not row:
            raise ValueError("Invalid client credentials")

        row = dict(row)
        agent_id = row.get("agent_id", "")
        org_id = row.get("organization_id")
        app_id = row.get("app_id")

        # Parse scopes
        scopes_raw = row.get("scopes", "[]")
        if isinstance(scopes_raw, str):
            try:
                scopes = json.loads(scopes_raw)
            except json.JSONDecodeError:
                scopes = []
        else:
            scopes = scopes_raw or []

        # Parse a2a permissions
        perms_raw = row.get("a2a_permissions", "{}")
        if isinstance(perms_raw, str):
            try:
                a2a_perms = json.loads(perms_raw)
            except json.JSONDecodeError:
                a2a_perms = {}
        else:
            a2a_perms = perms_raw or {}

        # Issue token via provider
        provider = self._get_provider()
        result = provider.issue_token(
            subject=f"agent_{agent_id}",
            audience=audience,
            scopes=scopes,
            claims={
                "org_id": org_id,
                "app_id": app_id,
                "agent_id": agent_id,
                "a2a": a2a_perms,
            },
        )
        return result["access_token"]

    async def issue_token_for_agent(self, agent_id: str, audience: str = "") -> str:
        """Issue a JWT for an agent by agent_id — internal use only.

        Unlike get_token(), this does NOT require the client_secret.
        Used by the platform when it needs a token for an agent it owns.
        The secret validation is skipped because the platform IS the IDP.
        """
        audience = audience or _audience()

        row = None
        if self.db:
            row = await self.db.fetch_one(
                """SELECT agent_id, organization_id, app_id, scopes, a2a_permissions
                   FROM agent_api_keys
                   WHERE agent_id = :agent_id
                     AND idp_client_id IS NOT NULL
                     AND is_active = true
                   LIMIT 1""",
                {"agent_id": str(agent_id)},
            )

        if not row:
            raise ValueError(f"No IDP-registered key found for agent {agent_id}")

        row = dict(row)
        org_id = row.get("organization_id")
        app_id = row.get("app_id")

        scopes_raw = row.get("scopes", "[]")
        if isinstance(scopes_raw, str):
            try:
                scopes = json.loads(scopes_raw)
            except json.JSONDecodeError:
                scopes = []
        else:
            scopes = scopes_raw or []

        perms_raw = row.get("a2a_permissions", "{}")
        if isinstance(perms_raw, str):
            try:
                a2a_perms = json.loads(perms_raw)
            except json.JSONDecodeError:
                a2a_perms = {}
        else:
            a2a_perms = perms_raw or {}

        provider = self._get_provider()
        result = provider.issue_token(
            subject=f"agent_{agent_id}",
            audience=audience,
            scopes=scopes,
            claims={
                "org_id": org_id,
                "app_id": app_id,
                "agent_id": str(agent_id),
                "a2a": a2a_perms,
            },
        )
        return result["access_token"]

    async def validate_token(self, token: str, audience: str = "") -> dict:
        """Validate a JWT in-process using the local RSA public key.

        No HTTP — just signature verification and claim extraction.
        """
        from jose import jwt as jose_jwt, JWTError

        audience = audience or _audience()
        provider = self._get_provider()

        # Get public key PEM for verification
        from cryptography.hazmat.primitives import serialization
        pub_pem = provider._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        try:
            claims = jose_jwt.decode(
                token,
                pub_pem,
                algorithms=["RS256"],
                audience=audience,
            )
        except JWTError as e:
            raise ValueError(f"Token validation failed: {e}")

        return claims

    def get_discovery_url(self) -> str:
        provider = self._get_provider()
        return provider.issuer
