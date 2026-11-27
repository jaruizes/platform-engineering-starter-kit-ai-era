"""HTTP server of the platform API.

    GET  /v1/golden-paths                         code Golden Paths and their parameters
    POST /v1/golden-paths/{name}/repositories     {"parameters": {...}, "requester": "..."}
    POST /v1/capability-proposals                 {"definition": {...}, "requester": "...", "requesterName": "..."}

Channels (portal, platform MCP server, CLI) call it with the token
PLATFORM_API_TOKEN. Until people and agents have their own identity
(Keycloak, increment A of docs/identity-and-access.md), the channel states
the requester and the platform records it.
"""

from __future__ import annotations

import hmac
import os
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from . import golden_paths, kube, proposals
from .git_server import GitServer, GitServerError, RepositoryExists
from .service import Forbidden, Platform


def default_platform() -> Platform:
    return Platform(
        git=GitServer.from_environment(),
        state=golden_paths.State(kube.environment_exists, kube.spring_service_exists),
        record=kube.record,
        catalog=golden_paths.catalog(),
    )


def create_app(platform: Platform, token: str | None) -> Starlette:
    expected = f"Bearer {token}".encode() if token else None

    def authorized(request: Request) -> bool:
        if expected is None:
            return True
        return hmac.compare_digest(request.headers.get("authorization", "").encode(), expected)

    async def body(request: Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise golden_paths.InvalidRequest("The body must be a JSON object.")
        return data

    def handle(operation):
        async def endpoint(request: Request) -> JSONResponse:
            if not authorized(request):
                return JSONResponse({"error": "Missing or wrong bearer token."}, status_code=401)
            try:
                return JSONResponse(await operation(request), status_code=201 if request.method == "POST" else 200)
            except proposals.InvalidDefinition as invalid:
                return JSONResponse({"error": str(invalid), "errors": invalid.errors}, status_code=422)
            except golden_paths.InvalidRequest as invalid:
                return JSONResponse({"error": str(invalid)}, status_code=422)
            except Forbidden as forbidden:
                return JSONResponse({"error": str(forbidden)}, status_code=403)
            except RepositoryExists as exists:
                return JSONResponse({"error": str(exists)}, status_code=409)
            except GitServerError as failed:
                return JSONResponse({"error": str(failed)}, status_code=502)
        return endpoint

    async def list_golden_paths(_: Request) -> Any:
        return platform.list_golden_paths()

    async def create_repository(request: Request) -> Any:
        data = await body(request)
        # Rendering and pushing take a few seconds: off the event loop.
        return await run_in_threadpool(
            platform.create_repository,
            request.path_params["name"], data.get("parameters") or {}, str(data.get("requester") or ""))

    async def propose_capability(request: Request) -> Any:
        data = await body(request)
        definition = data.get("definition")
        if not isinstance(definition, dict):
            raise golden_paths.InvalidRequest("definition must be a CapabilityDefinition object.")
        return await run_in_threadpool(
            platform.propose_capability, definition, str(data.get("requester") or ""), data.get("requesterName"))

    async def healthz(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return Starlette(routes=[
        Route("/v1/golden-paths", handle(list_golden_paths), methods=["GET"]),
        Route("/v1/golden-paths/{name}/repositories", handle(create_repository), methods=["POST"]),
        Route("/v1/capability-proposals", handle(propose_capability), methods=["POST"]),
        Route("/healthz", healthz),
    ])


def main() -> None:
    import uvicorn

    kube.load_kube_config()
    app = create_app(default_platform(), os.environ.get("PLATFORM_API_TOKEN") or None)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8083")))
