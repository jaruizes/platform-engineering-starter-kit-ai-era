"""New Zero-UI Golden Path reuses the portal scaffolder and a verified backend."""
import pytest

from platform_mcp import mcp_server, platform, portal


def _mock_backend(monkeypatch, *, exists=True):
    monkeypatch.setattr(platform, "get_environment", lambda name: {"metadata": {"name": name}} if exists else None)
    monkeypatch.setattr(platform, "list_spring_services", lambda: [{
        "metadata": {"name": "retail-sales-insights", "namespace": "env-retail-demo"}
    }] if exists else [])
    calls = []
    monkeypatch.setattr(portal, "run_template", lambda name, values: calls.append((name, values)))
    monkeypatch.setattr(portal, "repository_url", lambda name: f"http://git/platform/{name}")
    monkeypatch.setattr(portal, "push_url", lambda name: f"http://git/platform/{name}.git")
    monkeypatch.setattr(platform, "record", lambda *args, **kwargs: None)
    return calls


def test_golden_path_is_discoverable():
    path = next(x for x in platform.GOLDEN_PATHS if x["name"] == "api-mcp-adapter")
    assert path["tool"] == "create_api_mcp_adapter"
    assert "backend_service" in path["parameters"]


def test_creates_adapter_from_existing_backend(monkeypatch):
    calls = _mock_backend(monkeypatch)
    response = mcp_server.create_api_mcp_adapter(
        "retail-sales-mcp", "Retail insights", "platform-team",
        "retail-sales-insights", "retail-demo",
    )
    assert response["status"] == "created"
    assert response["backend_service"] == "retail-sales-insights"
    assert "port-forward svc/retail-sales-mcp" in response["next_step"]
    assert "claude mcp add --scope user --transport http" in response["next_step"]
    assert calls[0][0] == "api-mcp-adapter"
    assert calls[0][1]["backendService"] == "retail-sales-insights"
    assert calls[0][1]["environment"] == "retail-demo"


def test_requires_existing_backend(monkeypatch):
    calls = _mock_backend(monkeypatch, exists=False)
    response = mcp_server.create_api_mcp_adapter(
        "retail-sales-mcp", "Retail insights", "platform-team",
        "retail-sales-insights", "retail-demo",
    )
    assert response["status"] == "failed"
    assert calls == []


def test_rejects_bad_names_before_accessing_platform():
    with pytest.raises(ValueError):
        mcp_server.create_api_mcp_adapter(
            "adapter", "x", "platform-team", "../backend", "retail-demo",
        )
