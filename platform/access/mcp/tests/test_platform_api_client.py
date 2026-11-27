import io
import json
import urllib.error
import uuid

import pytest

from platform_mcp import platform_api_client as api


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_runs_code_golden_paths_in_the_platform_api(monkeypatch):
    sent = []

    def urlopen(request, timeout):
        sent.append(request)
        return Response(json.dumps({"status": "created", "repository": "http://git/platform/orders"}).encode())

    monkeypatch.setattr(api.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("PLATFORM_API_TOKEN", "s3cret")
    result = api.create_repository("spring-service", {"name": "orders"}, "agent:claude-code")
    assert result["status"] == "created"
    request = sent[0]
    assert request.full_url.endswith("/v1/golden-paths/spring-service/repositories")
    assert request.get_header("Authorization") == "Bearer s3cret"
    assert json.loads(request.data) == {"parameters": {"name": "orders"}, "requester": "agent:claude-code"}


def test_reports_why_the_platform_refused(monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 422, "Unprocessable", {},
                                     io.BytesIO(b'{"error": "Environment \'x\' does not exist. Request it first."}'))

    monkeypatch.setattr(api.urllib.request, "urlopen", urlopen)
    with pytest.raises(api.RequestFailed, match="does not exist"):
        api.create_repository("spring-service", {}, "agent:claude-code")


def test_says_when_the_platform_api_is_not_reachable(monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(api.urllib.request, "urlopen", urlopen)
    with pytest.raises(api.RequestFailed, match="not reachable"):
        api.create_repository("spring-service", {}, "agent:claude-code")


def test_clone_url_carries_the_push_account(monkeypatch):
    monkeypatch.setattr(api, "GIT_URL", "https://alb.example.com:3000")
    monkeypatch.setenv("GIT_PUSH_USERNAME", "developer")
    # A value made up here, with a character that must be escaped in a URL.
    value = f"{uuid.uuid4().hex}/x"
    monkeypatch.setenv("GIT_PUSH_PASSWORD", value)
    expected = f"https://developer:{value.replace('/', '%2F')}@alb.example.com:3000/platform/loyalty-points.git"
    assert api.push_url("loyalty-points") == expected
    monkeypatch.delenv("GIT_PUSH_PASSWORD")
    assert api.push_url("loyalty-points") == "https://alb.example.com:3000/platform/loyalty-points.git"
