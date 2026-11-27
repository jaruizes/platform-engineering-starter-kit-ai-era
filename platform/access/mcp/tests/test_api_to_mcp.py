"""The Zero-UI Golden Path runs in the platform API, which checks the backend."""
import pytest

from platform_mcp import mcp_server, platform, platform_api_client


def _mock_platform_api(monkeypatch, *, refuse=None):
    calls = []

    def create_repository(golden_path, parameters, requester):
        calls.append((golden_path, parameters, requester))
        if refuse:
            raise platform_api_client.RequestFailed(refuse)
        name = parameters["name"]
        return {"status": "created", "repository": f"http://git/platform/{name}",
                "catalogEntity": f"component:default/{name}"}

    monkeypatch.setattr(platform_api_client, "create_repository", create_repository)
    monkeypatch.setattr(platform_api_client, "push_url", lambda name: f"http://git/platform/{name}.git")
    return calls


def test_golden_path_is_discoverable():
    path = next(x for x in platform.GOLDEN_PATHS if x["name"] == "api-mcp-adapter")
    assert path["tool"] == "create_api_mcp_adapter"
    assert "backend_service" in path["parameters"]


def test_creates_adapter_from_existing_backend(monkeypatch):
    calls = _mock_platform_api(monkeypatch)
    response = mcp_server.create_api_mcp_adapter(
        "retail-sales-mcp", "Retail insights", "platform-team",
        "retail-sales-insights", "retail-demo",
    )
    assert response["status"] == "created"
    assert response["backend_service"] == "retail-sales-insights"
    assert "port-forward svc/retail-sales-mcp" in response["next_step"]
    assert "claude mcp add --scope user --transport http" in response["next_step"]
    golden_path, parameters, requester = calls[0]
    assert golden_path == "api-mcp-adapter"
    assert parameters["backendService"] == "retail-sales-insights"
    assert parameters["environment"] == "retail-demo"
    assert requester == "agent:unknown-agent"


def test_reports_the_platform_refusal(monkeypatch):
    _mock_platform_api(monkeypatch, refuse="SpringService 'retail-sales-insights' not found in env-retail-demo.")
    response = mcp_server.create_api_mcp_adapter(
        "retail-sales-mcp", "Retail insights", "platform-team",
        "retail-sales-insights", "retail-demo",
    )
    assert response["status"] == "failed"
    assert "not found" in response["reason"]


def test_rejects_bad_names_before_accessing_platform():
    with pytest.raises(ValueError):
        mcp_server.create_api_mcp_adapter(
            "adapter", "x", "platform-team", "../backend", "retail-demo",
        )


def test_create_service_goes_through_the_platform_api(monkeypatch):
    calls = _mock_platform_api(monkeypatch)
    response = mcp_server.create_service("loyalty-points", "Loyalty", "checkout", "points", "checkout-dev")
    assert response["status"] == "created"
    assert response["catalog_entity"] == "component:default/loyalty-points"
    assert calls[0][0] == "spring-service"
    assert calls[0][1] == {"name": "loyalty-points", "description": "Loyalty", "owner": "checkout",
                           "basePackage": "com.starterkit", "module": "points", "environment": "checkout-dev"}


def test_agent_names_become_safe_requesters():
    assert mcp_server._requester("claude-code") == "agent:claude-code"
    assert mcp_server._requester("Claude Desktop") == "agent:Claude-Desktop"
    assert mcp_server._requester("???") == "agent:unknown-agent"


def test_agents_only_delete_what_agents_requested(monkeypatch):
    envs = {
        "payments-dev": {"metadata": {"name": "payments-dev",
                                      "annotations": {"platform.starterkit.dev/requester-type": "human"}}},
        "agent-test": {"metadata": {"name": "agent-test",
                                    "annotations": {"platform.starterkit.dev/requester-type": "agent"}}},
    }
    deleted = []
    monkeypatch.setattr(platform, "get_environment", envs.get)
    monkeypatch.setattr(platform, "delete_environment", deleted.append)
    monkeypatch.setattr(platform, "record", lambda *args, **kwargs: None)
    refused = mcp_server.delete_environment("payments-dev")
    assert refused["status"] == "denied"
    assert deleted == []
    assert mcp_server.delete_environment("agent-test")["status"] == "deleted"
    assert deleted == ["agent-test"]
    assert mcp_server.delete_environment("nope")["status"] == "not_found"
