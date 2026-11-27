"""Platform MCP server: the platform's Golden Paths as tools for AI agents.

Agents never get raw infrastructure access. They call the same Golden Paths
a developer uses, through the platform API, and the same guardrails apply.
Requests outside the guardrails go to a human.

The server is an OAuth 2.1 resource server (MCP authorization): an agent
signs its person in with Keycloak and sends the access token; the server
forwards that token to the platform API, which knows which agent acts for
which person and decides. This server holds no Kubernetes access and makes
no authorization decision of its own.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from . import platform_api_client as api

NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$")

mcp = MCPServer(
    name="platform",
    title="Internal Developer Platform",
    instructions=(
        "Use this server to get environments and deploy services and frontend apps through the "
        "company's Golden Paths, and capabilities such as databases, instead of writing "
        "infrastructure code. Start with list_golden_paths. You act for the person who signed in: whoami shows "
        "their teams, and requests are only allowed for those teams. Use get_quality_status for read-only, "
        "commit-linked quality evidence and findings. Requests are checked by policy; if one needs human "
        "approval, tell the user and give them the approval id. When you build a new service, deliver it so "
        "the user can try it: unless they say otherwise, reuse a ready environment of the team or request a "
        "small one for 8 hours. Use create_service for a Spring backend and create_angular_app for an Angular frontend, "
        "then follow deployment with get_service_status. For an existing read-only REST API use create_api_mcp_adapter to publish an API-to-MCP adapter."
    ),
)


def _token(ctx: Context | None) -> str | None:
    """The agent's access token, forwarded as is to the platform API."""
    try:
        authorization = (ctx.headers or {}).get("authorization", "") if ctx else ""
    except Exception:  # noqa: BLE001 - outside a request
        authorization = ""
    return authorization[7:].strip() if authorization.lower().startswith("bearer ") else None


def _call(ctx: Context | None, method: str, path: str, body: dict[str, Any] | None = None,
          query: dict[str, Any] | None = None) -> Any:
    """A platform API operation, as a tool result an agent can act on."""
    try:
        return api.request(_token(ctx), method, path, body, query)
    except api.RequestFailed as failed:
        status = {401: "unauthenticated", 403: "denied", 404: "not_found", 409: "exists", 422: "invalid"}.get(
            failed.status, "failed")
        result: dict[str, Any] = {"status": status, "reason": str(failed)}
        if status == "denied":
            result["next_step"] = ("The platform refused it for the person you act for. Tell the user why; do not "
                                   "retry for another team.")
        return result


def _check_name(value: str, field: str) -> None:
    if not NAME_PATTERN.match(value):
        raise ValueError(f"{field} must be lowercase letters, numbers and dashes (max 30 characters).")


