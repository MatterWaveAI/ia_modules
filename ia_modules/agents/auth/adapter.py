"""IDPAdapter — abstract interface for IDP operations.

Implementations handle the difference between Keycloak Admin REST API
calls and local mini OIDC DB operations. Business logic calls adapter
methods without knowing which IDP is backing it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ClientCredentials:
    """Returned by register_client — store these with the agent key."""
    client_id: str
    client_secret: str


class IDPAdapter(ABC):

    @abstractmethod
    async def register_client(
        self,
        agent_id: str,
        org_id: int,
        permissions: dict,
    ) -> ClientCredentials:
        """Register a new IDP client for an agent.

        Args:
            agent_id: Agent ID.
            org_id: Organization the agent belongs to.
            permissions: The a2a permission dict to embed in tokens.

        Returns:
            ClientCredentials with client_id and client_secret.
        """

    @abstractmethod
    async def update_client_claims(self, client_id: str, permissions: dict):
        """Update the a2a claims on an existing IDP client."""

    @abstractmethod
    async def delete_client(self, client_id: str):
        """Remove a client from the IDP (on agent/key deletion)."""

    @abstractmethod
    async def get_token(
        self,
        client_id: str,
        client_secret: str,
        audience: str = "a2a-server",
    ) -> str:
        """Request a client_credentials JWT.

        Returns:
            The access_token string (a signed JWT).
        """

    @abstractmethod
    async def issue_token_for_agent(self, agent_id: str, audience: str = "") -> str:
        """Issue a JWT for an agent by agent_id — internal use only.

        Used by the platform when it needs a token for an agent it owns.
        How the secret is resolved depends on the adapter:
        - MiniOIDC: skips secret validation (platform IS the IDP)
        - Keycloak: retrieves the client secret via Admin API

        Args:
            agent_id: Agent ID.
            audience: The aud claim (defaults to A2A_AUDIENCE).

        Returns:
            The access_token string (a signed JWT).
        """

    @abstractmethod
    async def validate_token(self, token: str, audience: str = "") -> dict:
        """Validate a JWT and return its claims.

        This is the unified auth gate — called before any executor
        (subprocess or remote A2A) to verify the agent is authorized.

        Args:
            token: The JWT access_token string.
            audience: Expected audience claim. Defaults to A2A_AUDIENCE.

        Returns:
            Dict of validated claims (sub, agent_id, org_id, app_id,
            scopes, a2a permissions, etc.).

        Raises:
            ValueError: If the token is invalid, expired, or unauthorized.
        """

    @abstractmethod
    def get_discovery_url(self) -> str:
        """Return the OIDC Discovery URL for this adapter.

        The A2A server uses this to fetch JWKS and validate tokens.
        """
