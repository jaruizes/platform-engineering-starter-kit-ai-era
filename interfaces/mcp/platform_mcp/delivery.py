"""How a service created with the Spring service Golden Path is being
delivered: its pipeline (Gitea Actions), GitOps (Argo CD) and its pods.

A push to main of the service repository builds an image and writes it into
deploy/app.yaml; Argo CD applies deploy/ to the environment. This module puts
the three steps together so an agent knows when the service is up, and why
not when it is not.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from kubernetes.client.exceptions import ApiException

from . import platform

GITEA_URL = os.environ.get("GITEA_INTERNAL_URL", "http://gitea.platform-system.svc:3000")
GIT_URL = os.environ.get("GIT_URL", "http://localhost:3000")
OWNER = "platform"
LOG_LINES = 40

# Container states that will not fix themselves.
STUCK = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError", "InvalidImageName"}


def _gitea(path: str) -> Any:
    request = urllib.request.Request(f"{GITEA_URL}/api/v1{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"null")


def pipeline(service: str) -> dict[str, Any]:
    """The latest run of the service's pipeline."""
    try:
        runs = (_gitea(f"/repos/{OWNER}/{service}/actions/tasks?limit=1") or {}).get("workflow_runs") or []
    except (urllib.error.URLError, ValueError) as err:
        return {"status": "unknown", "message": f"The Git server did not answer: {err}"}
    if not runs:
        return {"status": "none", "message": "The pipeline has not run yet."}
    run = runs[0]
    return {
        "status": run.get("status"),
        "commit": (run.get("head_sha") or "")[:12],
        "title": run.get("display_title"),
        "url": run.get("url") or f"{GIT_URL}/{OWNER}/{service}/actions/runs/{run.get('run_number')}",
    }


def gitops(service: str) -> dict[str, Any]:
    """The Argo CD application of the service repository."""
    try:
        app = platform._custom().get_namespaced_custom_object("argoproj.io", "v1alpha1", "argocd", "applications", service)
    except ApiException as err:
        if err.status == 404:
            return {"sync": "none", "message": "Argo CD has not picked up the repository yet (it checks every 20 seconds)."}
        return {"sync": "unknown", "message": f"Argo CD could not be read ({err.status})."}
    status = app.get("status") or {}
    operation = status.get("operationState") or {}
    return {
        "sync": (status.get("sync") or {}).get("status"),
        "health": (status.get("health") or {}).get("status"),
        "revision": ((status.get("sync") or {}).get("revision") or "")[:12],
        "message": operation.get("message") if operation.get("phase") in ("Failed", "Error") else None,
    }


def pods(namespace: str, service: str) -> list[dict[str, Any]]:
    core = platform._core()
    items = core.list_namespaced_pod(namespace, label_selector=f"app.kubernetes.io/name={service}").items
    result = []
    for pod in items:
        statuses = pod.status.container_statuses or []
        state = statuses[0] if statuses else None
        waiting = state.state.waiting if state and state.state else None
        terminated = state.last_state.terminated if state and state.last_state else None
        entry: dict[str, Any] = {
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "ready": bool(state and state.ready),
            "restarts": state.restart_count if state else 0,
            "waiting_reason": waiting.reason if waiting else None,
            "waiting_message": waiting.message if waiting else None,
            "last_exit": f"{terminated.reason} ({terminated.exit_code})" if terminated else None,
        }
        if not entry["ready"] and state and (state.restart_count or entry["waiting_reason"] in STUCK):
            entry["logs"] = _logs(core, namespace, pod.metadata.name, previous=bool(state.restart_count))
        result.append(entry)
    return result


def _logs(core: Any, namespace: str, pod: str, previous: bool) -> str:
    try:
        return core.read_namespaced_pod_log(pod, namespace, tail_lines=LOG_LINES, previous=previous)
    except ApiException:
        try:
            return core.read_namespaced_pod_log(pod, namespace, tail_lines=LOG_LINES)
        except ApiException as err:
            return f"(no logs: {err.reason})"


def summarize(service: str, environment: str, run: dict[str, Any], argo: dict[str, Any],
              app: dict[str, Any] | None, replicas: list[dict[str, Any]]) -> tuple[str, str]:
    """(state, what to do next) from the three steps, in the order they happen."""
    namespace = f"env-{environment}"
    if run["status"] in ("failure", "cancelled"):
        return "pipeline_failed", f"The pipeline failed: read the failed step at {run['url']}, fix it and push to main again."
    if run["status"] in ("running", "waiting", "blocked") or run["status"] == "none":
        return "building", "The pipeline is building the image. Call get_service_status again in a minute."
    if app is None:
        return "deploying", "Argo CD has not created the service yet. Call get_service_status again in a moment."
    if not app.get("image"):
        return "deploying", "The pipeline has not written the image yet. Call get_service_status again in a moment."
    if argo.get("message"):
        return "gitops_failed", f"Argo CD could not apply deploy/: {argo['message']}"
    stuck = [p for p in replicas if p.get("waiting_reason") in STUCK or p.get("restarts")]
    if stuck and not any(p["ready"] for p in replicas):
        reason = stuck[0].get("waiting_reason") or stuck[0].get("last_exit")
        return "failing", (
            f"The service does not start ({reason}). Read the logs in pods[].logs, fix the code or "
            "deploy/app.yaml, and push to main."
        )
    if not app.get("ready"):
        return "starting", "The service is starting. Call get_service_status again in a moment."
    return "ready", (
        f"Ready. Try it from the user's laptop: kubectl -n {namespace} port-forward svc/{service} 8080:80, "
        "then curl http://localhost:8080/<path>."
    )


def status(service: str, environment: str) -> dict[str, Any]:
    namespace = f"env-{environment}"
    run = pipeline(service)
    argo = gitops(service)
    try:
        resource = platform._custom().get_namespaced_custom_object(
            platform.GROUP, platform.VERSION, namespace, "apps", service)
        app = platform.summarize_app(resource)
    except ApiException as err:
        if err.status != 404:
            raise
        app = None
    try:
        replicas = pods(namespace, service) if app else []
    except ApiException as err:
        replicas = [{"error": f"The pods could not be read ({err.status})."}]
    state, next_step = summarize(service, environment, run, argo, app, replicas)
    return {
        "service": service,
        "environment": environment,
        "state": state,
        "pipeline": run,
        "gitops": argo,
        "app": app,
        "pods": replicas,
        "next_step": next_step,
    }
