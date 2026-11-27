from pathlib import Path

import pytest
import yaml

from platform_api import golden_paths
from platform_api.golden_paths import RenderedFile

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def catalog():
    return golden_paths.catalog()


@pytest.fixture
def postgres_definition():
    return yaml.safe_load((ROOT / "platform/capabilities/infrastructure/postgres-database/capability.yaml").read_text())


class FakeGit:
    """Records what the platform asks the Git server to do."""

    def __init__(self):
        self.repositories: dict[str, tuple[str, list[RenderedFile], str]] = {}
        self.proposals: list[dict] = []

    def repository_url(self, name):
        return f"http://localhost:3000/platform/{name}"

    def create_repository(self, name, description, files, message, author=None):
        from platform_api.git_server import RepositoryExists

        if name in self.repositories:
            raise RepositoryExists(f"The repository platform/{name} already exists.")
        self.repositories[name] = (description, files, message)
        return self.repository_url(name)

    def propose_file(self, repository, path, content, title, body, author):
        self.proposals.append(dict(repository=repository, path=path, content=content, title=title,
                                   body=body, author=author))
        number = len(self.proposals)
        return {"number": number, "url": f"http://localhost:3000/platform/{repository}/pulls/{number}", "title": title}


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, action, message, subject, actor="", kind="Environment", warning=False, on_behalf_of=None):
        self.events.append(dict(action=action, message=message, subject=subject, actor=actor, kind=kind,
                                warning=warning, on_behalf_of=on_behalf_of))


def environment(name, team, requested_by="marta", requester_type="human", on_behalf_of=None, ready=True,
                size="small"):
    annotations = {"platform.starterkit.dev/requested-by": requested_by,
                   "platform.starterkit.dev/requester-type": requester_type}
    if on_behalf_of:
        annotations["platform.starterkit.dev/on-behalf-of"] = on_behalf_of
    return {
        "apiVersion": "platform.starterkit.dev/v1alpha1", "kind": "Environment",
        "metadata": {"name": name, "creationTimestamp": "2026-11-27T10:00:00Z", "annotations": annotations},
        "spec": {"team": team, "purpose": "test", "size": size, "ttlHours": 8},
        "status": {"namespace": f"env-{name}", "conditions": [{"type": "Ready", "status": "True" if ready else "False"}]},
    }


POSTGRES = {"name": "postgres-database", "kind": "PostgresDatabase", "plural": "postgresdatabases",
            "api_version": "platform.starterkit.dev/v1alpha1", "scope": "Namespaced", "outputs": {"secret": "x"}}


