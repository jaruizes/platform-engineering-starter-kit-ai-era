import pytest

from platform_mcp import portal


def fake_portal(monkeypatch, statuses, events=()):
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        if method == "POST":
            return {"id": "task-1"}
        if path.endswith("/events"):
            return list(events)
        return {"status": statuses.pop(0)}

    monkeypatch.setattr(portal, "_request", request)
    monkeypatch.setattr(portal.time, "sleep", lambda _: None)
    return calls


def test_runs_the_template_until_it_completes(monkeypatch):
    calls = fake_portal(monkeypatch, ["processing", "completed"])
    portal.run_template("spring-service", {"name": "orders-service"})
    assert calls[0] == (
        "POST",
        "/api/scaffolder/v2/tasks",
        {"templateRef": "template:default/spring-service", "values": {"name": "orders-service"}},
    )


def test_reports_why_the_template_failed(monkeypatch):
    fake_portal(monkeypatch, ["failed"], events=[
        {"body": {"message": "Repository already exists\n    at stack"}},
        {"body": {"message": "Run completed with status: failed"}},
    ])
    with pytest.raises(portal.TemplateFailed, match="Repository already exists"):
        portal.run_template("spring-service", {"name": "orders-service"})


def test_says_when_the_portal_is_not_deployed(monkeypatch):
    monkeypatch.delenv("PORTAL_TOKEN", raising=False)
    with pytest.raises(portal.TemplateFailed, match="no token"):
        portal.run_template("spring-service", {})


def test_clone_url_carries_the_push_account(monkeypatch):
    monkeypatch.setattr(portal, "GIT_URL", "https://alb.example.com:3000")
    monkeypatch.setenv("GIT_PUSH_USERNAME", "developer")
    monkeypatch.setenv("GIT_PUSH_PASSWORD", "s3cr/t")
    assert portal.push_url("loyalty-points") == "https://developer:s3cr%2Ft@alb.example.com:3000/platform/loyalty-points.git"
    monkeypatch.delenv("GIT_PUSH_PASSWORD")
    assert portal.push_url("loyalty-points") == "https://alb.example.com:3000/platform/loyalty-points.git"
