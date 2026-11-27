"""The MCP tools are a channel of the platform API: they forward the agent's
token and turn the platform's answer into something an agent can act on."""
import pytest

from platform_mcp import mcp_server, platform_api_client as api


class Ctx:
    def __init__(self, token="marta-claude-token"):
        self.headers = {"authorization": f"Bearer {token}"} if token else {}


def _mock_platform_api(monkeypatch, *, refuse=None, status=403):
    calls = []

    def request(token, method, path, body=None, query=None, timeout=180):
        calls.append((token, method, path, body, query))
        if refuse:
            raise api.RequestFailed(refuse, status)
        if path.endswith("/repositories"):
            name = body["parameters"]["name"]
            return {"status": "created", "repository": f"http://git/platform/{name}",
                    "catalogEntity": f"component:default/{name}"}
        return {"status": "accepted"}

    monkeypatch.setattr(api, "request", request)
    monkeypatch.setattr(api, "push_url", lambda name: f"http://git/platform/{name}.git")
    return calls


def test_creates_adapter_from_existing_backend(monkeypatch):
    calls = _mock_platform_api(monkeypatch)
    result = mcp_server.create_api_mcp_adapter(
        "retail-sales-mcp", "Retail tools", "platform-team", "retail-sales-insights", "retail-demo", ctx=Ctx())
    assert result["status"] == "created"
    token, method, path, body, _ = calls[0]
    assert (token, method, path) == ("marta-claude-token", "POST", "/v1/golden-paths/api-mcp-adapter/repositories")
    assert body["parameters"]["backendService"] == "retail-sales-insights"
    assert "requester" not in body, "the identity comes from the token, not from the tool"
    assert "port-forward svc/retail-sales-mcp" in result["next_step"]


def test_reports_the_platform_refusal(monkeypatch):
    _mock_platform_api(monkeypatch, refuse="Team scope: claude-code for marta is in checkout, not payments")
    result = mcp_server.create_service("orders", "Orders", "payments", "orders", ctx=Ctx())
    assert result["status"] == "denied" and "not payments" in result["reason"]
    assert "do not retry for another team" in result["next_step"]


def test_rejects_bad_names_before_accessing_platform(monkeypatch):
    calls = _mock_platform_api(monkeypatch)
    with pytest.raises(ValueError):
        mcp_server.create_api_mcp_adapter("Bad_Name", "x", "platform-team", "retail-sales-insights", "retail-demo")
    assert calls == []


def test_every_tool_forwards_the_token(monkeypatch):
    calls = _mock_platform_api(monkeypatch)
    mcp_server.request_environment("checkout", "pr-1", "Test", ctx=Ctx("t1"))
    mcp_server.list_environments(ctx=Ctx("t2"))
    mcp_server.deploy_service("pr-1", "checkout-api", ctx=Ctx("t3"))
    mcp_server.request_capability("PostgresDatabase", "orders-db", "pr-1", {"size": "small"}, ctx=Ctx("t4"))
    mcp_server.get_service_status("orders", "pr-1", ctx=Ctx("t5"))
    mcp_server.delete_environment("pr-1", ctx=Ctx("t6"))
    assert [(c[0], c[1], c[2]) for c in calls] == [
        ("t1", "POST", "/v1/environments"),
        ("t2", "GET", "/v1/environments"),
        ("t3", "POST", "/v1/environments/pr-1/services"),
        ("t4", "POST", "/v1/capabilities/PostgresDatabase/requests"),
        ("t5", "GET", "/v1/environments/pr-1/services/orders/status"),
        ("t6", "DELETE", "/v1/environments/pr-1"),
    ]


def test_create_service_goes_through_the_platform_api(monkeypatch):
    calls = _mock_platform_api(monkeypatch)
    result = mcp_server.create_service("orders", "Orders", "checkout", "orders", environment="checkout-dev", ctx=Ctx())
    assert result["status"] == "created" and result["clone"] == "git clone http://git/platform/orders.git"
    assert calls[0][3]["parameters"]["environment"] == "checkout-dev"
