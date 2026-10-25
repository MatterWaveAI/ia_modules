"""Local JWT-based agent auth for single-process deployments.

Threat model
------------
A host process runs an agent (e.g. OpenCode) as a child subprocess that
can touch the filesystem. The thing we want to prevent is that child
process getting itself launched under different parameters than the
parent authorized — e.g. a different cwd, a tool it wasn't granted, or
a different agent mode.

The parent Python process is trusted. Before every agent launch it:

  1. Mints an HS256-signed JWT whose `a2a` claim encodes the exact
     (cwd, mode, tools) triple the agent is allowed to run with.
  2. Verifies that token and calls `enforce_agent_claims()` — a pure
     function that raises `ClaimsViolation` if anything doesn't match.
  3. Only then does it shell out via its executor.

HS256 is the correct choice for this shape: the same process mints and
verifies, so a symmetric secret is sufficient. There is no value in
asymmetric crypto here because there is no second party — the parent
both signs and checks. The secret lives in a file under a caller-chosen
data dir; it is loaded into Python memory on startup and never placed
in `os.environ`, so it is not inherited by the agent subprocess.

Extending this to a real multi-user deployment
----------------------------------------------
Swap `LocalJwtAuth` for a class wrapping `ia_modules.agents.auth`'s
`KeycloakAdapter` (or any other OIDC adapter). The mint/verify method
shape stays identical, the `a2a` claim stays identical, and
`enforce_agent_claims` stays identical — only the token source and the
verification key change. You would additionally add a FastAPI auth
middleware that validates incoming user tokens, but nothing downstream
of this class (executor, pipelines, steps, frontends) would move.

Things this deliberately does NOT do
------------------------------------
- No subprocess isolation. The agent inherits most of the parent's env
  (that's how `OPENCODE_API_KEY` reaches it in the first place). For
  real isolation run the agent under a separate user or in a container.
- No refresh tokens, no revocation, no JWKS. Single-process demo.
- No Windows ACL hardening on the secret file. It's written under the
  caller-chosen data dir and relies on the OS file permissions of the
  user running the app.
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Iterable, Union

from jose import jwt

from ..permissions import ClaimsViolation, enforce_agent_claims

_AUDIENCE = "ia-showcase-agent"
_ISSUER = "ia-showcase-local"
_TOKEN_TTL_SECONDS = 600
_USER_TOKEN_TTL_SECONDS = 3600
_ALGORITHM = "HS256"

# Wide-open ``a2a`` claim used when minting *user* tokens for the
# local-mode demo. The user→backend boundary exists only so the
# browser can talk to an API that insists on a bearer; in local mode
# there's no multi-tenant isolation to enforce, so the token's a2a
# claim uses ``["*"]`` everywhere and real enforcement still happens
# at the parent→child boundary where ``mint()`` produces a *tight*
# claim bound to the actual (cwd, mode, tools) of the pipeline step.
_USER_TOKEN_WIDE_A2A = {
    "allowed_cwd": ["*"],
    "allowed_modes": ["*"],
    "allowed_tools": ["*"],
}
_LOCAL_USER_SUB = "local-user"


class LocalJwtAuth:
    """Mint + verify short-lived HS256 tokens bound to agent parameters.

    This is the single-process signer. To run against a real IdP,
    replace this class with one that wraps `KeycloakAdapter` — same two
    methods, same claim shape.
    """

    def __init__(self, secret_path: Union[Path, str]):
        self._secret = _load_or_create_secret(Path(secret_path))

    def mint(self, cwd: str, mode: str, tools: Iterable[str]) -> str:
        """Mint a signed token that binds the agent to (cwd, mode, tools)."""
        now = int(time.time())
        claims = {
            "iss": _ISSUER,
            "sub": "agent_showcase",
            "aud": _AUDIENCE,
            "iat": now,
            "exp": now + _TOKEN_TTL_SECONDS,
            "scopes": ["agent:run"],
            "a2a": {
                "allowed_cwd": [cwd],
                "allowed_modes": [mode],
                "allowed_tools": list(tools),
            },
        }
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def verify_and_enforce(
        self,
        token: str,
        cwd: str,
        mode: str,
        tools: Iterable[str],
    ) -> dict:
        """Verify the token signature and enforce its claims.

        Raises `ClaimsViolation` if the agent is asking to do something
        the token doesn't allow. Callers must treat this as fatal — do
        NOT wrap in a try/except that falls back to running anyway.
        """
        claims = jwt.decode(
            token,
            self._secret,
            algorithms=[_ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
        )
        enforce_agent_claims(claims, cwd=cwd, mode=mode, tools=list(tools))
        return claims

    def mint_user_token(self, sub: str = _LOCAL_USER_SUB) -> str:
        """Mint a bearer token for the user→backend boundary in local mode.

        Unlike ``mint()``, this token carries a wide-open ``a2a`` claim
        (``allowed_cwd=["*"]`` etc.) because the local-mode demo is
        single-tenant: the only purpose of the token is to let the
        browser satisfy the ``Authorization: Bearer`` check on the
        FastAPI edge. The real enforcement — the (cwd, mode, tools)
        tuple each pipeline step is allowed to run with — still happens
        at the parent→child boundary via ``mint`` / ``verify_and_enforce``.
        """
        now = int(time.time())
        claims = {
            "iss": _ISSUER,
            "sub": sub,
            "aud": _AUDIENCE,
            "iat": now,
            "exp": now + _USER_TOKEN_TTL_SECONDS,
            "scopes": ["showcase:user"],
            "a2a": dict(_USER_TOKEN_WIDE_A2A),
        }
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def validate_token(self, token: str) -> dict:
        """Verify the token signature and return its claims.

        Unlike ``verify_and_enforce``, this does NOT call
        ``enforce_agent_claims``. It's the user→backend validation
        path: the FastAPI edge only needs to know "is this token
        real and unexpired?", not "does it allow tool X for cwd Y?".
        Claim enforcement for the agent subprocess happens later,
        inside ``run_pipeline`` via ``enforce_agent_claims`` and
        inside ``SubprocessExecutor.execute()`` via
        ``verify_and_enforce``.
        """
        return jwt.decode(
            token,
            self._secret,
            algorithms=[_ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
        )


def _load_or_create_secret(path: Path) -> str:
    """Load the HS256 secret from `path`, generating it on first run.

    The secret stays in memory in the parent Python process. It is
    never written to any environment variable, so it is not inherited
    by the agent subprocess that the executor launches.

    Create is race-free: we use ``os.open(O_CREAT|O_EXCL|O_WRONLY, 0o600)``
    so two processes starting simultaneously can't both write the file
    (the loser gets ``FileExistsError`` and falls through to the read
    path). We also do NOT strip the read bytes — the secret is compared
    verbatim and a stray trailing newline would silently invalidate
    every token minted by a different instance.
    """
    path = Path(path)
    if path.is_file():
        return path.read_text(encoding="utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(32)

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError:
        # Lost the race with another process — read what it wrote.
        return path.read_text(encoding="utf-8")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(secret)
    except BaseException:
        # If the write fails, remove the empty/partial file so the
        # next run can retry cleanly instead of loading an empty secret.
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return secret


__all__ = ["LocalJwtAuth", "ClaimsViolation"]
