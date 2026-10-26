"""Helpers for capability acceptance tests.

The tests talk to a real platform (`make up`) through the two doors a
capability has: the platform API with kubectl, as a person, and the platform
MCP server, as an AI agent. Both go through the same guardrails.

    PLATFORM_MCP_URL   platform MCP server (default http://localhost:8081/mcp)
    PLATFORM_MCP_TOKEN its bearer token, if it has one
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

import yaml

GROUP = "platform.starterkit.dev"
VERSION = "v1alpha1"
HUMAN_USER = "capability-tests@example.com"
AGENT_USER = "system:serviceaccount:platform-system:platform-mcp"
MCP_URL = os.environ.get("PLATFORM_MCP_URL", "http://localhost:8081/mcp")


class Timeout(AssertionError):
    pass


def kubectl(*args: str, input: str | None = None, check: bool = True, as_user: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["kubectl", *args]
    if as_user:
        # A person with full access: the guardrails, not RBAC, are under test.
        cmd += [f"--as={as_user}", "--as-group=system:masters"]
    result = subprocess.run(cmd, input=input, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"{' '.join(cmd)} failed: {result.stderr.strip()}")
    return result


def get(kind: str, name: str, namespace: str | None = None) -> dict[str, Any] | None:
    args = ["get", kind, name, "-o", "json"]
    if namespace:
        args += ["-n", namespace]
    result = kubectl(*args, check=False)
    return json.loads(result.stdout) if result.returncode == 0 else None


def wait_for(what: str, condition, timeout: float = 180, interval: float = 3):
    deadline = time.monotonic() + timeout
    while True:
        value = condition()
        if value:
            return value
        if time.monotonic() > deadline:
            raise Timeout(f"Timed out after {timeout:.0f}s waiting for {what}.")
        time.sleep(interval)


def unique(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(2)}"


@dataclass
class Outcome:
    """What the requester got back: created, denied or pending_approval."""

    status: str
    reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class Human:
    """A person using the platform API (kubectl)."""

    kind = "human"

    def request(self, capability_kind: str, plural: str, namespace: str, name: str, spec: dict[str, Any]) -> Outcome:
        manifest = {
            "apiVersion": f"{GROUP}/{VERSION}",
            "kind": capability_kind,
            "metadata": {"name": name, "namespace": namespace},
            "spec": spec,
        }
        result = kubectl("create", "-f", "-", input=yaml.safe_dump(manifest), check=False, as_user=HUMAN_USER)
        if result.returncode == 0:
            return Outcome("created")
        return Outcome("denied", result.stderr.strip())


class Agent:
    """An AI agent using the platform MCP server."""

    kind = "agent"

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self._call(tool, arguments))

    async def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        import httpx2
        from mcp import ClientSession, types
        from mcp.client.streamable_http import streamable_http_client

        token = os.environ.get("PLATFORM_MCP_TOKEN")
        client = httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"} if token else None,
            timeout=httpx2.Timeout(30, read=300),
        )
        async with client, streamable_http_client(MCP_URL, http_client=client) as streams:
            async with ClientSession(
                streams[0], streams[1], client_info=types.Implementation(name="capability-tests", version="1")
            ) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
                if getattr(result, "is_error", getattr(result, "isError", False)):
                    raise AssertionError(f"{tool} failed: {result.content[0].text}")
                return json.loads(result.content[0].text)

    def request(self, capability_kind: str, plural: str, namespace: str, name: str, spec: dict[str, Any]) -> Outcome:
        environment = namespace.removeprefix("env-")
        answer = self.call("request_capability", {
            "capability": capability_kind, "name": name, "environment": environment, "parameters": spec,
        })
        status = {"accepted": "created"}.get(answer["status"], answer["status"])
        if status == "pending_approval":
            # Leave no approval request behind for a person to decide.
            kubectl("delete", "configmap", f"approval-{answer['approval_id']}", "-n", "platform-system", check=False)
        return Outcome(status, answer.get("reason", ""), answer)


def environment(team: str = "capability-tests") -> tuple[str, str]:
    """Creates an ephemeral environment and returns (name, namespace) once it is ready."""
    name = unique("captest")
    manifest = {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "Environment",
        "metadata": {"name": name},
        "spec": {"team": team, "purpose": "capability acceptance tests", "size": "medium", "ttlHours": 2},
    }
    kubectl("create", "-f", "-", input=yaml.safe_dump(manifest), as_user=HUMAN_USER)

    def ready():
        env = get("environments.platform.starterkit.dev", name)
        conditions = (env or {}).get("status", {}).get("conditions", [])
        return any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)

    wait_for(f"environment {name}", ready, timeout=120)
    return name, f"env-{name}"


def delete_environment(name: str) -> None:
    kubectl("delete", "environments.platform.starterkit.dev", name, "--wait=false", check=False)


def run_pod(namespace: str, image: str, command: list[str], env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    """Runs a one-off pod and returns its output; the return code says if the command worked."""
    name = unique("probe")
    overrides = {
        "spec": {
            "containers": [{
                "name": name, "image": image, "command": command,
                "env": [{"name": k, "value": v} for k, v in (env or {}).items()],
                "resources": {"requests": {"cpu": "50m", "memory": "64Mi"}, "limits": {"cpu": "200m", "memory": "128Mi"}},
            }],
        },
    }
    return subprocess.run(
        ["kubectl", "run", name, "-n", namespace, "--image", image, "--restart=Never", "--rm", "-i", "--quiet",
         f"--pod-running-timeout={timeout}s", "--overrides", json.dumps(overrides)],
        capture_output=True, text=True, timeout=timeout + 60,
    )
