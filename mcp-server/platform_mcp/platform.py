"""Access to the platform API (Crossplane composite resources) shared by the
MCP server and the console.

Every request goes through the Kubernetes API with the identity of the
process that makes it, so the same guardrails (Kyverno policies) apply to
agents and humans.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

GROUP = "platform.starterkit.dev"
VERSION = "v1alpha1"
PREFIX = "platform.starterkit.dev"
NAMESPACE = os.environ.get("PLATFORM_NAMESPACE", "platform-system")
APPROVAL_LABEL = f"{PREFIX}/approval-request"

HUMAN_APPROVAL_MARKER = "Human approval required"


def load_kube_config() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


@dataclass
class Denied(Exception):
    """A guardrail rejected the request."""

    reason: str

    @property
    def needs_human_approval(self) -> bool:
        return HUMAN_APPROVAL_MARKER in self.reason


def denial_reason(err: ApiException) -> str:
    """Extracts the policy message from an admission rejection."""
    try:
        message = json.loads(err.body).get("message", "")
    except (TypeError, ValueError):
        message = str(err.reason)
    # Kyverno messages look like: admission webhook "..." denied the request:
    # Policy <name> failed: <message>
    for marker in ("failed: ", "denied the request: "):
        if marker in message:
            message = message.split(marker)[-1]
    return message.strip()


def is_policy_denial(err: ApiException) -> bool:
    return err.status in (400, 403, 422) and "admission webhook" in (err.body or "")


def _custom() -> client.CustomObjectsApi:
    return client.CustomObjectsApi()


def _core() -> client.CoreV1Api:
    return client.CoreV1Api()


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- Golden Paths -----------------------------------------------------------

GOLDEN_PATHS = [
    {
        "name": "ephemeral-environment",
        "kind": "Environment",
        "description": (
            "An isolated environment (namespace) to test a change, with a CPU and "
            "memory budget, team access and automatic deletion after its time to live."
        ),
        "parameters": {
            "team": "Team that owns and pays for the environment",
            "name": "Short name, lowercase letters, numbers and dashes",
            "purpose": "What the environment is for, for example the change to test",
            "size": "small (default), medium or large",
            "ttl_hours": "Hours until it is deleted automatically (default 8, max 72)",
        },
        "guardrails": [
            "Environments live at most 72 hours.",
            "Each team can have at most 3 active environments.",
            "Agents can only request small environments; larger ones need human approval.",
        ],
        "tool": "request_environment",
    },
    {
        "name": "new-service",
        "kind": "App",
        "description": (
            "Deploys a service the standard way: health probes, resource limits, "
            "hardened security context, ownership labels and an internal URL."
        ),
        "parameters": {
            "environment": "Environment to deploy into",
            "name": "Service name",
            "image": "Container image (defaults to a sample web service)",
            "replicas": "1 to 3",
        },
        "guardrails": ["Agents can only deploy into ephemeral environments."],
        "tool": "deploy_service",
    },
    {
        "name": "spring-service",
        "kind": "Repository",
        "description": (
            "Creates the repository of a new Spring Boot service that follows the engineering "
            "standards: module-first hexagonal packages, Maven, JPA with Flyway, OpenAPI, "
            "Testcontainers, ArchUnit rules and an AGENTS.md. It is registered in the catalog and, "
            "with an environment, built and deployed on every push to main."
        ),
        "parameters": {
            "name": "Service and repository name, for example orders-service",
            "description": "What the service does, in the domain language",
            "team": "Team that owns the service",
            "module": "First functional module, for example orders",
            "environment": "Environment to deliver it to, with its PostgreSQL (optional)",
            "base_package": "Base Java package (default com.starterkit)",
        },
        "guardrails": [
            "The architecture rules run in ./mvnw verify for every change, human or AI-written.",
            "Read the engineering standards (portal MCP server) before designing or writing code.",
            "Delivery is GitOps: a push to main is built by the platform pipeline and deployed by Argo CD, "
            "into ephemeral environments only. Follow it with get_service_status.",
        ],
        "tool": "create_service",
    },
]

SIZES = {"small", "medium", "large"}


def environment_manifest(
    team: str, name: str, purpose: str, size: str, ttl_hours: int, agent: str | None
) -> dict[str, Any]:
    annotations = {f"{PREFIX}/purpose": purpose}
    if agent:
        annotations[f"{PREFIX}/agent"] = agent
    return {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "Environment",
        "metadata": {"name": name, "annotations": annotations},
        "spec": {"team": team, "purpose": purpose, "size": size, "ttlHours": ttl_hours},
    }


def create_environment(manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        return _custom().create_cluster_custom_object(GROUP, VERSION, "environments", manifest)
    except ApiException as err:
        if is_policy_denial(err):
            raise Denied(denial_reason(err)) from err
        if err.status == 409:
            raise Denied(f"An environment called '{manifest['metadata']['name']}' already exists.") from err
        raise


def get_environment(name: str) -> dict[str, Any] | None:
    try:
        return _custom().get_cluster_custom_object(GROUP, VERSION, "environments", name)
    except ApiException as err:
        if err.status == 404:
            return None
        raise


def list_environments() -> list[dict[str, Any]]:
    return _custom().list_cluster_custom_object(GROUP, VERSION, "environments")["items"]


def delete_environment(name: str) -> None:
    _custom().delete_cluster_custom_object(GROUP, VERSION, "environments", name)


def create_app(namespace: str, name: str, image: str | None, replicas: int, agent: str | None) -> dict[str, Any]:
    spec: dict[str, Any] = {"replicas": replicas}
    if image:
        spec["image"] = image
    manifest = {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "App",
        "metadata": {"name": name, "annotations": {f"{PREFIX}/agent": agent} if agent else {}},
        "spec": spec,
    }
    try:
        return _custom().create_namespaced_custom_object(GROUP, VERSION, namespace, "apps", manifest)
    except ApiException as err:
        if is_policy_denial(err):
            raise Denied(denial_reason(err)) from err
        if err.status == 409:
            raise Denied(f"A service called '{name}' already exists in {namespace}.") from err
        raise


def list_apps() -> list[dict[str, Any]]:
    return _custom().list_cluster_custom_object(GROUP, VERSION, "apps")["items"]


def summarize_environment(env: dict[str, Any]) -> dict[str, Any]:
    meta, spec, status = env["metadata"], env.get("spec", {}), env.get("status", {})
    annotations = meta.get("annotations") or {}
    created = datetime.fromisoformat(meta["creationTimestamp"].replace("Z", "+00:00"))
    ready = any(
        c.get("type") == "Ready" and c.get("status") == "True" for c in status.get("conditions", [])
    )
    return {
        "name": meta["name"],
        "team": spec.get("team"),
        "size": spec.get("size"),
        "purpose": spec.get("purpose"),
        "namespace": status.get("namespace"),
        "ready": ready,
        "estimated_daily_cost_eur": float(status.get("estimatedDailyCost", 0) or 0),
        "requested_by": annotations.get(f"{PREFIX}/requested-by"),
        "requester_type": annotations.get(f"{PREFIX}/requester-type"),
        "approved_by": annotations.get(f"{PREFIX}/approved-by"),
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(hours=spec.get("ttlHours", 8))).isoformat(),
    }


def summarize_app(app: dict[str, Any]) -> dict[str, Any]:
    meta, spec, status = app["metadata"], app.get("spec", {}), app.get("status", {})
    annotations = meta.get("annotations") or {}
    ready = any(
        c.get("type") == "Ready" and c.get("status") == "True" for c in status.get("conditions", [])
    )
    return {
        "name": meta["name"],
        "namespace": meta["namespace"],
        "image": spec.get("image"),
        "replicas": spec.get("replicas"),
        "ready": ready,
        "url": status.get("url"),
        "requested_by": annotations.get(f"{PREFIX}/requested-by"),
        "requester_type": annotations.get(f"{PREFIX}/requester-type"),
    }


# --- Capabilities ------------------------------------------------------------
# Capabilities built from a CapabilityDefinition (capabilities/<name>/) carry
# everything a consumer needs on their XRD: a label to find them, and
# annotations with the title, guardrails, cost and examples. That is how they
# reach agents without code of their own in this server.

XRD_GROUP, XRD_VERSION, XRD_PLURAL = "apiextensions.crossplane.io", "v2", "compositeresourcedefinitions"
CAPABILITY_LABEL = f"{PREFIX}/capability"


def _annotation_json(annotations: dict[str, str], key: str, default: Any) -> Any:
    try:
        return json.loads(annotations.get(f"{PREFIX}/{key}", ""))
    except ValueError:
        return default


def summarize_capability(xrd: dict[str, Any]) -> dict[str, Any]:
    meta, spec = xrd["metadata"], xrd["spec"]
    annotations = meta.get("annotations") or {}
    version = spec["versions"][-1]
    props = (version.get("schema", {}).get("openAPIV3Schema", {}).get("properties", {})
             .get("spec", {}).get("properties", {}))
    parameters = {
        name: {k: v for k, v in prop.items() if k in ("type", "description", "enum", "default", "minimum", "maximum")}
        for name, prop in props.items()
    }
    return {
        "name": meta["labels"][CAPABILITY_LABEL],
        "kind": spec["names"]["kind"],
        "plural": spec["names"]["plural"],
        "api_version": f"{spec['group']}/{version['name']}",
        "scope": spec.get("scope", "Namespaced"),
        "title": annotations.get(f"{PREFIX}/title", spec["names"]["kind"]),
        "description": annotations.get(f"{PREFIX}/description", ""),
        "owner": annotations.get(f"{PREFIX}/owner", ""),
        "stage": annotations.get(f"{PREFIX}/stage", "experimental"),
        "parameters": parameters,
        "outputs": _annotation_json(annotations, "outputs", {}),
        "guardrails": _annotation_json(annotations, "guardrails", []),
        "examples": _annotation_json(annotations, "examples", []),
        "estimated_daily_cost_eur": _annotation_json(annotations, "cost", {}),
        "tool": "request_capability",
    }


def list_capabilities() -> list[dict[str, Any]]:
    xrds = _custom().list_cluster_custom_object(XRD_GROUP, XRD_VERSION, XRD_PLURAL, label_selector=CAPABILITY_LABEL)
    return sorted((summarize_capability(x) for x in xrds["items"]), key=lambda c: c["name"])


def find_capability(capability: str) -> dict[str, Any] | None:
    """By capability name (postgres-database) or kind (PostgresDatabase)."""
    wanted = capability.strip().lower()
    return next((c for c in list_capabilities() if wanted in (c["name"], c["kind"].lower())), None)


def _plural(kind: str) -> str:
    """Plural of a platform kind, from its XRD (Golden Paths and capabilities alike)."""
    xrds = _custom().list_cluster_custom_object(XRD_GROUP, XRD_VERSION, XRD_PLURAL)["items"]
    for xrd in xrds:
        if xrd["spec"]["group"] == GROUP and xrd["spec"]["names"]["kind"] == kind:
            return xrd["spec"]["names"]["plural"]
    raise KeyError(kind)


def capability_manifest(
    capability: dict[str, Any], name: str, namespace: str | None, parameters: dict[str, Any], agent: str | None
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"name": name, "annotations": {f"{PREFIX}/agent": agent} if agent else {}}
    if capability["scope"] == "Namespaced":
        metadata["namespace"] = namespace
    return {"apiVersion": capability["api_version"], "kind": capability["kind"], "metadata": metadata, "spec": parameters}


def create_resource(manifest: dict[str, Any]) -> dict[str, Any]:
    """Creates any Golden Path or capability request, with this process's identity."""
    plural = _plural(manifest["kind"])
    namespace = manifest["metadata"].get("namespace")
    try:
        if namespace:
            return _custom().create_namespaced_custom_object(GROUP, VERSION, namespace, plural, manifest)
        return _custom().create_cluster_custom_object(GROUP, VERSION, plural, manifest)
    except ApiException as err:
        if is_policy_denial(err):
            raise Denied(denial_reason(err)) from err
        if err.status == 409:
            raise Denied(f"A {manifest['kind']} called '{manifest['metadata']['name']}' already exists.") from err
        if err.status == 422:
            raise Denied(f"Invalid request: {denial_reason(err)}") from err
        if err.status == 404 and namespace:
            raise Denied(f"There is no environment with namespace {namespace}.") from err
        raise


