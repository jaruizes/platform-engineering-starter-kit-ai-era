"""Client for the platform API (platform/capabilities/api).

Code Golden Paths (new repositories) are platform capabilities: the platform
API renders their skeletons and creates the repositories. The MCP server is
one of their channels, like the portal and the CLI, and works the same with
or without a portal.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

PLATFORM_API_URL = os.environ.get("PLATFORM_API_URL", "http://platform-api.platform-system.svc:8083")
GIT_URL = os.environ.get("GIT_URL", "http://localhost:3000")
GIT_OWNER = "platform"


class RequestFailed(Exception):
    """The platform did not do it; the message says why."""


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    token = os.environ.get("PLATFORM_API_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{PLATFORM_API_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        try:
            reason = json.loads(err.read()).get("error", "")
        except ValueError:
            reason = ""
        raise RequestFailed(reason or f"The platform API answered {err.code}.") from err
    except urllib.error.URLError as err:
        raise RequestFailed(f"The platform API is not reachable: {err.reason}") from err


def create_repository(golden_path: str, parameters: dict[str, Any], requester: str) -> dict[str, Any]:
    """Runs a code Golden Path through the platform API and returns what it created."""
    return _request("POST", f"/v1/golden-paths/{quote(golden_path)}/repositories",
                    {"parameters": parameters, "requester": requester})


def repository_url(name: str) -> str:
    return f"{GIT_URL}/{GIT_OWNER}/{name}"


def push_url(name: str) -> str:
    """Clone URL with the Git server account agents push with, when there is one."""
    user, password = os.environ.get("GIT_PUSH_USERNAME"), os.environ.get("GIT_PUSH_PASSWORD")
    if not (user and password):
        return f"{repository_url(name)}.git"
    scheme, rest = GIT_URL.split("://", 1)
    return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{rest}/{GIT_OWNER}/{name}.git"
