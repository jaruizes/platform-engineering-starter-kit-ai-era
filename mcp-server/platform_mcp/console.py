"""Platform console: what the platform is doing, and human approvals.

Shows who requested what (human or agent, for which team), how much it
costs, the AI-era metrics, and the requests waiting for a human decision.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route

from . import platform

INDEX = (Path(__file__).parent / "static" / "index.html").read_text()


def _state() -> dict:
    environments = [platform.summarize_environment(e) for e in platform.list_environments()]
    apps = [platform.summarize_app(a) for a in platform.list_apps()]
    approvals = platform.list_approvals()
    for approval in approvals:
        approval.pop("manifest", None)
    activity = platform.list_activity()
    return {
        "environments": sorted(environments, key=lambda e: e["created_at"], reverse=True),
        "apps": apps,
        "approvals": approvals,
        "activity": activity,
        "metrics": platform.compute_metrics(environments, approvals, activity),
    }


async def index(_: Request) -> HTMLResponse:
    return HTMLResponse(INDEX)


async def state(_: Request) -> JSONResponse:
    return JSONResponse(_state())


async def decide(request: Request) -> JSONResponse:
    approval_id = request.path_params["approval_id"]
    body = await request.json()
    approver = (body.get("approver") or "").strip()
    if not approver:
        return JSONResponse({"error": "Tell us who you are to approve or reject."}, status_code=400)
    approve = body.get("decision") == "approve"
    try:
        result = platform.decide_approval(approval_id, approve, approver)
    except KeyError:
        return JSONResponse({"error": "Approval request not found."}, status_code=404)
    action = {"approved": "Approved", "rejected": "Rejected"}.get(result["status"], "ApprovalFailed")
    message = f"{approver} {result['status']} the request from {result['agent']}"
    if result.get("decision_note"):
        message += f": {result['decision_note']}"
    platform.record(action, message, result["request"]["name"], warning=action != "Approved", actor=approver)
    result.pop("manifest", None)
    return JSONResponse(result)


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
        Route("/api/approvals/{approval_id}", decide, methods=["POST"]),
        Route("/metrics", metrics),
        Route("/healthz", healthz),
    ]
)


def main() -> None:
    os.environ.setdefault("PLATFORM_COMPONENT", "platform-console")
    platform.load_kube_config()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