def get_resource(capability: dict[str, Any], name: str, namespace: str | None) -> dict[str, Any] | None:
    try:
        if namespace:
            return _custom().get_namespaced_custom_object(GROUP, VERSION, namespace, capability["plural"], name)
        return _custom().get_cluster_custom_object(GROUP, VERSION, capability["plural"], name)
    except ApiException as err:
        if err.status == 404:
            return None
        raise


def summarize_resource(obj: dict[str, Any]) -> dict[str, Any]:
    meta, status = obj["metadata"], obj.get("status", {})
    annotations = meta.get("annotations") or {}
    conditions = status.get("conditions", [])
    ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions)
    not_ready = next((c.get("message") for c in conditions if c.get("type") == "Ready" and c.get("status") != "True"), None)
    return {
        "kind": obj["kind"],
        "name": meta["name"],
        "namespace": meta.get("namespace"),
        "parameters": {k: v for k, v in obj.get("spec", {}).items() if k != "crossplane"},
        "ready": ready,
        "waiting_for": None if ready else not_ready,
        "status": {k: v for k, v in status.items() if k != "conditions"},
        "requested_by": annotations.get(f"{PREFIX}/requested-by"),
        "requester_type": annotations.get(f"{PREFIX}/requester-type"),
        "approved_by": annotations.get(f"{PREFIX}/approved-by"),
    }


