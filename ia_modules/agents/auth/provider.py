"""MiniOIDCProvider — built-in OIDC token issuer for standalone deployments.

Signs JWTs with a local RSA key pair so the A2A server can validate them
via standard JWKS, without needing an external IDP like Keycloak.

Not production-grade security (single-server key, no HA key distribution),
but structurally correct — same token format, same OIDC endpoints, same
validation path.
"""

import hashlib
import logging
import os
import time
from base64 import urlsafe_b64encode
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

logger = logging.getLogger(__name__)

# Where RSA keys are stored on disk
_DEFAULT_KEY_DIR = os.getenv("MINI_OIDC_KEY_DIR", "")
_TOKEN_TTL = int(os.getenv("MINI_OIDC_TOKEN_TTL", "300"))


def _get_key_dir() -> Path:
    if _DEFAULT_KEY_DIR:
        return Path(_DEFAULT_KEY_DIR)
    # Default: DATA_DIR/oidc_keys or ~/.ia_modules/oidc_keys. The FIBERWISE_ names and
    # ~/.fiberwise are the pre-0.3.0 locations, still honoured so existing keys keep working.
    data_dir = os.getenv("IA_MODULES_DATA_DIR") or os.getenv("FIBERWISE_DATA_DIR", "")
    if data_dir:
        return Path(data_dir) / "oidc_keys"
    key_dir = Path.home() / ".ia_modules" / "oidc_keys"
    legacy_dir = Path.home() / ".fiberwise" / "oidc_keys"
    if not key_dir.exists() and legacy_dir.exists():
        return legacy_dir
    return key_dir


class MiniOIDCProvider:
    """Local OIDC token issuer with RSA key management."""

    def __init__(self, issuer: str):
        """
        Args:
            issuer: The issuer URL (e.g. http://localhost:5555/oidc).
                    Must match what the A2A server expects in OIDC_DISCOVERY_URL.
        """
        self.issuer = issuer.rstrip("/")
        self._key_dir = _get_key_dir()
        self._private_key = None
        self._public_key = None
        self._kid = None
        self._jwks_json = None
        self._load_or_generate_keys()

    def _load_or_generate_keys(self):
        """Load existing RSA key pair or generate a new one."""
        self._key_dir.mkdir(parents=True, exist_ok=True)
        priv_path = self._key_dir / "private.pem"
        pub_path = self._key_dir / "public.pem"

        if priv_path.exists() and pub_path.exists():
            self._private_key = serialization.load_pem_private_key(
                priv_path.read_bytes(), password=None,
            )
            self._public_key = serialization.load_pem_public_key(
                pub_path.read_bytes(),
            )
            logger.info("Loaded existing OIDC signing keys from %s", self._key_dir)
        else:
            self._private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048,
            )
            self._public_key = self._private_key.public_key()

            priv_path.write_bytes(self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            pub_path.write_bytes(self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
            logger.info("Generated new OIDC signing keys in %s", self._key_dir)

        # Compute kid from public key thumbprint (SHA256 of DER)
        pub_der = self._public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._kid = hashlib.sha256(pub_der).hexdigest()[:16]

        # Pre-build JWKS response
        pub_numbers = self._public_key.public_numbers()
        n_bytes = pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, "big")
        e_bytes = pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, "big")
        self._jwks_json = {
            "keys": [{
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": self._kid,
                "n": urlsafe_b64encode(n_bytes).rstrip(b"=").decode(),
                "e": urlsafe_b64encode(e_bytes).rstrip(b"=").decode(),
            }],
        }

    def get_discovery(self) -> dict:
        """Return OIDC Discovery document."""
        return {
            "issuer": self.issuer,
            "jwks_uri": f"{self.issuer}/jwks",
            "token_endpoint": f"{self.issuer}/token",
            "grant_types_supported": ["client_credentials"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "response_types_supported": ["token"],
        }

    def get_jwks(self) -> dict:
        """Return JWKS (public keys)."""
        return self._jwks_json  # type: ignore[return-value]

    def issue_token(
        self,
        subject: str,
        audience: str,
        scopes: list[str],
        claims: dict | None = None,
    ) -> dict:
        """Sign and return a JWT.

        Args:
            subject: The sub claim (e.g. agent_<agent_id>).
            audience: The aud claim (e.g. a2a-server).
            scopes: Space-joined into the scope claim.
            claims: Additional claims to include (org_id, app_id, a2a, etc.).

        Returns:
            {"access_token": "...", "token_type": "Bearer", "expires_in": 300}
        """
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": subject,
            "aud": audience,
            "iat": now,
            "exp": now + _TOKEN_TTL,
            "scope": " ".join(scopes),
        }
        if claims:
            payload.update(claims)

        # Sign with private key using python-jose
        priv_pem = self._private_key.private_bytes(  # type: ignore[union-attr]
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = jwt.encode(
            payload, priv_pem, algorithm="RS256",
            headers={"kid": self._kid},
        )

        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": _TOKEN_TTL,
        }
