import json
from urllib.error import HTTPError

import pytest

from platform_mcp import quality


def test_quality_status_returns_commit_and_failed_findings(monkeypatch):
    payload = {"status": "failed", "sourceCommit": "abc", "architecture": "backend-spring-v2",
               "profile": {"name": "backend-spring-v2", "version": 1},
               "checks": [{"id": "archunit", "status": "failed"}]}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return json.dumps(payload).encode()

    monkeypatch.setattr(quality, "urlopen", lambda url, timeout: Response())
    result = quality.quality_status("orders-service")
    assert result["sourceCommit"] == "abc"
    assert result["findings"] == payload["checks"]


def test_quality_status_validates_service_before_network(monkeypatch):
    monkeypatch.setattr(quality, "urlopen", lambda *_args, **_kwargs: pytest.fail("network must not be called"))
    with pytest.raises(ValueError):
        quality.quality_status("../secret")


def test_missing_evidence_is_unknown(monkeypatch):
    def missing(*_args, **_kwargs):
        raise HTTPError("url", 404, "missing", {}, None)
    monkeypatch.setattr(quality, "urlopen", missing)
    assert quality.quality_status("orders-service")["status"] == "unknown"


def test_quality_status_adds_read_only_sonar_findings(monkeypatch):
    monkeypatch.setenv("SONAR_HOST_URL", "http://sonarqube.quality.svc:9000")
    monkeypatch.setenv("SONAR_TOKEN", "analysis-token")
    payloads = [
        {"status": "passed", "sourceCommit": "abc", "checks": []},
        {"analyses": [{"revision": "abc"}]},
        {"total": 1, "issues": [{"key": "issue-1", "rule": "java:S106", "severity": "MAJOR",
                                   "type": "CODE_SMELL", "message": "Use a logger", "line": 12}]},
        {"projectStatus": {"status": "ERROR"}},
    ]
    requests = []

    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout):
        requests.append(request)
        assert timeout == 5
        return Response(payloads.pop(0))

    monkeypatch.setattr(quality, "urlopen", fake_urlopen)
    result = quality.quality_status("orders-service")
    assert result["sonar"]["status"] == "error"
    assert result["sonar"]["sourceCommit"] == "abc"
    assert result["sonar"]["findings"][0]["rule"] == "java:S106"
    assert all(request.get_header("Authorization", "").startswith("Basic ") for request in requests[1:])