# --- Human approvals ---------------------------------------------------------
# A request an agent cannot make on its own is stored as an approval request.
# A human approves or rejects it in the console, which then creates the
# resource with its own identity and records who approved it.


def create_approval_request(manifest: dict[str, Any], agent: str, reason: str) -> str:
    approval_id = f"{manifest['metadata']['name']}-{secrets.token_hex(2)}"
    body = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            name=f"approval-{approval_id}",
            namespace=NAMESPACE,
            labels={APPROVAL_LABEL: "true", f"{PREFIX}/approval-status": "pending"},
            annotations={f"{PREFIX}/agent": agent},
        ),
        data={"manifest": json.dumps(manifest), "reason": reason, "agent": agent},
    )
    _core().create_namespaced_config_map(NAMESPACE, body)
    return approval_id


def get_approval(approval_id: str) -> dict[str, Any] | None:
    try:
        cm = _core().read_namespaced_config_map(f"approval-{approval_id}", NAMESPACE)
    except ApiException as err:
        if err.status == 404:
            return None
        raise
    return _summarize_approval(cm)


def list_approvals() -> list[dict[str, Any]]:
    cms = _core().list_namespaced_config_map(NAMESPACE, label_selector=APPROVAL_LABEL).items
    return sorted(
        (_summarize_approval(cm) for cm in cms), key=lambda a: a["created_at"], reverse=True
    )