@mcp.tool(title="List Golden Paths")
def list_golden_paths(ctx: Context | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    """Lists the Golden Paths and capabilities this platform offers, with their parameters and guardrails.

    Capabilities (databases and the like) are all requested with request_capability.
    """
    return _call(ctx, "GET", "/v1/offering")


@mcp.tool(title="Who am I")
def whoami(ctx: Context | None = None) -> dict[str, Any]:
    """Who the platform sees: this agent, the person it acts for, and their teams.

    Requests are only allowed for those teams.
    """
    return _call(ctx, "GET", "/v1/me")


@mcp.tool(
    title="Get service quality status",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
def get_quality_status(service: str, ctx: Context | None = None) -> dict[str, Any]:
    """Reads the latest committed quality gate evidence and findings for a service.

    Args:
        service: Service repository name, for example inventory-service.
    """
    return _call(ctx, "GET", f"/v1/services/{api.quote(service, safe='')}/quality")


@mcp.tool(title="Request an environment")
def request_environment(
    team: str,
    name: str,
    purpose: str,
    size: str = "small",
    ttl_hours: int = 8,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Requests an ephemeral environment to test a change, for one of the user's teams.

    Args:
        team: Team that owns the environment and pays for it (one of the user's teams, see whoami).
        name: Short name for the environment (lowercase, numbers, dashes).
        purpose: What it is for, for example the change to test.
        size: small (default), medium or large.
        ttl_hours: Hours until it is deleted automatically (default 8).
    """
    _check_name(team, "team")
    _check_name(name, "name")
    return _call(ctx, "POST", "/v1/environments",
                 {"team": team, "name": name, "purpose": purpose, "size": size, "ttlHours": ttl_hours})


@mcp.tool(title="Get an environment")
def get_environment(name: str, ctx: Context | None = None) -> dict[str, Any]:
    """Returns the status of an environment: readiness, namespace, cost, requester and expiry."""
    _check_name(name, "name")
    return _call(ctx, "GET", f"/v1/environments/{name}")


@mcp.tool(title="List environments")
def list_environments(team: str | None = None, ctx: Context | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    """Lists the active environments of the user's teams, optionally for one team."""
    return _call(ctx, "GET", "/v1/environments", query={"team": team})


@mcp.tool(title="Deploy a service")
def deploy_service(
    environment: str,
    name: str,
    image: str | None = None,
    replicas: int = 1,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Deploys a ready-made image into an environment using the SpringService runtime Golden Path.

    Services created with create_service do not need it: every push to their
    main branch is built and deployed by the platform (GitOps).

    Args:
        environment: Environment to deploy into.
        name: Service name.
        image: Container image. Defaults to a sample web service.
        replicas: Number of replicas, 1 to 3.
    """
    _check_name(name, "name")
    _check_name(environment, "environment")
    return _call(ctx, "POST", f"/v1/environments/{environment}/services",
                 {"name": name, "image": image, "replicas": replicas})


def _repository(ctx: Context | None, golden_path: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Runs a code Golden Path: the platform renders the skeleton and creates the repository."""
    return _call(ctx, "POST", f"/v1/golden-paths/{golden_path}/repositories", {"parameters": parameters})


@mcp.tool(title="Create a service")
def create_service(
    name: str,
    description: str,
    team: str,
    module: str,
    environment: str | None = None,
    base_package: str = "com.starterkit",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Creates the repository of a new Spring Boot service with the spring-service Golden Path.

    The repository follows the engineering standards from the first commit and is
    registered in the catalog. Use it instead of scaffolding a service by hand.
    With an environment, the service is delivered there with its own PostgreSQL:
    every push to main runs the platform pipeline (tests, architecture rules,
    image) and Argo CD deploys it. Follow it with get_service_status.

    Args:
        name: Service and repository name (lowercase letters, numbers and dashes).
        description: What the service does, in the domain language.
        team: Team that owns the service, one of the user's teams.
        module: First functional module, a business capability such as records.
        environment: Ephemeral environment to deploy to (request_environment first).
            Without it, only the repository is created and nothing is deployed, so
            leave it out only when the user does not want to try the service.
        base_package: Base Java package; the service package adds the name without dashes.
    """
    if not re.match(r"^[a-z]([-a-z0-9]{0,38}[a-z0-9])?$", name):
        raise ValueError("name must be lowercase letters, numbers and dashes (max 40 characters).")
    if not re.match(r"^[a-z][a-z0-9]*$", module):
        raise ValueError("module must be lowercase letters and numbers, for example records.")
    _check_name(team, "team")
    if environment:
        _check_name(environment, "environment")
    parameters = {"name": name, "description": description, "owner": team, "basePackage": base_package,
                  "module": module}
    if environment:
        parameters["environment"] = environment
    created = _repository(ctx, "spring-service", parameters)
    if created.get("status") != "created":
        return created
    deliver = (
        f" Then commit and push to main: the platform builds and deploys it to env-{environment} "
        f"(the skeleton is already on its way). Follow it with get_service_status(name='{name}', "
        f"environment='{environment}') until it is ready."
        if environment else ""
    )
    return {
        "status": "created",
        "repository": created["repository"],
        # With the Git server account for agents, so a push needs no prompt.
        "clone": f"git clone {api.push_url(name)}",
        "catalog_entity": created["catalogEntity"],
        "environment": environment,
        "next_step": (
            "Clone the repository, read its AGENTS.md and the engineering standards that apply to it (portal MCP "
            f"server: platform.get-standards-for-entity with component:default/{name}, architecture backend-spring-v2), "
            "implement inside the generated module, and run ./mvnw verify "
            "before finishing: it checks the architecture rules." + deliver
        ),
    }


@mcp.tool(title="Get the status of a service")
def get_service_status(name: str, environment: str, resource_kind: str = "SpringService",
                       ctx: Context | None = None) -> dict[str, Any]:
    """How the delivery of a service or frontend created with a Golden Path is going.

    Puts together its pipeline (tests and image), GitOps (Argo CD) and its pods,
    with the logs when it does not start, and says what to do next. Call it after
    a push to main until state is ready (or something failed).

    Args:
        name: Service name.
        environment: Environment it is deployed to.
        resource_kind: SpringService for a backend (default), or App for an Angular frontend.
    """
    _check_name(environment, "environment")
    if resource_kind not in ("SpringService", "App"):
        raise ValueError("resource_kind must be SpringService or App.")
    return _call(ctx, "GET", f"/v1/environments/{environment}/services/{api.quote(name, safe='')}/status",
                 query={"kind": resource_kind})


@mcp.tool(title="Create an Angular frontend")
def create_angular_app(
    name: str,
    description: str,
    team: str,
    environment: str | None = None,
    backend_service: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Creates an Angular frontend repository with the angular-app Golden Path.

    The repository contains an Angular skeleton, build and test pipeline, static
    Nginx image delivery, and a namespaced Crossplane App resource. With an
    environment, Argo CD applies the App and Crossplane creates its Kubernetes
    Deployment and Service. Optionally, /api/ is routed to a SpringService in
    the same environment.

    Args:
        name: Frontend and repository name (lowercase letters, numbers and dashes).
        description: What the frontend lets its users do.
        team: Owning team, one of the user's teams.
        environment: Ephemeral environment to deploy into (request_environment first).
        backend_service: Optional SpringService name in the same environment.
    """
    if not re.match(r"^[a-z]([-a-z0-9]{0,38}[a-z0-9])?$", name):
        raise ValueError("name must be lowercase letters, numbers and dashes (max 40 characters).")
    _check_name(team, "team")
    if backend_service and not re.match(r"^[a-z]([-a-z0-9]{0,38}[a-z0-9])?$", backend_service):
        raise ValueError("backend_service must be a SpringService name (lowercase letters, numbers and dashes).")
    if environment:
        _check_name(environment, "environment")
    if backend_service and not environment:
        raise ValueError("backend_service needs the environment where it runs.")
    parameters: dict[str, Any] = {"name": name, "description": description, "owner": team}
    if environment:
        parameters["environment"] = environment
    if backend_service:
        parameters["backendService"] = backend_service
    created = _repository(ctx, "angular-app", parameters)
    if created.get("status") != "created":
        return created
    deliver = (
        f" Commit and push to main to run frontend tests and deploy App into env-{environment}. "
        f"Use get_service_status(name='{name}', environment='{environment}', resource_kind='App') to follow it."
        if environment else ""
    )
    return {
        "status": "created",
        "repository": created["repository"],
        "clone": f"git clone {api.push_url(name)}",
        "catalog_entity": created["catalogEntity"],
        "environment": environment,
        "backend_service": backend_service,
        "next_step": (
            "Read AGENTS.md and the frontend-angular-v1 architecture rules from the portal MCP server, "
            "implement the user journeys and tests, then run npm install, npm test and npm run build." + deliver
        ),
    }


@mcp.tool(title="Create an API-to-MCP adapter")
def create_api_mcp_adapter(
    name: str,
    description: str,
    team: str,
    backend_service: str,
    environment: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Creates a separate MCP adapter repository for a deployed REST backend.

    This Zero-UI Golden Path does not create another database or backend.
    It generates a Streamable HTTP server deployed in the SAME ephemeral
    namespace as the existing REST service via the Gitea/Argo CD pipeline.
    No public ingress: each consumer uses their own authorized port-forward.

    After generation: clone repo, define reviewed GET operations, push to main,
    let GitOps deploy, then register the remote MCP URL in Claude Code.
    """
    for field, value in (("name", name), ("backend_service", backend_service)):
        if not re.fullmatch(r"[a-z]([-a-z0-9]{0,38}[a-z0-9])?", value):
            raise ValueError(f"{field} must be a DNS-safe lowercase name (max 40 characters).")
    _check_name(team, "team")
    _check_name(environment, "environment")
    # The platform checks that the backend is deployed in that environment.
    created = _repository(ctx, "api-mcp-adapter", {
        "name": name,
        "description": description,
        "owner": team,
        "backendService": backend_service,
        "environment": environment,
    })
    if created.get("status") != "created":
        return created
    return {
        "status": "created",
        "repository": created["repository"],
        "clone": f"git clone {api.push_url(name)}",
        "catalog_entity": created["catalogEntity"],
        "backend_service": backend_service,
        "environment": environment,
        "next_step": (
            "Clone the adapter, edit operations.json using the approved backend OpenAPI "
            "GET operations, run tests and push to main. Gitea Actions deploys the "
            "MCP via Argo CD into env-" + environment + ". "
            "Then each user runs kubectl -n env-" + environment +
            " port-forward svc/" + name + " 18081:8080 and registers with "
            "claude mcp add --scope user --transport http " + name +
            " http://127.0.0.1:18081/mcp. See generated README."
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
    if environment:
        _check_name(environment, "environment")
    return _call(ctx, "POST", f"/v1/capabilities/{api.quote(capability, safe='')}/requests",
                 {"name": name, "environment": environment, "parameters": parameters or {}})


@mcp.tool(title="Get a capability request")
def get_capability_request(capability: str, name: str, environment: str | None = None,
                           ctx: Context | None = None) -> dict[str, Any]:
    """Returns the status of a capability request: readiness, outputs (for example the Secret name) and requester."""
    _check_name(name, "name")
    return _call(ctx, "GET", f"/v1/capabilities/{api.quote(capability, safe='')}/requests/{name}",
                 query={"environment": environment})


@mcp.tool(title="Get approval status")
def get_approval_status(approval_id: str, ctx: Context | None = None) -> dict[str, Any]:
    """Returns whether a human approved or rejected a request."""
    return _call(ctx, "GET", f"/v1/approvals/{api.quote(approval_id, safe='')}")


@mcp.tool(title="Delete an environment")
def delete_environment(name: str, ctx: Context | None = None) -> dict[str, Any]:
    """Deletes an environment that is no longer needed, to free the team's budget.

    Agents can only delete environments that an agent requested for the same person.
    """
    _check_name(name, "name")
    return _call(ctx, "DELETE", f"/v1/environments/{name}")


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


class OAuthResource:
    """OAuth 2.1 resource server in front of the MCP endpoint (MCP authorization spec).

    Without a valid Keycloak access token it answers 401 with the protected
    resource metadata, so MCP clients (Claude Code, Gemini CLI...) discover
    Keycloak, sign the person in and retry with a token. The token is checked
    with the platform API (GET /v1/me), cached for a minute, and forwarded
    unchanged with every tool call.
    """

    PUBLIC = ("/healthz", "/.well-known/oauth-protected-resource")

    def __init__(self, app: ASGIApp, resource: str, authorization_server: str, validate=None,
                 cache_seconds: float = 60) -> None:
        self.app = app
        self.resource = resource.rstrip("/")
        self.authorization_server = authorization_server
        self.validate = validate or (lambda token: api.request(token, "GET", "/v1/me", timeout=10))
        self.cache_seconds = cache_seconds
        self._valid: dict[str, float] = {}
        base = self.resource.rsplit("/mcp", 1)[0]
        self.metadata_url = f"{base}/.well-known/oauth-protected-resource"

    def metadata(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "authorization_servers": [self.authorization_server],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["openid", "profile"],
            "resource_name": "Internal Developer Platform",
        }

    def _authenticated(self, token: str) -> tuple[bool, str]:
        now = time.monotonic()
        if self._valid.get(token, 0) > now:
            return True, ""
        try:
            self.validate(token)
        except api.RequestFailed as failed:
            return False, str(failed)
        self._valid = {t: exp for t, exp in self._valid.items() if exp > now}
        self._valid[token] = now + self.cache_seconds
        return True, ""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if path.startswith("/.well-known/oauth-protected-resource"):
            await JSONResponse(self.metadata())(scope, receive, send)
            return
        if path in self.PUBLIC:
            await self.app(scope, receive, send)
            return
        sent = dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")
        token = sent[7:].strip() if sent.lower().startswith("bearer ") else ""
        valid, reason = self._authenticated(token) if token else (False, "")
        if not valid:
            challenge = f'Bearer resource_metadata="{self.metadata_url}"'
            if token:
                challenge += ', error="invalid_token"'
            body = {"error": "invalid_token" if token else "unauthorized",
                    "error_description": reason or "Sign in with the platform's identity provider."}
            await JSONResponse(body, status_code=401, headers={"WWW-Authenticate": challenge})(scope, receive, send)
            return
        await self.app(scope, receive, send)


def main() -> None:
    import uvicorn

    allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*").split(",")
    app: ASGIApp = mcp.streamable_http_app(
        transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts),
        host="0.0.0.0",
    )
    app = OAuthResource(
        app,
        resource=os.environ.get("MCP_RESOURCE_URL", "http://localhost:8081/mcp"),
        authorization_server=os.environ.get("OIDC_ISSUER", "http://localhost:8180/realms/platform"),
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8081")))
