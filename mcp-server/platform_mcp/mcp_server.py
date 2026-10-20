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

from . import platform, portal
from .platform import Denied

NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$")

mcp = MCPServer(
    name="platform",
    title="Internal Developer Platform",
    instructions=(
        "Use this server to get environments and deploy services through the "
        "company's Golden Paths, and capabilities such as databases, instead of writing "
        "infrastructure code. Start with list_golden_paths. Requests are checked by policy; if one needs human "
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
    """Lists the Golden Paths and capabilities this platform offers, with their parameters and guardrails.

    Capabilities (databases and the like) are all requested with request_capability.
    """
    return platform.GOLDEN_PATHS + platform.list_capabilities()


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
                    "Tell the user this request needs human approval in the developer portal "
                    "(AI Platform page) or the platform console "
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


@mcp.tool(title="Create a service")
def create_service(
    name: str,
    description: str,
    team: str,
    module: str,
    base_package: str = "com.starterkit",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Creates the repository of a new Spring Boot service with the spring-service Golden Path.

    The repository follows the engineering standards from the first commit and is
    registered in the catalog. Use it instead of scaffolding a service by hand.

    Args:
        name: Service and repository name (lowercase letters, numbers and dashes).
        description: What the service does, in the domain language.
        team: Team that owns the service, for example checkout.
        module: First functional module, a business capability such as orders.
        base_package: Base Java package; the service package adds the name without dashes.
    """
    if not re.match(r"^[a-z]([-a-z0-9]{0,38}[a-z0-9])?$", name):
        raise ValueError("name must be lowercase letters, numbers and dashes (max 40 characters).")
    if not re.match(r"^[a-z][a-z0-9]*$", module):
        raise ValueError("module must be lowercase letters and numbers, for example orders.")
    _check_name(team, "team")
    agent = agent_name(ctx)
    values = {
        "name": name,
        "description": description,
        "owner": f"group:default/{team}",
        "basePackage": base_package,
        "module": module,
        "requestedBy": f"agent:{agent}",
    }
    try:
        portal.run_template("spring-service", values)
    except portal.TemplateFailed as failed:
        platform.record("RequestFailed", f"{agent} could not create service {name}: {failed}",
                        name, warning=True, actor=agent, kind="Component")
        return {"status": "failed", "reason": str(failed)}
    repository = portal.repository_url(name)
    platform.record("RequestAccepted", f"{agent} created service {name} for team {team} from the Spring service template",
                    name, actor=agent, kind="Component")
    return {
        "status": "created",
        "repository": repository,
        "clone": f"git clone {repository}.git",
        "catalog_entity": f"component:default/{name}",
        "next_step": (
            "Clone the repository, read its AGENTS.md and the engineering standards (portal MCP server: "
            "platform.get-engineering-standard), implement inside the generated module, and run ./mvnw verify "
            "before finishing: it checks the architecture rules."
        ),
    }


@mcp.tool(title="Request a capability")
def request_capability(
    capability: str,
    name: str,
    environment: str | None = None,
    parameters: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Requests a platform capability, for example a PostgresDatabase, with its Golden Path.

    list_golden_paths shows the capabilities, their parameters, guardrails and cost.

    Args:
        capability: Capability kind or name, for example PostgresDatabase.
        name: Name for what you request (lowercase letters, numbers and dashes).
        environment: Environment it goes into, for capabilities that live in one.
        parameters: Parameters of the capability, for example {"size": "small"}. Omit to use the defaults.
    """
    _check_name(name, "name")
    cap = platform.find_capability(capability)
    if cap is None:
        names = ", ".join(c["kind"] for c in platform.list_capabilities()) or "none yet"
        return {"status": "not_found", "reason": f"There is no capability '{capability}'. Available: {names}."}
    namespace = None
    if cap["scope"] == "Namespaced":
        if not environment:
            return {"status": "denied", "reason": f"{cap['kind']} lives in an environment: tell me which one."}
        _check_name(environment, "environment")
        namespace = f"env-{environment}"
    agent = agent_name(ctx)
    manifest = platform.capability_manifest(cap, name, namespace, parameters or {}, agent)
    subject = f"{cap['kind']} {name}" + (f" in {namespace}" if namespace else "")
    try:
        platform.create_resource(manifest)
    except Denied as denied:
        if denied.needs_human_approval:
            approval_id = platform.create_approval_request(manifest, agent, denied.reason)
            platform.record("RequestNeedsApproval", f"{agent} asked for {subject}: {denied.reason}",
                            name, warning=True, actor=agent, kind=cap["kind"])
            return {
                "status": "pending_approval",
                "approval_id": approval_id,
                "reason": denied.reason,
                "next_step": (
                    "Tell the user this request needs human approval in the developer portal "
                    f"(AI Platform page) or the platform console (approval id {approval_id}). "
                    "Use get_approval_status to follow it."
                ),
            }
        platform.record("RequestDenied", f"{agent} asked for {subject}: {denied.reason}",
                        name, warning=True, actor=agent, kind=cap["kind"])
        return {"status": "denied", "reason": denied.reason}
    platform.record("RequestAccepted", f"{agent} requested {subject}", name, actor=agent, kind=cap["kind"])
    return {
        "status": "accepted",
        "capability": cap["kind"],
        "name": name,
        "namespace": namespace,
        "outputs": cap["outputs"],
        "next_step": "Use get_capability_request to check when it is ready and what it returns.",
    }


@mcp.tool(title="Get a capability request")
def get_capability_request(capability: str, name: str, environment: str | None = None) -> dict[str, Any]:
    """Returns the status of a capability request: readiness, outputs (for example the Secret name) and requester."""
    cap = platform.find_capability(capability)
    if cap is None:
        return {"status": "not_found", "reason": f"There is no capability '{capability}'."}
    namespace = f"env-{environment}" if cap["scope"] == "Namespaced" and environment else None
    obj = platform.get_resource(cap, name, namespace)
    if obj is None:
        return {"status": "not_found", "name": name}
    return platform.summarize_resource(obj)


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
