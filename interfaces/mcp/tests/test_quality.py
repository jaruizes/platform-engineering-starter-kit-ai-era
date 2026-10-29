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
