"""The operations of the platform API, independent of any channel.

The HTTP server (server.py) exposes them; the portal, the platform MCP
server and the CLI call them. Each operation receives the identity of the
request (identity.py), is authorized first (authorization.py) and records
who did it, allowed or denied.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable

from . import authorization as authz
from . import golden_paths, proposals
from .authorization import Forbidden
from .git_server import GitServer, GitServerError
from .identity import PREFIX, Identity

Recorder = Callable[..., None]

PLATFORM_REPOSITORY = "platform-starter-kit"
NAME = re.compile(r"^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$")

__all__ = ["Forbidden", "NotFound", "Platform"]


class NotFound(LookupError):
    """There is no such thing (or the requester may not know it exists)."""


def _check_name(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not NAME.match(value):
        raise golden_paths.InvalidRequest(
            f"{field_name} must be lowercase letters, numbers and dashes (max 30 characters).")


@dataclass
class Platform:
    git: GitServer
    state: golden_paths.State
    record: Recorder
    catalog: dict[str, golden_paths.CodeGoldenPath]
    cluster: Any = None                 # platform_api.cluster, or a fake in tests
    delivery: Any = None                # platform_api.delivery
    quality: Any = None                 # platform_api.quality
    wait_seconds: float = 60
    sleep: Callable[[float], None] = field(default=time.sleep)

    def _record(self, identity: Identity, action: str, message: str, subject: str, kind: str = "Environment",
                warning: bool = False) -> None:
        self.record(action, message, subject, actor=identity.requester, kind=kind, warning=warning,
                    on_behalf_of=identity.person if identity.is_agent else None)

    def _deny(self, identity: Identity, denied: Forbidden, what: str, subject: str, kind: str = "Environment") -> None:
        self._record(identity, "RequestDenied", f"{identity.display} {what}: {denied}", subject, kind, warning=True)

    def _environment(self, name: str) -> dict[str, Any] | None:
        _check_name(name, "environment")
        return self.cluster.get_environment(name)

    # --- Who am I ---------------------------------------------------------------

    @staticmethod
    def whoami(identity: Identity) -> dict[str, Any]:
        return identity.describe()

    # --- Catalog ----------------------------------------------------------------

    def list_golden_paths(self) -> list[dict[str, Any]]:
        """Code Golden Paths and their parameters (for the CLI and the portal)."""
        return [path.describe() for path in self.catalog.values()]

    def list_offering(self) -> list[dict[str, Any]]:
        """Everything the platform offers: Golden Paths and capabilities (for agents)."""
        return self.cluster.GOLDEN_PATHS + self.cluster.list_capabilities()

    # --- Environments -----------------------------------------------------------

    def request_environment(self, identity: Identity, team: str, name: str, purpose: str,
                            size: str = "small", ttl_hours: int = 8) -> dict[str, Any]:
        _check_name(team, "team")
        _check_name(name, "name")
        if size not in self.cluster.SIZES:
            raise golden_paths.InvalidRequest("size must be small, medium or large.")
        try:
            ttl_hours = int(ttl_hours)
        except (TypeError, ValueError) as err:
            raise golden_paths.InvalidRequest("ttl_hours must be a number of hours.") from err
        try:
            authz.require_team(identity, team, "request environments")
        except Forbidden as denied:
            self._deny(identity, denied, f"asked for a {size} environment for team {team}", name)
            raise
        manifest = self.cluster.environment_manifest(team, name, purpose, size, ttl_hours, identity.annotations())
        return self._create(identity, manifest, team, f"a {size} environment for team {team}", name, "Environment",
                            accepted=lambda: {
                                "status": "accepted", "environment": name, "namespace": f"env-{name}",
                                "next_step": "Use get_environment to check when it is ready, then deploy_service "
                                             "to deploy into it.",
                            })

    def _create(self, identity: Identity, manifest: dict[str, Any], team: str | None, what: str, subject: str,
                kind: str, accepted: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Creates a resource; agent requests outside the guardrails become approval requests."""
        try:
            self.cluster.create_resource(manifest, as_agent=identity.is_agent)
        except self.cluster.Denied as denied:
            if denied.needs_human_approval and identity.is_agent:
                approval_id = self.cluster.create_approval_request(
                    manifest, identity.agent, denied.reason, team=team, on_behalf_of=identity.person)
                self._record(identity, "RequestNeedsApproval", f"{identity.display} asked for {what}: {denied.reason}",
                             subject, kind, warning=True)
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
            self._record(identity, "RequestDenied", f"{identity.display} asked for {what}: {denied.reason}",
                         subject, kind, warning=True)
            return {"status": "denied", "reason": denied.reason}
        verb = "got" if kind == "Environment" else "requested"
        self._record(identity, "RequestAccepted", f"{identity.display} {verb} {what}", subject, kind)
        return accepted()

    def list_environments(self, identity: Identity, team: str | None = None) -> list[dict[str, Any]]:
        envs = [self.cluster.summarize_environment(e) for e in self.cluster.list_environments()]
        return [e for e in envs if authz.can_read(identity, e["team"]) and (team is None or e["team"] == team)]

    def get_environment(self, identity: Identity, name: str) -> dict[str, Any]:
        env = self._environment(name)
        if env is None:
            raise NotFound(f"There is no environment '{name}'.")
        authz.require_read(identity, authz.team_of_environment(env), f"environment {name}")
        return self.cluster.summarize_environment(env)

    def delete_environment(self, identity: Identity, name: str) -> dict[str, Any]:
        env = self._environment(name)
        if env is None:
            raise NotFound(f"There is no environment '{name}'.")
        annotations = env.get("metadata", {}).get("annotations") or {}
        team = authz.team_of_environment(env)
        try:
            authz.require_delete(identity, team, annotations, f"environment {name}")
        except Forbidden as denied:
            self._deny(identity, denied, f"tried to delete environment {name}", name)
            raise
        deletion = {
            f"{PREFIX}/deleted-by": identity.agent if identity.is_agent else identity.person,
            f"{PREFIX}/deleter-teams": ",".join(identity.teams),
            f"{PREFIX}/deleted-on-behalf-of": identity.person or "",
        }
        try:
            self.cluster.delete_environment(name, deletion, as_agent=identity.is_agent)
        except self.cluster.Denied as denied:
            self._record(identity, "RequestDenied", f"{identity.display} tried to delete environment {name}: "
                         f"{denied.reason}", name, warning=True)
            return {"status": "denied", "name": name, "reason": denied.reason}
        self._record(identity, "EnvironmentDeleted", f"{identity.display} deleted environment {name}", name)
        return {"status": "deleted", "name": name}

    # --- Services ------------------------------------------------------------------

    def _wait_until_ready(self, environment: str) -> dict[str, Any] | None:
        deadline = time.monotonic() + self.wait_seconds
        while True:
            env = self.cluster.get_environment(environment)
            if env is None or self.cluster.summarize_environment(env)["ready"] or time.monotonic() >= deadline:
                return env
            self.sleep(2)

    def deploy_service(self, identity: Identity, environment: str, name: str, image: str | None = None,
                       replicas: int = 1) -> dict[str, Any]:
        _check_name(name, "name")
        env = self._environment(environment)
        if env is None:
            raise NotFound(f"Environment '{environment}' does not exist. Request it first.")
        namespace = f"env-{environment}"
        try:
            authz.require_team(identity, authz.team_of_environment(env), f"deploy into environment {environment}")
        except Forbidden as denied:
            self._deny(identity, denied, f"tried to deploy {name} in {namespace}", environment)
            raise
        env = self._wait_until_ready(environment)
        if env is None or not self.cluster.summarize_environment(env)["ready"]:
            return {"status": "not_ready",
                    "reason": f"Environment '{environment}' is not ready yet. Check it with get_environment."}
        manifest = self.cluster.spring_service_manifest(namespace, name, image, int(replicas), identity.annotations())
        return self._create(identity, manifest, authz.team_of_environment(env), f"{name} in {namespace}",
                            environment, "SpringService",
                            accepted=lambda: {"status": "accepted",
                                              "url": f"http://{name}.{namespace}.svc.cluster.local"})

    def service_status(self, identity: Identity, name: str, environment: str,
                       resource_kind: str = "SpringService") -> dict[str, Any]:
        if resource_kind not in ("SpringService", "App"):
            raise golden_paths.InvalidRequest("resource_kind must be SpringService or App.")
        env = self._environment(environment)
        if env is None:
            raise NotFound(f"There is no environment '{environment}'.")
        authz.require_read(identity, authz.team_of_environment(env), f"environment {environment}")
        return self.delivery.status(name, environment, resource_kind)

    def quality_status(self, identity: Identity, service: str) -> dict[str, Any]:
        owner = self.quality.owner_team(service)
        if owner is None:
            raise NotFound(f"There is no service repository '{service}'.")
        authz.require_read(identity, owner, f"service {service}")
        return self.quality.quality_status(service)

    # --- Capabilities ----------------------------------------------------------------

    def _capability(self, capability: str) -> dict[str, Any]:
        cap = self.cluster.find_capability(capability)
        if cap is None:
            names = ", ".join(c["kind"] for c in self.cluster.list_capabilities()) or "none yet"
            raise NotFound(f"There is no capability '{capability}'. Available: {names}.")
        return cap

    def _capability_team(self, cap: dict[str, Any], environment: str | None,
                         parameters: dict[str, Any]) -> tuple[str | None, str | None]:
        """(namespace, owner team) of a capability request."""
        if cap["scope"] != "Namespaced":
            return None, parameters.get("team")
        if not environment:
            raise golden_paths.InvalidRequest(f"{cap['kind']} lives in an environment: say which one.")
        env = self._environment(environment)
        if env is None:
            raise NotFound(f"Environment '{environment}' does not exist. Request it first.")
        return f"env-{environment}", authz.team_of_environment(env)

    def request_capability(self, identity: Identity, capability: str, name: str, environment: str | None = None,
                           parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        _check_name(name, "name")
        parameters = parameters or {}
        if not isinstance(parameters, dict):
            raise golden_paths.InvalidRequest("parameters must be an object.")
        cap = self._capability(capability)
        namespace, team = self._capability_team(cap, environment, parameters)
        subject = f"{cap['kind']} {name}" + (f" in {namespace}" if namespace else "")
        try:
            authz.require_team(identity, team, f"request {cap['kind']}")
        except Forbidden as denied:
            self._deny(identity, denied, f"asked for {subject}", name, cap["kind"])
            raise
        manifest = self.cluster.capability_manifest(cap, name, namespace, parameters, identity.annotations())
        return self._create(identity, manifest, team, subject, name, cap["kind"], accepted=lambda: {
            "status": "accepted", "capability": cap["kind"], "name": name, "namespace": namespace,
            "outputs": cap["outputs"],
            "next_step": "Use get_capability_request to check when it is ready and what it returns.",
        })

    def get_capability_request(self, identity: Identity, capability: str, name: str,
                               environment: str | None = None) -> dict[str, Any]:
        cap = self._capability(capability)
        namespace, team = (None, None)
        if cap["scope"] == "Namespaced":
            namespace, team = self._capability_team(cap, environment, {})
        obj = self.cluster.get_resource(cap, name, namespace)
        if obj is None:
            raise NotFound(f"There is no {cap['kind']} '{name}'.")
        if cap["scope"] != "Namespaced":
            team = (obj.get("spec") or {}).get("team")
        authz.require_read(identity, team, f"{cap['kind']} {name}")
        return self.cluster.summarize_resource(obj)

    # --- Approvals ---------------------------------------------------------------------

    def get_approval(self, identity: Identity, approval_id: str) -> dict[str, Any]:
        approval = self.cluster.get_approval(approval_id)
        if approval is None:
            raise NotFound(f"There is no approval request '{approval_id}'.")
        team = approval.get("team") or (approval["manifest"].get("spec") or {}).get("team")
        authz.require_read(identity, team, f"approval request {approval_id}")
        approval.pop("manifest", None)
        return approval

    # --- Code Golden Paths -------------------------------------------------------------

    def create_repository(self, identity: Identity, golden_path: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Runs a code Golden Path: renders its skeleton and creates the repository."""
        path = self.catalog.get(golden_path)
        if path is None:
            raise golden_paths.InvalidRequest(
                f"There is no code Golden Path '{golden_path}'. Available: {', '.join(self.catalog) or 'none'}.")
        resolved = golden_paths.resolve_parameters(path, parameters, self.state)
        name = resolved.get("name", "")
        team = resolved.get("owner", "").split("/")[-1]
        try:
            authz.require_team(identity, team or None, f"create repositories with the {path.name} Golden Path")
            for p in path.parameters:
                if p.type == "environment" and resolved.get(p.name) and self.cluster is not None:
                    env = self.cluster.get_environment(resolved[p.name])
                    authz.require_team(identity, authz.team_of_environment(env),
                                       f"deliver into environment {resolved[p.name]}")
        except Forbidden as denied:
            self._deny(identity, denied, f"tried to create {name} ({path.name})", name, "Component")
            raise
        values = golden_paths.render_values(path, resolved, identity.requester)
        repository = golden_paths.render_repository(path, resolved)
        name = repository.get("name") or name
        files = golden_paths.render_skeleton(path, values)
        trailer = f"Requested-by: {identity.requester}"
        if identity.is_agent and identity.person:
            trailer += f"\nOn-behalf-of: user:default/{identity.person}"
        try:
            url = self.git.create_repository(
                name, repository.get("description", ""), files,
                message=f"Create {name} from the {path.name} Golden Path\n\n{trailer}")
        except GitServerError as failed:
            self._record(identity, "RequestFailed", f"{identity.display} could not create {name} ({path.name}): {failed}",
                         name, "Component", warning=True)
            raise
        self._record(identity, "RequestAccepted",
                     f"{identity.display} created {name} for team {team} from the {path.title} Golden Path",
                     name, "Component")
        return {
            "status": "created",
            "goldenPath": path.name,
            "name": name,
            "repository": url,
            "cloneUrl": f"{url}.git",
            "catalogEntity": f"component:default/{name}",
            "environment": resolved.get("environment") or None,
            "requestedBy": identity.requester,
            "onBehalfOf": identity.person if identity.is_agent else None,
        }

    # --- Capability proposals ----------------------------------------------------------

    def propose_capability(self, identity: Identity, definition: dict[str, Any],
                           requester_name: str | None = None) -> dict[str, Any]:
        """Validates a capability definition and opens its pull request."""
        try:
            authz.require_propose(identity)
        except Forbidden as denied:
            self._deny(identity, denied, "tried to propose a capability",
                       str((definition.get("metadata") or {}).get("name") or "capability"), "CapabilityDefinition")
            raise
        proposals.validate(definition)
        name = definition["metadata"]["name"]
        person = requester_name or identity.person or identity.requester
        title = f"New platform capability: {definition['metadata']['title']}"
        pull = self.git.propose_file(
            PLATFORM_REPOSITORY,
            proposals.DEFINITION_PATH.format(name=name),
            proposals.file_content(definition),
            title,
            proposals.pull_request_body(definition, person),
            author=(person, "platform@starterkit.local"),
        )
        self._record(identity, "CapabilityProposed",
                     f"{person} proposed the capability {name} (pull request #{pull['number']})",
                     name, "CapabilityDefinition")
        return {
            "status": "proposed",
            "name": name,
            "pullRequestUrl": pull["url"],
            "pullRequestNumber": pull["number"],
            "entityRef": f"resource:default/{name}.pr-{pull['number']}",
        }
