"""LocalJwtAdapter — IDPAdapter backed by LocalJwtAuth (HS256).

Used when ``AGENT_AUTH_MODE=local`` (the default). Unlike
``MiniOIDCAdapter``, this adapter does NOT spin up an RSA keypair, does
NOT need a database, and does NOT expose client_credentials endpoints.
It exists for a single purpose: give a local single-process demo a way
to validate bearer tokens on the user→backend edge using the *same*
HS256 secret the subprocess gate already uses.

Why not MiniOIDCAdapter?
    MiniOIDCAdapter carries a lot of weight the showcase doesn't use:
    DB-backed client credentials, `register_client`/`delete_client`,
    an RSA keypair, a JWKS endpoint. Those exist to make the adapter a
    drop-in replacement for Keycloak at the A2A server layer. The
    showcase has no A2A server — it's one process — and the browser's
    only need is "give me a bearer I can send". LocalJwtAdapter is the
    minimal thing that satisfies that need and reuses the HS256 secret
    the parent→child boundary already has on disk.

Secret path
    The adapter reads ``LOCAL_JWT_SECRET_PATH`` at construction time.
    Callers (e.g. the showcase's ``build_pipeline``) should set this
    to the same path they pass to ``LocalJwtAuth(...)`` so both
    boundaries share one signing secret. If the env var is unset,
    falls back to ``./data/jwt_secret``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from .adapter import IDPAdapter, ClientCredentials
from .local_jwt_auth import LocalJwtAuth


logger = logging.getLogger(__name__)

_DEFAULT_SECRET_PATH = "./data/jwt_secret"


class LocalJwtAdapter(IDPAdapter):
    """HS256-backed IDP adapter for single-process local demos.

    Only ``validate_token`` and ``issue_token_for_agent`` do real work.
    The client-management methods raise ``NotImplementedError`` because
    there is no IDP database to manage — this adapter is a thin wrapper
    over a single file-backed signing secret.
    """

    def __init__(self, db=None, secret_path: Optional[str] = None):
        # db is accepted for protocol compatibility with the other
        # adapters but is ignored — there's no client database.
        self.db = db
        resolved = secret_path or os.getenv("LOCAL_JWT_SECRET_PATH") or _DEFAULT_SECRET_PATH
        self._auth = LocalJwtAuth(Path(resolved))

    # ------------------------------------------------------------------
    # Client management — not supported. The showcase never calls these.
    # ------------------------------------------------------------------

    async def register_client(
        self,
        agent_id: str,
        org_id: int,
        permissions: dict,
    ) -> ClientCredentials:
        raise NotImplementedError(
            "LocalJwtAdapter does not manage clients. Switch to "
            "MiniOIDCAdapter or KeycloakAdapter if you need a DB-backed "
            "client registry."
        )

    async def update_client_claims(self, client_id: str, permissions: dict):
        raise NotImplementedError("LocalJwtAdapter does not manage clients.")

    async def delete_client(self, client_id: str):
        raise NotImplementedError("LocalJwtAdapter does not manage clients.")

    async def get_token(
        self,
        client_id: str,
        client_secret: str,
        audience: str = "",
    ) -> str:
        raise NotImplementedError(
            "LocalJwtAdapter has no client_credentials flow. "
            "Use issue_token_for_agent() or mint_user_token() directly."
        )

    # ------------------------------------------------------------------
    # Token minting + validation — the actual useful surface.
    # ------------------------------------------------------------------

    async def issue_token_for_agent(self, agent_id: str, audience: str = "") -> str:
        """Issue a user token for the local-mode demo.

        ``agent_id`` is used as the ``sub`` claim. ``audience`` is
        ignored because ``LocalJwtAuth`` hardcodes its audience; all
        tokens in local mode share one signer.
        """
        return self._auth.mint_user_token(sub=str(agent_id))

    async def validate_token(self, token: str, audience: str = "") -> dict:
        """Verify the HS256 signature and return the claims dict.

        Raises ``ValueError`` on any validation failure — the FastAPI
        edge converts that into HTTP 401.

        The specific ``JWTError`` subclass (``ExpiredSignatureError``,
        ``JWTClaimsError``, ``JWSError``, ``JWTError``) is logged
        server-side at debug level before being collapsed into a
        bare ``ValueError`` ([31]). This preserves the
        public-facing generic-error contract while giving operators
        enough detail in logs to triage clock skew vs. wrong-signer
        vs. malformed token scenarios.
        """
        from jose import JWTError

        try:
            return self._auth.validate_token(token)
        except JWTError as exc:
            logger.debug(
                "LocalJwtAdapter rejected token (%s): %s",
                type(exc).__name__,
                exc,
            )
            raise ValueError(f"Token validation failed: {exc}")

    def get_discovery_url(self) -> str:
        # No discovery document — everything is in-process.
        return ""

    # ------------------------------------------------------------------
    # Convenience hook for the showcase's /api/auth/local-login route.
    # ------------------------------------------------------------------

    def mint_user_token(self, sub: str = "local-user") -> str:
        """Mint a wide-open user bearer for the local-mode demo."""
        return self._auth.mint_user_token(sub=sub)
