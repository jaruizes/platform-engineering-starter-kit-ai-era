"""Runs the developer portal's Software Templates for agents.

Code Golden Paths (new repositories) live in the portal as templates. Agents
run the same templates people use, through the scaffolder API, with a token
that can only reach the scaffolder.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import quote
from typing import Any

PORTAL_URL = os.environ.get("PORTAL_URL", "http://portal.platform-system.svc:7007")
GIT_URL = os.environ.get("GIT_URL", "http://localhost:3000")
GIT_OWNER = "platform"


class TemplateFailed(Exception):
    """The template ran and failed; the message says why."""


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    token = os.environ.get("PORTAL_TOKEN")
    if not token:
        raise TemplateFailed("The platform MCP server has no token for the developer portal (PORTAL_TOKEN).")
    request = urllib.request.Request(
        f"{PORTAL_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        raise TemplateFailed(f"The portal refused the request ({err.code}): {err.read().decode()[:500]}") from err
    except urllib.error.URLError as err:
        raise TemplateFailed(f"The developer portal is not reachable: {err.reason}") from err


def _failure(task_id: str) -> str:
    events = _request("GET", f"/api/scaffolder/v2/tasks/{task_id}/events") or []
    messages = [e.get("body", {}).get("message", "") for e in events]
    messages = [m.splitlines()[0] for m in messages if m and not m.startswith("Run completed")]
    return messages[-1] if messages else "unknown error"


def run_template(template: str, values: dict[str, Any], timeout: float = 180) -> None:
    """Runs a template and waits until it finishes."""
    task = _request("POST", "/api/scaffolder/v2/tasks", {"templateRef": f"template:default/{template}", "values": values})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = (_request("GET", f"/api/scaffolder/v2/tasks/{task['id']}") or {}).get("status")
        if status == "completed":
            return
        if status in ("failed", "cancelled"):
            raise TemplateFailed(_failure(task["id"]))
        time.sleep(2)
    raise TemplateFailed(f"The template did not finish in {int(timeout)} seconds (task {task['id']}).")


def repository_url(name: str) -> str:
    return f"{GIT_URL}/{GIT_OWNER}/{name}"


def push_url(name: str) -> str:
    """Clone URL with the Git server account agents push with, when there is one."""
    user, password = os.environ.get("GIT_PUSH_USERNAME"), os.environ.get("GIT_PUSH_PASSWORD")
    if not (user and password):
        return f"{repository_url(name)}.git"
    scheme, rest = GIT_URL.split("://", 1)
    return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{rest}/{GIT_OWNER}/{name}.git"
