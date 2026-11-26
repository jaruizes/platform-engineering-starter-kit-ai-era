import json

from kubernetes.client.exceptions import ApiException

from platform_mcp import platform


def _denial(message: str) -> ApiException:
    err = ApiException(status=400, reason="Bad Request")
    err.body = json.dumps({"message": message})
    return err


def test_denial_reason_extracts_policy_message():
    err = _denial(
        'admission webhook "vpol.validate.kyverno.svc-fail" denied the request: '
        "Policy agent-guardrails failed: Human approval required: agents can only request small environments"
    )
    assert platform.is_policy_denial(err)
    reason = platform.denial_reason(err)
    assert reason.startswith("Human approval required")
    assert platform.Denied(reason).needs_human_approval


def test_summarize_environment():
    env = {
        "metadata": {
            "name": "pr-42",
            "creationTimestamp": "2026-10-19T10:00:00Z",
            "annotations": {
                "platform.starterkit.dev/requested-by": "claude-code",
                "platform.starterkit.dev/requester-type": "agent",
            },
        },
        "spec": {"team": "payments", "size": "small", "ttlHours": 8, "purpose": "test"},
        "status": {"namespace": "env-pr-42", "estimatedDailyCost": "1.50",
                   "conditions": [{"type": "Ready", "status": "True"}]},
    }
    s = platform.summarize_environment(env)
    assert s["ready"] and s["requester_type"] == "agent"
    assert s["expires_at"].startswith("2026-10-19T18:00:00")
    assert s["estimated_daily_cost_eur"] == 1.5


def test_compute_metrics():
    envs = [
        {"team": "payments", "requester_type": "agent", "estimated_daily_cost_eur": 1.5},
        {"team": "payments", "requester_type": "human", "estimated_daily_cost_eur": 3.0},
        {"team": "checkout", "requester_type": "human", "estimated_daily_cost_eur": 1.5},
    ]
    activity = [
        {"component": "platform-mcp", "action": "RequestAccepted"},
        {"component": "platform-mcp", "action": "RequestNeedsApproval"},
        {"component": "platform-console", "action": "Approved"},
    ]
    approvals = [{"status": "pending"}, {"status": "approved"}]
    m = platform.compute_metrics(envs, approvals, activity)
    assert m["agent_share"] == 33
    assert m["agent_requests"] == 2
    assert m["agent_first_time_pass_rate"] == 50
    assert m["denied_by_policy"] == 1
    assert m["pending_approvals"] == 1
    assert m["cost_by_team"] == {"checkout": 1.5, "payments": 4.5}


def test_summarize_capability_reads_the_xrd():
    import yaml
    from pathlib import Path

    xrd = yaml.safe_load((Path(__file__).parents[3] / "platform/capabilities/postgres-database/definition.yaml").read_text())
    c = platform.summarize_capability(xrd)
    assert c["name"] == "postgres-database" and c["kind"] == "PostgresDatabase"
    assert c["api_version"] == "platform.starterkit.dev/v1alpha1" and c["plural"] == "postgresdatabases"
    assert c["parameters"]["size"]["enum"] == ["small", "medium", "large"]
    assert c["estimated_daily_cost_eur"]["large"] == "8.00"
    assert len(c["guardrails"]) == 3 and c["tool"] == "request_capability"


def test_capability_manifest_marks_the_agent():
    cap = {"api_version": "platform.starterkit.dev/v1alpha1", "kind": "PostgresDatabase", "scope": "Namespaced"}
    m = platform.capability_manifest(cap, "orders-db", "env-pr-42", {"size": "small"}, "claude-code")
    assert m["metadata"] == {"name": "orders-db", "namespace": "env-pr-42",
                             "annotations": {"platform.starterkit.dev/agent": "claude-code"}}
    assert m["spec"] == {"size": "small"}


def test_summarize_resource_hides_crossplane_internals():
    obj = {
        "kind": "PostgresDatabase",
        "metadata": {"name": "orders-db", "namespace": "env-pr-42",
                     "annotations": {"platform.starterkit.dev/requester-type": "agent"}},
        "spec": {"size": "small", "crossplane": {"resourceRefs": []}},
        "status": {"secretName": "orders-db-connection",
                   "conditions": [{"type": "Ready", "status": "False", "message": "Unready resources: server"}]},
    }
    s = platform.summarize_resource(obj)
    assert s["parameters"] == {"size": "small"}
    assert s["status"] == {"secretName": "orders-db-connection"}
    assert not s["ready"] and s["waiting_for"] == "Unready resources: server"
