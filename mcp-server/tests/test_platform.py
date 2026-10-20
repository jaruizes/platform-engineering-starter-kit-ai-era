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
