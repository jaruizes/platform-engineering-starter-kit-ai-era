"""platformctl is a thin channel: it sends the request and shows the answer."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("platformctl", ROOT / "platform/access/cli/platformctl.py")
platformctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platformctl)


def test_create_sends_the_parameters_not_who_asks(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(platformctl, "call", lambda method, path, body=None: sent.append((method, path, body))
                        or {"status": "created"})
    platformctl.main(["create", "spring-service", "name=loyalty-points", "description=Loyalty points"])
    # Who asks comes from the token.
    assert sent == [("POST", "/v1/golden-paths/spring-service/repositories", {
        "parameters": {"name": "loyalty-points", "description": "Loyalty points"}})]
    assert json.loads(capsys.readouterr().out)["status"] == "created"


def test_propose_reads_the_definition(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(platformctl, "call", lambda method, path, body=None: sent.append(body) or {})
    definition = ROOT / "platform/capabilities/infrastructure/postgres-database/capability.yaml"
    platformctl.main(["propose", str(definition), "--name", "Ana"])
    assert sent[0]["definition"]["metadata"]["name"] == "postgres-database"
    assert sent[0]["requesterName"] == "Ana"


def test_rejects_parameters_without_a_value():
    with pytest.raises(SystemExit, match="key=value"):
        platformctl.main(["create", "spring-service", "loyalty-points"])


def test_sends_the_signed_in_token(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("PLATFORM_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="Not signed in"):
        platformctl.access_token()
    platformctl._save("platformctl", {"access_token": "abc", "refresh_token": "r", "expires_in": 300})
    assert platformctl.access_token() == "abc"
    assert oct(platformctl._token_file("platformctl").stat().st_mode)[-3:] == "600"
    sent = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"kind": "person"}'

    monkeypatch.setattr(platformctl.urllib.request, "urlopen", lambda request, timeout: sent.append(request) or Response())
    assert platformctl.call("GET", "/v1/me") == {"kind": "person"}
    assert sent[0].get_header("Authorization") == "Bearer abc"


def test_requests_environments(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(platformctl, "call", lambda method, path, body=None: sent.append((method, path, body)) or {})
    platformctl.main(["request-environment", "checkout", "pr-1", "Test PR 1", "--size", "medium", "--ttl", "24"])
    platformctl.main(["delete-environment", "pr-1"])
    assert sent == [("POST", "/v1/environments", {"team": "checkout", "name": "pr-1", "purpose": "Test PR 1",
                                                  "size": "medium", "ttlHours": 24}),
                    ("DELETE", "/v1/environments/pr-1", None)]


def test_approvals(monkeypatch, capsys):
    sent = []
    pending = [{"id": "load-test-1a2b", "status": "pending", "team": "checkout", "agent": "claude-code",
                "on_behalf_of": "marta", "request": {"kind": "Environment", "name": "load-test", "size": "large"},
                "can_decide": False, "cannot_decide_reason": "Four eyes: marta cannot decide"}]
    monkeypatch.setattr(platformctl, "call",
                        lambda method, path, body=None: sent.append((method, path, body)) or
                        (pending if method == "GET" else {"status": "approved"}))
    platformctl.main(["approvals"])
    assert "claude-code for marta" in capsys.readouterr().out
    platformctl.main(["approve", "load-test-1a2b", "--note", "ok"])
    platformctl.main(["reject", "load-test-1a2b"])
    assert sent == [("GET", "/v1/approvals?status=pending", None),
                    ("POST", "/v1/approvals/load-test-1a2b/decision", {"decision": "approve", "note": "ok"}),
                    ("POST", "/v1/approvals/load-test-1a2b/decision", {"decision": "reject", "note": ""})]


def test_login_uses_pkce_in_the_device_flow(monkeypatch):
    import base64
    import hashlib
    posts, saved = [], []

    def post(url, data):
        posts.append((url, data))
        if url.endswith("/auth/device"):
            return {"device_code": "dc", "user_code": "ABCD", "verification_uri": "http://kc/device", "interval": 0}
        return {"access_token": "t"}

    monkeypatch.setattr(platformctl, "_post_form", post)
    monkeypatch.setattr(platformctl, "_save", lambda client, tokens: saved.append(client))
    monkeypatch.setattr(platformctl.time, "sleep", lambda seconds: None)
    platformctl.login("platformctl")
    device, token = posts[0][1], posts[1][1]
    # The realm requires S256 PKCE on the person-facing clients, device flow included.
    assert device["code_challenge_method"] == "S256"
    expected = base64.urlsafe_b64encode(hashlib.sha256(token["code_verifier"].encode()).digest()).rstrip(b"=").decode()
    assert device["code_challenge"] == expected
    assert saved == ["platformctl"]
