"""Agent Auth — IDP adapter for agent key authentication.

Supports three modes, selected via ``AGENT_AUTH_MODE``:

- ``local`` (default): ``LocalJwtAdapter`` — HS256, single file-backed
  secret, no database. Single-process demos (ia_showcase).
- ``mini-oidc``: ``MiniOIDCAdapter`` — RSA-signed JWTs, DB-backed
  client registry, in-process JWKS. For platform services that need
  OIDC semantics without an external IDP.
- ``oidc``: ``KeycloakAdapter`` — real external Keycloak (or
  Auth0/Cognito) via OIDC discovery + JWKS.
"""

import os

from .adapter import IDPAdapter, ClientCredentials
from .mini_oidc_adapter import MiniOIDCAdapter
from .keycloak_adapter import KeycloakAdapter
from .local_jwt_adapter import LocalJwtAdapter
from .defaults import get_default_permissions, DEFAULT_A2A_PERMISSIONS
from .local_jwt_auth import LocalJwtAuth


def get_adapter(db=None) -> IDPAdapter:
    """Get the configured IDP adapter.

    Args:
        db: Database provider (used by ``mini-oidc`` and ``oidc`` adapters).
    """
    mode = os.getenv("AGENT_AUTH_MODE", "local")
    if mode == "oidc":
        return KeycloakAdapter(db=db)
    if mode == "mini-oidc":
        return MiniOIDCAdapter(db=db)
    return LocalJwtAdapter(db=db)


__all__ = [
    "IDPAdapter",
    "ClientCredentials",
    "LocalJwtAdapter",
    "MiniOIDCAdapter",
    "KeycloakAdapter",
    "LocalJwtAuth",
    "get_adapter",
    "get_default_permissions",
    "DEFAULT_A2A_PERMISSIONS",
]
