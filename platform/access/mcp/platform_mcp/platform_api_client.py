"""Client for the platform API (platform/capabilities/api).

Every platform operation is a platform API operation: the MCP server is one
of its channels, like the portal and the CLI. It forwards the agent's own
Keycloak access token, so the platform API knows which agent acts for which
person and authorizes it; the MCP server makes no decision of its own.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import quote

PLATFORM_API_URL = os.environ.get("PLATFORM_API_URL", "http://platform-api.platform-system.svc:8083")
GIT_URL = os.environ.get("GIT_URL", "http://localhost:3000")
GIT_OWNER = "platform"


class RequestFailed(Exception):
    """The platform did not do it; the message says why."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def request(token: str | None, method: str, path: str, body: dict[str, Any] | None = None,
            query: dict[str, Any] | None = None, timeout: float = 180) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if query:
        path += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    req = urllib.request.Request(
        f"{PLATFORM_API_URL}{path}", method=method, headers=headers,
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        try:
            reason = json.loads(err.read()).get("error", "")
        except ValueError:
            reason = ""
        raise RequestFailed(reason or f"The platform API answered {err.code}.", err.code) from err
    except urllib.error.URLError as err:
        raise RequestFailed(f"The platform API is not reachable: {err.reason}", 503) from err


def create_repository(token: str | None, golden_path: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Runs a code Golden Path through the platform API and returns what it created."""
    return request(token, "POST", f"/v1/golden-paths/{quote(golden_path)}/repositories", {"parameters": parameters})


def client_credentials_token(client_id: str | None = None, secret: str | None = None) -> str:
    """Access token of an autonomous agent (client credentials), e.g. ci-agent for make demo-agent."""
    issuer = os.environ.get("OIDC_TOKEN_ISSUER") or os.environ.get("OIDC_ISSUER",
                                                                    "http://localhost:8180/realms/platform")
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id or os.environ.get("AGENT_CLIENT_ID", "ci-agent"),
        "client_secret": secret or os.environ["AGENT_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(f"{issuer}/protocol/openid-connect/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())["access_token"]


def repository_url(name: str) -> str:
    return f"{GIT_URL}/{GIT_OWNER}/{name}"


def push_url(name: str) -> str:
    """Clone URL with the Git server account agents push with, when there is one."""
    user, password = os.environ.get("GIT_PUSH_USERNAME"), os.environ.get("GIT_PUSH_PASSWORD")
    if not (user and password):
        return f"{repository_url(name)}.git"
    scheme, rest = GIT_URL.split("://", 1)
    return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{rest}/{GIT_OWNER}/{name}.git"
