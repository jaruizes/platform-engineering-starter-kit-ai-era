"""HTTP server of the platform API.

    GET    /v1/me                                       who the token says you are
    GET    /v1/offering                                 Golden Paths and capabilities (for agents)
    GET    /v1/golden-paths                             code Golden Paths and their parameters
    POST   /v1/golden-paths/{name}/repositories         {"parameters": {...}}
    POST   /v1/capability-proposals                     {"definition": {...}, "requesterName": "..."}
    GET    /v1/environments[?team=]                     only those of your teams
    POST   /v1/environments                             {"team", "name", "purpose", "size", "ttlHours"}
    GET    /v1/environments/{name}
    DELETE /v1/environments/{name}
    POST   /v1/environments/{name}/services             {"name", "image", "replicas"}
    GET    /v1/environments/{env}/services/{name}/status[?kind=App]
    GET    /v1/services/{name}/quality
    POST   /v1/capabilities/{capability}/requests       {"name", "environment", "parameters"}
    GET    /v1/capabilities/{capability}/requests/{name}[?environment=]
    GET    /v1/approvals/{id}

Every request carries a Keycloak access token (Authorization: Bearer). The
platform API validates it, builds the identity (identity.py) and authorizes
the operation (authorization.py). Until increment B, the portal may instead
use the channel token PLATFORM_API_TOKEN and state the signed-in person.
"""

from __future__ import annotations

import os
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from . import golden_paths, kube, proposals
from .git_server import GitServer, GitServerError, RepositoryExists
from .identity import Authenticator, TokenVerifier, Unauthenticated
from .service import Forbidden, NotFound, Platform


def default_platform() -> Platform:
    from . import cluster, delivery, quality

    return Platform(
        git=GitServer.from_environment(),
        state=golden_paths.State(kube.environment_exists, kube.spring_service_exists),
        record=cluster.record,
        catalog=golden_paths.catalog(),
        cluster=cluster,
        delivery=delivery,
        quality=quality,
    )


def default_authenticator() -> Authenticator:
    return Authenticator(TokenVerifier.from_environment(), os.environ.get("PLATFORM_API_TOKEN") or None)