class FakeCluster:
    """The Kubernetes side, with the agent guardrails Kyverno would apply."""

    from platform_api.cluster import (GOLDEN_PATHS, SIZES, Denied, capability_manifest, compute_metrics,
                                      environment_manifest, spring_service_manifest, summarize_environment,
                                      summarize_resource, summarize_spring_service)
    GOLDEN_PATHS, SIZES, Denied = GOLDEN_PATHS, SIZES, Denied
    compute_metrics = staticmethod(compute_metrics)
    summarize_spring_service = staticmethod(summarize_spring_service)
    environment_manifest = staticmethod(environment_manifest)
    spring_service_manifest = staticmethod(spring_service_manifest)
    capability_manifest = staticmethod(capability_manifest)
    summarize_environment = staticmethod(summarize_environment)
    summarize_resource = staticmethod(summarize_resource)

    def __init__(self):
        self.environments = {
            "checkout-dev": environment("checkout-dev", "checkout"),
            "agent-env": environment("agent-env", "checkout", "claude-code", "agent", on_behalf_of="marta"),
            "payments-dev": environment("payments-dev", "payments", "luis"),
        }
        self.created, self.deleted, self.approvals = [], [], {}
        self.services = [
            {"metadata": {"name": "orders-service", "namespace": "env-checkout-dev", "annotations": {}}, "spec": {}},
            {"metadata": {"name": "billing", "namespace": "env-payments-dev", "annotations": {}}, "spec": {}},
        ]
        self.activity = [
            {"time": "2026-11-27T10:00:00+00:00", "component": "platform-api", "action": "RequestAccepted",
             "subject": "checkout-dev", "message": "marta got an environment", "actor": "marta",
             "requester_type": "human", "on_behalf_of": "", "warning": False},
            {"time": "2026-11-27T10:01:00+00:00", "component": "platform-api", "action": "RequestAccepted",
             "subject": "payments-dev", "message": "luis got an environment", "actor": "luis",
             "requester_type": "human", "on_behalf_of": "", "warning": False},
        ]

    def list_spring_services(self):
        return self.services

    def list_activity(self):
        return self.activity

    def list_approvals(self):
        return [dict(a) for a in self.approvals.values()]

    def decide_approval(self, approval_id, approve, approver, note=""):
        approval = self.approvals[approval_id]
        status = "rejected"
        if approve:
            manifest = approval["manifest"]
            manifest["metadata"].setdefault("annotations", {})["platform.starterkit.dev/approved-by"] = approver
            try:
                self.create_resource(manifest)
                status = "approved"
            except self.Denied as denied:
                status, note = "failed", denied.reason
        approval.update(status=status, decided_by=approver, decision_note=note)
        return dict(approval)

    def get_environment(self, name):
        return self.environments.get(name)

    def list_environments(self):
        return list(self.environments.values())

    def create_resource(self, manifest, as_agent=False):
        if as_agent and manifest["kind"] == "Environment" and manifest["spec"]["size"] != "small":
            raise self.Denied("Human approval required: agents can only request small environments on their own.")
        self.created.append((manifest, as_agent))
        return manifest

    def create_approval_request(self, manifest, agent, reason, team=None, on_behalf_of=None):
        approval_id = f"{manifest['metadata']['name']}-0001"
        self.approvals[approval_id] = {
            "id": approval_id, "status": "pending", "agent": agent, "team": team, "on_behalf_of": on_behalf_of,
            "reason": reason, "manifest": manifest, "created_at": "2026-11-27T10:00:00+00:00",
            "request": manifest["spec"] | {"name": manifest["metadata"]["name"], "kind": manifest["kind"]}}
        return approval_id

    def get_approval(self, approval_id):
        approval = self.approvals.get(approval_id)
        return dict(approval) if approval else None

    def delete_environment(self, name, deletion, as_agent):
        self.deleted.append((name, deletion, as_agent))
        del self.environments[name]

    def list_capabilities(self):
        return [POSTGRES]

    def find_capability(self, capability):
        return POSTGRES if capability.lower() in ("postgresdatabase", "postgres-database") else None

    def get_resource(self, cap, name, namespace):
        return None


class FakeQuality:
    owners = {"orders-service": "checkout", "billing": "payments"}

    def owner_team(self, service):
        return self.owners.get(service)

    def quality_status(self, service):
        return {"service": service, "status": "passed"}


class FakeDelivery:
    def status(self, name, environment, kind):
        return {"service": name, "environment": environment, "state": "ready"}


@pytest.fixture
def platform(catalog):
    from platform_api.service import Platform

    services = {("orders-service", "checkout-dev")}
    cluster = FakeCluster()
    return Platform(
        git=FakeGit(),
        state=golden_paths.State(lambda e: e in cluster.environments, lambda s, e: (s, e) in services),
        record=Recorder(),
        catalog=catalog,
        cluster=cluster,
        delivery=FakeDelivery(),
        quality=FakeQuality(),
        wait_seconds=0,
        sleep=lambda _: None,
    )


# The sample organization of the demo.
from platform_api.identity import Identity  # noqa: E402

MARTA = Identity("person", "marta", None, ("checkout",), ("developer",), "platformctl")
ANA = Identity("person", "ana", None, ("platform-team",), ("approver", "developer"), "platformctl")
MARTAS_AGENT = Identity("agent", "marta", "claude-code", ("checkout",), ("developer",), "claude-code")
LUIS_AGENT = Identity("agent", "luis", "claude-code", ("payments",), ("developer",), "claude-code")
CARLOS = Identity("person", "carlos", None, ("checkout",), ("approver", "developer"), "portal")
LUIS = Identity("person", "luis", None, ("payments",), ("approver", "developer"), "portal")
MARTA_APPROVER = Identity("person", "marta", None, ("checkout",), ("approver", "developer"), "portal")
CI_AGENT = Identity("autonomous", None, "ci-agent", ("checkout",), (), "ci-agent")
