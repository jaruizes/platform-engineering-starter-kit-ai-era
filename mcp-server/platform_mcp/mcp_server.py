"""Platform MCP server: the platform's Golden Paths as tools for AI agents.

Agents never get raw infrastructure access. They call the same Golden Paths
a developer uses, with the platform's identity for agents, and the same
guardrails apply. Requests outside the guardrails go to a human.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from . import platform
from .platform import Denied

NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$")

mcp = MCPServer(
    name="platform",
    title="Internal Developer Platform",
    instructions=(
        "Use this server to get environments and deploy services through the "
        "company's Golden Paths instead of writing infrastructure code. Start with "
        "list_golden_paths. Requests are checked by policy; if one needs human "
        "approval, tell the user and give them the approval id."
    ),
)


def agent_name(ctx: Context | None) -> str:
    """Name the MCP client reports for itself, for example 'claude-code'."""
    try:
        params = ctx.session.client_params if ctx else None
        if params and params.client_info:
            return params.client_info.name
    except Exception:  # noqa: BLE001 - older or stateless clients
        pass
    return "unknown-agent"


def _check_name(value: str, field: str) -> None:
    if not NAME_PATTERN.match(value):
        raise ValueError(f"{field} must be lowercase letters, numbers and dashes (max 30 characters).")


@mcp.tool(title="List Golden Paths")
def list_golden_paths() -> list[dict[str, Any]]:
    """Lists the Golden Paths this platform offers, with their parameters and guardrails."""
    return platform.GOLDEN_PATHS


@mcp.tool(title="Request an environment")
def request_environment(
    team: str,
    name: str,
    purpose: str,
    size: str = "small",
    ttl_hours: int = 8,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Requests an ephemeral environment to test a change.

    Args:
        team: Team that owns the environment and pays for it.
        name: Short name for the environment (lowercase, numbers, dashes).
        purpose: What it is for, for example the change to test.
        size: small (default), medium or large.
        ttl_hours: Hours until it is deleted automatically (default 8).
    """
    _check_name(team, "team")
    _check_name(name, "name")
    if size not in platform.SIZES:
        raise ValueError("size must be small, medium or large.")
    agent = agent_name(ctx)
    manifest = platform.environment_manifest(team, name, purpose, size, ttl_hours, agent)
    try:
        platform.create_environment(manifest)
    except Denied as denied:
        if denied.needs_human_approval:
            approval_id = platform.create_approval_request(manifest, agent, denied.reason)
            platform.record("RequestNeedsApproval", f"{agent} asked for a {size} environment for team {team}: {denied.reason}",
                            name, warning=True, actor=agent)
            return {
                "status": "pending_approval",
                "approval_id": approval_id,
                "reason": denied.reason,
                "next_step": (
                    "Tell the user this request needs human approval in the platform console "
                    f"(approval id {approval_id}). Use get_approval_status to follow it, or ask for "
                    "a small environment instead."
                ),
            }
        platform.record("RequestDenied", f"{agent} asked for a {size} environment for team {team}: {denied.reason}",
                        name, warning=True, actor=agent)
        return {"status": "denied", "reason": denied.reason}
    platform.record("RequestAccepted", f"{agent} got a {size} environment for team {team}: {purpose}", name, actor=agent)
    return {
        "status": "accepted",
        "environment": name,
        "namespace": f"env-{name}",
        "next_step": "Use get_environment to check when it is ready, then deploy_service to deploy into it.",
    }


@mcp.tool(title="Get an environment")
def get_environment(name: str) -> dict[str, Any]:
    """Returns the status of an environment: readiness, namespace, cost, requester and expiry."""
    env = platform.get_environment(name)
    if env is None:
        return {"status": "not_found", "name": name}
    return platform.summarize_environment(env)


@mcp.tool(title="List environments")
def list_environments(team: str | None = None) -> list[dict[str, Any]]:
    """Lists active environments, optionally for one team."""
    envs = [platform.summarize_environment(e) for e in platform.list_environments()]
    return [e for e in envs if team is None or e["team"] == team]


def _wait_until_ready(environment: str, timeout: float = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        env = platform.get_environment(environment)
        if env is None:
            return False
        if platform.summarize_environment(env)["ready"]:
            return True
        time.sleep(2)
    return False


@mcp.tool(title="Deploy a service")
def deploy_service(
    environment: str,
    name: str,
    image: str | None = None,
    replicas: int = 1,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Deploys a service into an environment using the new-service Golden Path.

    Args:
        environment: Environment to deploy into.
        name: Service name.
        image: Container image. Defaults to a sample web service.
        replicas: Number of replicas, 1 to 3.
    """
    _check_name(name, "name")
    agent = agent_name(ctx)
    namespace = f"env-{environment}"
    if not _wait_until_ready(environment):
        return {
            "status": "not_ready",
            "reason": f"Environment '{environment}' does not exist or is not ready yet. Check it with get_environment.",
        }
    try:
        platform.create_app(namespace, name, image, replicas, agent)
    except Denied as denied:
        platform.record("RequestDenied", f"{agent} tried to deploy {name} in {namespace}: {denied.reason}",
                        environment, warning=True, actor=agent)
        return {"status": "denied", "reason": denied.reason}
    platform.record("RequestAccepted", f"{agent} deployed {name} in {namespace}", environment, actor=agent)
    return {"status": "accepted", "url": f"http://{name}.{namespace}.svc.cluster.local"}


@mcp.tool(title="Get approval status")
def get_approval_status(approval_id: str) -> dict[str, Any]:
    """Returns whether a human approved or rejected a request."""
    approval = platform.get_approval(approval_id)
    if approval is None:
        return {"status": "not_found", "approval_id": approval_id}
    approval.pop("manifest", None)
    return approval


@mcp.tool(title="Delete an environment")
def delete_environment(name: str, ctx: Context | None = None) -> dict[str, Any]:
    """Deletes an environment that is no longer needed, to free the team's budget."""
    agent = agent_name(ctx)
    if platform.get_environment(name) is None:
        return {"status": "not_found", "name": name}
    platform.delete_environment(name)
    platform.record("EnvironmentDeleted", f"{agent} deleted environment {name}", name, actor=agent)
    return {"status": "deleted", "name": name}


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def main() -> None:
    os.environ.setdefault("PLATFORM_COMPONENT", "platform-mcp")
    platform.load_kube_config()
    allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*").split(",")
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8081")),
        transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts),
    )