def create_app(platform: Platform, authenticator: Authenticator) -> Starlette:
    async def body(request: Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise golden_paths.InvalidRequest("The body must be a JSON object.")
        return data

    def handle(operation, status: int = 200):
        async def endpoint(request: Request) -> JSONResponse:
            try:
                identity = authenticator.identify(request.headers)
            except Unauthenticated as missing:
                return JSONResponse({"error": str(missing)}, status_code=401,
                                    headers={"WWW-Authenticate": 'Bearer realm="platform"'})
            try:
                return JSONResponse(await operation(request, identity), status_code=status)
            except proposals.InvalidDefinition as invalid:
                return JSONResponse({"error": str(invalid), "errors": invalid.errors}, status_code=422)
            except (golden_paths.InvalidRequest, ValueError) as invalid:
                return JSONResponse({"error": str(invalid)}, status_code=422)
            except Forbidden as forbidden:
                return JSONResponse({"error": str(forbidden)}, status_code=403)
            except NotFound as missing:
                return JSONResponse({"error": str(missing)}, status_code=404)
            except RepositoryExists as exists:
                return JSONResponse({"error": str(exists)}, status_code=409)
            except GitServerError as failed:
                return JSONResponse({"error": str(failed)}, status_code=502)
        return endpoint

    def call(method, *args, **kwargs):
        # Kubernetes, Git and rendering calls block: off the event loop.
        return run_in_threadpool(method, *args, **kwargs)

    async def me(_: Request, who) -> Any:
        return platform.whoami(who)

    async def offering(_: Request, __) -> Any:
        return await call(platform.list_offering)

    async def list_golden_paths(_: Request, __) -> Any:
        return platform.list_golden_paths()

    async def create_repository(request: Request, who) -> Any:
        data = await body(request)
        return await call(platform.create_repository, who, request.path_params["name"], data.get("parameters") or {})

    async def propose_capability(request: Request, who) -> Any:
        data = await body(request)
        definition = data.get("definition")
        if not isinstance(definition, dict):
            raise golden_paths.InvalidRequest("definition must be a CapabilityDefinition object.")
        return await call(platform.propose_capability, who, definition, data.get("requesterName"))

    async def list_environments(request: Request, who) -> Any:
        return await call(platform.list_environments, who, request.query_params.get("team") or None)

    async def request_environment(request: Request, who) -> Any:
        data = await body(request)
        return await call(platform.request_environment, who, str(data.get("team") or ""), str(data.get("name") or ""),
                          str(data.get("purpose") or ""), str(data.get("size") or "small"), data.get("ttlHours", 8))

    async def get_environment(request: Request, who) -> Any:
        return await call(platform.get_environment, who, request.path_params["name"])

    async def delete_environment(request: Request, who) -> Any:
        return await call(platform.delete_environment, who, request.path_params["name"])

    async def deploy_service(request: Request, who) -> Any:
        data = await body(request)
        return await call(platform.deploy_service, who, request.path_params["name"], str(data.get("name") or ""),
                          data.get("image") or None, data.get("replicas", 1))

    async def service_status(request: Request, who) -> Any:
        return await call(platform.service_status, who, request.path_params["name"],
                          request.path_params["environment"], request.query_params.get("kind") or "SpringService")

    async def quality_status(request: Request, who) -> Any:
        return await call(platform.quality_status, who, request.path_params["name"])

    async def request_capability(request: Request, who) -> Any:
        data = await body(request)
        return await call(platform.request_capability, who, request.path_params["capability"],
                          str(data.get("name") or ""), data.get("environment") or None, data.get("parameters"))

    async def get_capability_request(request: Request, who) -> Any:
        return await call(platform.get_capability_request, who, request.path_params["capability"],
                          request.path_params["name"], request.query_params.get("environment") or None)

    async def get_approval(request: Request, who) -> Any:
        return await call(platform.get_approval, who, request.path_params["id"])

    async def healthz(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return Starlette(routes=[
        Route("/v1/me", handle(me), methods=["GET"]),
        Route("/v1/offering", handle(offering), methods=["GET"]),
        Route("/v1/golden-paths", handle(list_golden_paths), methods=["GET"]),
        Route("/v1/golden-paths/{name}/repositories", handle(create_repository, 201), methods=["POST"]),
        Route("/v1/capability-proposals", handle(propose_capability, 201), methods=["POST"]),
        Route("/v1/environments", handle(list_environments), methods=["GET"]),
        Route("/v1/environments", handle(request_environment, 201), methods=["POST"]),
        Route("/v1/environments/{name}", handle(get_environment), methods=["GET"]),
        Route("/v1/environments/{name}", handle(delete_environment), methods=["DELETE"]),
        Route("/v1/environments/{name}/services", handle(deploy_service, 201), methods=["POST"]),
        Route("/v1/environments/{environment}/services/{name}/status", handle(service_status), methods=["GET"]),
        Route("/v1/services/{name}/quality", handle(quality_status), methods=["GET"]),
        Route("/v1/capabilities/{capability}/requests", handle(request_capability, 201), methods=["POST"]),
        Route("/v1/capabilities/{capability}/requests/{name}", handle(get_capability_request), methods=["GET"]),
        Route("/v1/approvals/{id}", handle(get_approval), methods=["GET"]),
        Route("/healthz", healthz),
    ])


def main() -> None:
    import uvicorn

    kube.load_kube_config()
    os.environ.setdefault("PLATFORM_COMPONENT", "platform-api")
    uvicorn.run(create_app(default_platform(), default_authenticator()),
                host="0.0.0.0", port=int(os.environ.get("PORT", "8083")))
