"""Who is asking: the identity of every request, taken from a Keycloak
access token, never from what the client says about itself.

| Token | Identity |
|---|---|
| A person through a person's channel (client_kind=person, e.g. platformctl) | person |
| An agent client (client_kind=agent, e.g. claude-code) with a person signed in | agent on behalf of that person |
| Client credentials (service-account-<client>) | autonomous agent of its owner team |

The person's teams are the Keycloak groups; an agent acting for a person
gets exactly those teams, and an autonomous agent only its owner team.

Until the portal signs people in with Keycloak (increment B of
docs/identity-and-access.md), it still calls with the channel token
PLATFORM_API_TOKEN and states the person and their teams from the catalog.
That path only ever identifies people, never agents.
"""

from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

PREFIX = "platform.starterkit.dev"
PLATFORM_TEAM = "platform-team"
NAME = re.compile(r"^[a-z0-9]([-a-z0-9._]{0,61}[a-z0-9])?$")


class Unauthenticated(Exception):
    """No identity, or not a valid one: sign in."""


@dataclass(frozen=True)
class Identity:
    kind: str                     # person | agent | autonomous
    person: str | None            # marta
    agent: str | None             # claude-code, ci-agent
    teams: tuple[str, ...]
    roles: tuple[str, ...] = ()
    channel: str = ""             # the OAuth client, or "portal"
    chain: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_agent(self) -> bool:
        return self.kind in ("agent", "autonomous")

    @property
    def requester(self) -> str:
        """How the Golden Paths and the audit trail record it."""
        return f"agent:{self.agent}" if self.is_agent else f"user:default/{self.person}"

    @property
    def display(self) -> str:
        if self.kind == "agent":
            return f"{self.agent} for {self.person}"
        return self.agent if self.kind == "autonomous" else self.person  # type: ignore[return-value]

    @property
    def in_platform_team(self) -> bool:
        return PLATFORM_TEAM in self.teams

    def annotations(self) -> dict[str, str]:
        """What the platform writes on every resource it creates. Kyverno
        protects these annotations: only the platform API can set them."""
        result = {f"{PREFIX}/requester-teams": ",".join(self.teams)}
        if self.is_agent:
            result[f"{PREFIX}/agent"] = self.agent or ""
        if self.person:
            result[f"{PREFIX}/on-behalf-of"] = self.person
        if self.chain:
            result[f"{PREFIX}/agent-chain"] = " > ".join(self.chain)
        return result

    def describe(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "person": self.person, "agent": self.agent, "teams": list(self.teams),
            "roles": list(self.roles), "channel": self.channel, "agentChain": list(self.chain),
            "requester": self.requester,
        }


def _chain(act: Any) -> tuple[str, ...]:
    """The `act` claim of token exchange, outermost actor first."""
    chain = []
    while isinstance(act, dict) and len(chain) < 10:
        actor = act.get("client_id") or act.get("azp") or act.get("sub")
        if actor:
            chain.append(str(actor))
        act = act.get("act")
    return tuple(chain)


def identity_from_claims(claims: Mapping[str, Any]) -> Identity:
    client = str(claims.get("azp") or claims.get("client_id") or "")
    username = str(claims.get("preferred_username") or "")
    if not client or not NAME.match(client):
        raise Unauthenticated("The token does not say which client it was issued to (azp).")
    roles = tuple(sorted((claims.get("realm_access") or {}).get("roles") or ()))
    chain = _chain(claims.get("act"))
    if username.startswith("service-account-") or not username:
        # Client credentials: an agent with no person behind it.
        owner = str(claims.get("owner_team") or "")
        return Identity("autonomous", None, client, (owner,) if owner else (), roles, client, chain)
    if not NAME.match(username):
        raise Unauthenticated("The token has no valid preferred_username.")
    teams = tuple(sorted({str(g).strip("/").split("/")[-1] for g in claims.get("groups") or () if g}))
    if claims.get("client_kind") == "person":
        return Identity("person", username, None, teams, roles, client, chain)
    # Any other client is an agent: the guardrails apply unless the realm says otherwise.
    return Identity("agent", username, client, teams, roles, client, chain)


class TokenVerifier:
    """Validates Keycloak access tokens: signature (JWKS), issuer, audience, expiry."""

    def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
        import jwt

        self.issuer, self.audience = issuer, audience
        self._jwt = jwt
        self._keys = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=10)

    def claims(self, token: str) -> dict[str, Any]:
        jwt = self._jwt
        try:
            key = self._keys.get_signing_key_from_jwt(token)
            return jwt.decode(token, key.key, algorithms=["RS256", "ES256", "PS256"], audience=self.audience,
                              issuer=self.issuer, leeway=30, options={"require": ["exp", "iss", "aud"]})
        except jwt.PyJWKClientConnectionError as err:
            raise Unauthenticated(f"Keycloak is not reachable to check the token: {err}") from err
        except jwt.PyJWTError as err:
            raise Unauthenticated(f"Invalid token: {err}") from err

    @classmethod
    def from_environment(cls) -> "TokenVerifier | None":
        issuer = os.environ.get("OIDC_ISSUER")
        if not issuer:
            return None
        jwks = os.environ.get("OIDC_JWKS_URL") or f"{issuer}/protocol/openid-connect/certs"
        return cls(issuer, os.environ.get("OIDC_AUDIENCE", "platform"), jwks)


class Authenticator:
    """Builds the identity of a request from its headers."""

    def __init__(self, verifier: Any | None, channel_token: str | None = None) -> None:
        self.verifier = verifier
        self.channel = f"Bearer {channel_token}".encode() if channel_token else None

    def identify(self, headers: Mapping[str, str]) -> Identity:
        authorization = headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise Unauthenticated("Sign in: send a Keycloak access token as Authorization: Bearer <token>.")
        if self.channel is not None and hmac.compare_digest(authorization.encode(), self.channel):
            return self._portal(headers)
        if self.verifier is None:
            raise Unauthenticated("This platform API has no identity provider configured (OIDC_ISSUER).")
        return identity_from_claims(self.verifier.claims(authorization[7:].strip()))

    @staticmethod
    def _portal(headers: Mapping[str, str]) -> Identity:
        """Transitional (until increment B): the portal states the signed-in person."""
        requester = headers.get("x-platform-requester", "")
        if not requester.startswith("user:default/") or not NAME.match(requester.removeprefix("user:default/")):
            raise Unauthenticated("The portal must state the signed-in person (X-Platform-Requester: user:default/<name>).")
        teams = tuple(sorted({t.strip().split("/")[-1] for t in headers.get("x-platform-teams", "").split(",")
                              if t.strip() and NAME.match(t.strip().split("/")[-1])}))
        return Identity("person", requester.removeprefix("user:default/"), None, teams, (), "portal")