def _summarize_approval(cm: client.V1ConfigMap) -> dict[str, Any]:
    manifest = json.loads(cm.data["manifest"])
    return {
        "id": cm.metadata.name.removeprefix("approval-"),
        "status": cm.metadata.labels.get(f"{PREFIX}/approval-status", "pending"),
        "agent": cm.data.get("agent"),
        "reason": cm.data.get("reason"),
        "decided_by": (cm.metadata.annotations or {}).get(f"{PREFIX}/decided-by"),
        "decision_note": (cm.metadata.annotations or {}).get(f"{PREFIX}/decision-note"),
        "request": manifest["spec"] | {
            "name": manifest["metadata"]["name"],
            "kind": manifest["kind"],
            "namespace": manifest["metadata"].get("namespace"),
        },
        "manifest": manifest,
        "created_at": cm.metadata.creation_timestamp.isoformat(),
    }


def decide_approval(approval_id: str, approve: bool, approver: str) -> dict[str, Any]:
    approval = get_approval(approval_id)
    if approval is None:
        raise KeyError(approval_id)
    if approval["status"] != "pending":
        return approval
    note = ""
    status = "rejected"
    if approve:
        manifest = approval["manifest"]
        manifest["metadata"].setdefault("annotations", {})[f"{PREFIX}/approved-by"] = approver
        try:
            create_resource(manifest)
            status = "approved"
        except Denied as denied:
            # Approval does not bypass the guardrails that apply to everyone.
            status, note = "failed", denied.reason
    patch = {
        "metadata": {
            "labels": {f"{PREFIX}/approval-status": status},
            "annotations": {f"{PREFIX}/decided-by": approver, f"{PREFIX}/decision-note": note},
        }
    }
    _core().patch_namespaced_config_map(f"approval-{approval_id}", NAMESPACE, patch)
    return get_approval(approval_id) or approval


