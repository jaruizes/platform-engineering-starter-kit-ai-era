"""Platform console: what the platform is doing, read-only.

Shows who requested what (human or agent, for which team), how much it
costs, the AI-era metrics, and the requests waiting for a human decision.
It decides nothing: approvers decide through the platform API (the portal's
AI Platform page or platformctl), signed in, where the approval rules live.
It is the backup screen for operators and has no write access to the cluster.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route

from . import cluster as platform

INDEX = (Path(__file__).parent / "static" / "index.html").read_text()


def _state() -> dict:
    environments = [platform.summarize_environment(e) for e in platform.list_environments()]
    services = [platform.summarize_spring_service(service) for service in platform.list_spring_services()]
    approvals = platform.list_approvals()
    for approval in approvals:
        approval.pop("manifest", None)
    activity = platform.list_activity()
    return {
        "environments": sorted(environments, key=lambda e: e["created_at"], reverse=True),
        "services": services,
        "approvals": approvals,
        "activity": activity,
        "metrics": platform.compute_metrics(environments, approvals, activity),
    }


async def index(_: Request) -> HTMLResponse:
    return HTMLResponse(INDEX)


async def state(_: Request) -> JSONResponse:
    return JSONResponse(_state())


async def metrics(_: Request) -> PlainTextResponse:
    """Prometheus format, so any dashboard can read the same numbers."""
    m = _state()["metrics"]
    lines = [
        f"platform_active_environments {m['active_environments']}",
        f"platform_agent_requests_total {m['agent_requests']}",
        f"platform_agent_requests_denied_total {m['denied_by_policy']}",
        f"platform_pending_approvals {m['pending_approvals']}",
        f"platform_daily_cost_eur {m['daily_cost_eur']}",
    ]
    lines += [f'platform_team_daily_cost_eur{{team="{t}"}} {c}' for t, c in m["cost_by_team"].items()]
    return PlainTextResponse("\n".join(lines) + "\n")


async def healthz(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/state", state),
        Route("/metrics", metrics),
        Route("/healthz", healthz),
    ]
)


def main() -> None:
    os.environ.setdefault("PLATFORM_COMPONENT", "platform-console")
    platform.load_kube_config()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