# --- Audit trail -------------------------------------------------------------
# Every action is recorded as a Kubernetes event, so it can be traced and
# measured by any tool that already reads events.


def record(
    action: str, message: str, subject: str, warning: bool = False, actor: str = "", kind: str = "Environment"
) -> None:
    timestamp = now()
    event = client.CoreV1Event(
        metadata=client.V1ObjectMeta(generate_name="platform-", namespace=NAMESPACE,
                                     annotations={f"{PREFIX}/actor": actor}),
        # Events must live in the namespace of the object they describe, so the
        # trail points to the environment by name from platform-system.
        involved_object=client.V1ObjectReference(
            api_version=f"{GROUP}/{VERSION}", kind=kind, name=subject, namespace=NAMESPACE
        ),
        reason=action,
        message=message,
        type="Warning" if warning else "Normal",
        source=client.V1EventSource(component=os.environ.get("PLATFORM_COMPONENT", "platform")),
        first_timestamp=timestamp,
        last_timestamp=timestamp,
        count=1,
    )
    try:
        _core().create_namespaced_event(NAMESPACE, event)
    except ApiException:
        # The audit trail must never break the request itself.
        pass


def list_activity(limit: int = 50) -> list[dict[str, Any]]:
    events = _core().list_namespaced_event(NAMESPACE).items
    events = [e for e in events if e.source and e.source.component in ("platform-mcp", "platform-console", "platform-portal")]
    events.sort(key=lambda e: e.last_timestamp or e.metadata.creation_timestamp, reverse=True)
    return [
        {
            "time": (e.last_timestamp or e.metadata.creation_timestamp).isoformat(),
            "component": e.source.component,
            "action": e.reason,
            "subject": e.involved_object.name,
            "message": e.message,
            "actor": (e.metadata.annotations or {}).get(f"{PREFIX}/actor", ""),
            "warning": e.type == "Warning",
        }
        for e in events[:limit]
    ]


# --- Metrics -----------------------------------------------------------------


def compute_metrics(
    environments: list[dict[str, Any]], approvals: list[dict[str, Any]], activity: list[dict[str, Any]]
) -> dict[str, Any]:
    """AI-era metrics from the deck: governance, cost and value of agent work."""
    agent_requests = [a for a in activity if a["component"] == "platform-mcp" and a["action"].startswith("Request")]
    first_time = [a for a in agent_requests if a["action"] == "RequestAccepted"]
    denied = [a for a in agent_requests if a["action"] in ("RequestDenied", "RequestNeedsApproval")]
    by_agent = [e for e in environments if e["requester_type"] == "agent"]
    cost_by_team: dict[str, float] = {}
    for env in environments:
        cost_by_team[env["team"]] = cost_by_team.get(env["team"], 0) + env["estimated_daily_cost_eur"]
    return {
        "active_environments": len(environments),
        "agent_share": round(100 * len(by_agent) / len(environments)) if environments else 0,
        "agent_requests": len(agent_requests),
        "agent_first_time_pass_rate": round(100 * len(first_time) / len(agent_requests)) if agent_requests else None,
        "denied_by_policy": len(denied),
        "pending_approvals": sum(1 for a in approvals if a["status"] == "pending"),
        "approved": sum(1 for a in approvals if a["status"] == "approved"),
        "rejected": sum(1 for a in approvals if a["status"] == "rejected"),
        "daily_cost_eur": round(sum(cost_by_team.values()), 2),
        "agent_daily_cost_eur": round(sum(e["estimated_daily_cost_eur"] for e in by_agent), 2),
        "cost_by_team": dict(sorted(cost_by_team.items())),
    }
